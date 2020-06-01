from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from urllib.parse import parse_qs
from io import BytesIO
import http
import os
import json
import threading
import sys
import asyncio
import _thread

from modules.core.config import Config
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.real_path = os.path.dirname(os.path.realpath(__file__))
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path in ["/restart.html"]:
            file = "/restart.html"
        else:
            file = "/index.html"
        
        with open(self.real_path+file) as fh:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(fh.read().encode())        
       
            
    def do_POST(self):

        if self.path == '/get_settings.json':
            self.send_response(200)
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            response = BytesIO()
            response.write(WebServer.generate_settings())
            self.wfile.write(response.getvalue())           
        elif self.path == '/set_general_settings.json':
            WebServer.bot.CoreConfig.setGeneralSetting(self.data_redirect("/restart.html"))
            _thread.start_new_thread(WebServer.restart, ())
        elif self.path == '/get_general_settings.json':
            self.send_response(200)
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            response = BytesIO()
            response.write(WebServer.generate_general_settings())
            self.wfile.write(response.getvalue())
        elif self.path == '/set_settings.json':
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            self.send_response(200)
            self.end_headers()
            
            body = "?"+body.decode('utf-8')
            parsed = urlparse(body)
            WebServer.bot.CoreConfig.setCommandSetting(parse_qs(parsed.query))            
        elif self.path == '/terminate_bot.json':
            self.data_redirect()
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            asyncio.ensure_future(WebServer.terminate())
            loop.run_forever()      
        elif self.path == '/restart_bot.json':
            self.data_redirect("/restart.html")
            _thread.start_new_thread(WebServer.restart, ())
        elif self.path == '/add_role.json':
            WebServer.bot.CoreConfig.add_role(self.data_redirect())      
        elif self.path == '/delete_role.json':
            WebServer.bot.CoreConfig.delete_role(self.data_redirect())        
        elif self.path == '/active_deall_role.json':
            WebServer.bot.CoreConfig.deall_role(self.data_redirect())        
        elif self.path == '/active_all_role.json':
            WebServer.bot.CoreConfig.all_role(self.data_redirect())         
        elif "set_module_settings::" in self.path:
            WebServer.set_module_settings(self.path, self.data_redirect())        
        elif self.path == '/get_module_settings.json':
            #Default response
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            self.send_response(200)
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            
            response = BytesIO()
            response.write(WebServer.get_module_settings())
            self.wfile.write(response.getvalue())
        else:
            #Default response
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            self.send_response(200)
            self.end_headers()
            
            response = BytesIO()
            response.write(b'POST request. ')
            response.write(b'Received: ')
            response.write(body)
            self.wfile.write(response.getvalue())

    def data_redirect(self, file="/"):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        self.send_response(301)
        self.send_header('Location', file)
        self.end_headers()
        
        body = "?"+body.decode('utf-8')
        parsed = urlparse(body)
        return parse_qs(parsed.query)

class WebServer():
    bot = None
    CommandChecker = None
    CoreConfig = None
    def __init__(self, bot, CommandChecker, CoreConfig):
        self.bot = bot
        WebServer.bot = bot
        WebServer.CommandChecker = CommandChecker
        WebServer.CoreConfig = CoreConfig
        port = 8000
        
        daemon = threading.Thread(name='web_server',
                                  target=self._start_server,
                                  args=[port])
        daemon.setDaemon(True) # Set as a daemon so it will be killed once the main thread is dead.
        daemon.start()

        
    def _start_server(self, port=8000):
        print("Settings page online on: http://localhost:{}/".format(port))
        self.httpd = HTTPServer(('localhost', port), SimpleHTTPRequestHandler)
        self.httpd.serve_forever()
    
    def generate_settings():
        if(WebServer.CommandChecker):
            WebServer.bot.CoreConfig.load_role_permissions() #Load permissions from file

            settings = {}
            roles = WebServer.bot.CoreConfig.cfgPermissions_Roles.keys()
            for command in WebServer.bot.CoreConfig.bot.commands:
                settings[str(command)] = {}
                for role in roles:
                    settings[str(command)][role] = WebServer.bot.CoreConfig.cfgPermissions_Roles[role]["command_"+str(command)]
            settings["head"] = list(roles)
            settings["registered"] = WebServer.CommandChecker.registered
            json_dump = json.dumps(settings)
            return json_dump.encode()       

    def get_module_settings():
        if(WebServer.CommandChecker):
            settings = {}
            for cfg in WebServer.CoreConfig.registered:
                settings[os.path.basename(cfg.cfg_path).split(".")[0]] = cfg.cfg

            json_dump = json.dumps(settings)
            return json_dump.encode()    
        
    def generate_general_settings():
        WebServer.bot.CoreConfig.load_role_permissions() #Load permissions from file
        json_dump = json.dumps(WebServer.bot.CoreConfig.cfg.cfg)
        return json_dump.encode()
        
    def set_module_settings(file, data):
        file = file.split("::")[1]
        for cfg in WebServer.CoreConfig.registered:
            if(os.path.basename(cfg.cfg_path) == file):
                for key, value in cfg.items():
                    if(isinstance(value, int)):
                        cfg[key] = int(data[key][0])
                    elif(isinstance(value, str)):
                        cfg[key] = str(data[key][0])
                    elif(value == None):
                        if(key in data):
                            cfg[key] = data[key][0]
                    else:
                        raise Exception("Unkown datatype '{}'".format(type(value)))
                break

            
            
    async def terminate():
        WebServer.bot.terminated = True
        await WebServer.bot.logout()
    
    def restart():
        WebServer.bot.restarting = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        asyncio.ensure_future(WebServer._restart())
        loop.run_forever()   
    
    async def _restart():
        await asyncio.sleep(2)
        await WebServer.bot.logout()
        