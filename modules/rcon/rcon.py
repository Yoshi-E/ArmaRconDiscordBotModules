﻿import socket
import os
import sys
import re
import zlib
import binascii
import asyncio
import traceback
from collections import deque
import datetime
import codecs
#Author: Yoshi_E
#Date: 2019.06.14
#Found on github: https://github.com/Yoshi-E/Python-BEC-RCon
#Python3.6 Implementation of data protocol: https://www.battleye.com/downloads/BERConProtocol.txt
#Code based on 'felixms' https://github.com/felixms/arma-rcon-class-php
#License: https://creativecommons.org/licenses/by-nc-sa/4.0/
import builtins as __builtin__
import logging

logging.basicConfig(filename='error.log',
                    level=logging.INFO, 
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def print(*args, **kwargs):
    if(len(args)>0):
        logging.info(args[0])
    return __builtin__.print(*args, **kwargs)
    
class ARC():

    def __init__(self, serverIP, RConPassword, serverPort = 2302, options = {}):

        self.options = {
            'timeoutSec'    : 5,
            'autosaveBans'  : False,
            'debug'         : False
        }
        
        self.codec = "iso-8859-1" #text encoding (not all codings are supported)
        
        self.socket = None;
        # Status of the connection
        self.disconnected = True
        # Stores all recent server message (Format: array([datetime, msg],...))
        self.serverMessage = deque( maxlen=100) 
        # Event Handlers (Format: array([name, function],...)
        self.Events = []
        #Multi packet buffer
        self.MultiPackets = []
        # Locks Sending until space to send is available 
        self.sendLock = False
        # Stores all recent command returned data (Format: array([datetime, msg],...))
        self.serverCommandData = deque( maxlen=10) 
        
        if (type(serverPort) != int or type(RConPassword) != str or type(serverIP) != str):
            raise Exception('Wrong constructor parameter type(s)!')
        if(serverIP == "localhost"): #localhost is not supported
            self.serverIP = "127.0.0.1"
        else:
            self.serverIP = serverIP
        self.serverPort = serverPort
        self.rconPassword = RConPassword
        self.options = {**self.options, **options}
        self.checkOptionTypes()
        self.connect()

    
    #destructor
    def __del__(self):
        self.disconnect()
    
    #Closes the connection
    def disconnect(self):
        if (self.disconnected):
            return None
        self.on_disconnect()
        self.socket.close()
        self.socket = None
        self.disconnected = True
    
    #Creates a connection to the server
    def connect(self):
        self.sendLock = False
        if (self.disconnected == False):
            self.disconnect()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #
        self.socket.connect((self.serverIP,  self.serverPort)) # #"udp://"+
        if (self.socket == False):
            raise Exception('Failed to create socket!')
        
        self.socket.setblocking(0)
        self.authorize()
        self.disconnected = False
        
        #spawn async tasks
        self.listenForDataTask = asyncio.ensure_future(self.listenForData())
        self.keepAliveLoopTask = asyncio.ensure_future(self.keepAliveLoop())
        
    #Closes the current connection and creates a new one
    def reconnect(self):
        if (self.disconnected == False):
            self.disconnect()
        self.connect()
        return None
    
    #Validate all option types
    def checkOptionTypes(self):
        if (type(self.options['timeoutSec']) != int):
            raise Exception("Expected option 'timeoutSec' to be integer, got %s" % type(self.options['timeoutSec']))
        if (type(self.options['autosaveBans']) != bool):
            raise Exception("Expected option 'autosaveBans' to be boolean, got %s" % type(self.options['autosaveBans']))
        if (type(self.options['debug']) != bool):
            raise Exception("Expected option 'debug' to be boolean, got %s" % type(self.options['debug']))

    #Sends the login data to the server in order to send commands later
    def authorize(self):
        sent = self.writeToSocket(self.getLoginMessage())
        if (sent == False):
            raise Exception('Failed to send login!')

    #sends the RCon command, but waits until command is confirmed before sending another one
    async def send(self, command):
        for i in range(0,10*60):
            if(self.sendLock == False): #Lock released by waitForResponse()
                self.sendLock = True
                if (self.disconnected):
                    raise Exception('Failed to send command, because the connection is closed!')
            
                msgCRC = self.getMsgCRC(command)
                head = 'BE'+chr(int(msgCRC[0],16))+chr(int(msgCRC[1],16))+chr(int(msgCRC[2],16))+chr(int(msgCRC[3],16))+chr(int('ff',16))+chr(int('01',16))+chr(int('0',16))
                msg = head+command
                if (self.writeToSocket(msg) == False):
                    raise Exception('Failed to send command!')
                return True
            else:
                await asyncio.sleep(0.1) #watis 0.1 second before checking again
        raise Exception("Failed to send in time: "+command)
    
    #Writes the given message to the socket
    def writeToSocket(self, message):
        return self.socket.send(bytes(message.encode(self.codec)))
    
    #Debug funcion to view special chars
    def String2Hex(self,string):
        return string.encode(self.codec).hex()

    #Generates the password's CRC32 data
    def getAuthCRC(self):
        #str = self.String2Hex(chr(255)+chr(0)+self.rconPassword.strip())
        str = (chr(255)+chr(0)+self.rconPassword.strip()).encode(self.codec)
        authCRC = '%x' % zlib.crc32(bytes(str))
        authCRC = [authCRC[-2:], authCRC[-4:-2], authCRC[-6:-4], authCRC[0:2]] #working
        return authCRC
    
    #Generates the message's CRC32 data
    def getMsgCRC(self, command):
        str = bytes(((chr(255)+chr(1)+chr(int('0',16))+command).encode(self.codec)))
        msgCRC = ('%x' % zlib.crc32(str)).zfill(8)
        msgCRC = [msgCRC[-2:], msgCRC[-4:-2], msgCRC[-6:-4], msgCRC[0:2]]
        return msgCRC
    
    #Generates the login message
    def getLoginMessage(self):
        authCRC = self.getAuthCRC()
        loginMsg = 'BE'+chr(int(authCRC[0],16))+chr(int(authCRC[1],16))+chr(int(authCRC[2],16))+chr(int(authCRC[3],16))
        loginMsg += chr(int('ff',16))+chr(int('00',16))+self.rconPassword
        return loginMsg
        
###################################################################################################
#####                                  BEC Commands                                            ####
###################################################################################################   

    #Sends a custom command to the server
    async def command(self, command):
        if (is_string(command) == False):
            raise Exception('Wrong parameter type!')
        await self.send(command)
        return await self.waitForResponse()

    #Kicks a player who is currently on the server
    async def kickPlayer(self, player, reason = 'Admin Kick'):
        if (type(player) != int and type(player) != str):
            raise Exception('Expected parameter 1 to be string or integer, got %s' % type(player))
        if (type(reason) != str):
            raise Exception('Expected parameter 2 to be string, got %s' % type(reason))
        await self.send("kick "+str(player)+" "+reason)
        return None

    #Sends a global message to all players
    async def sayGlobal(self, message):
        if (type(message) != str):
            raise Exception('Expected parameter 1 to be string, got %s' % type(message))
        await self.send("Say -1 "+message)
        return None

    #Sends a message to a specific player
    async def sayPlayer(self, player, message):
        if (type(player) != int or type(message) != str):
            raise Exception('Wrong parameter type(s)!')
        await self.send("Say "+str(player)+" "+message)
        return None

    #Loads the "scripts.txt" file without the need to restart the server
    async def loadScripts(self):
        await self.send('loadScripts')
        return None

    #Changes the MaxPing value. If a player has a higher ping, he will be kicked from the server
    async def maxPing(self, ping):
        if (type(ping) != int):
            raise Exception('Expected parameter 1 to be integer, got %s' % type(ping))
        await self.send("MaxPing "+ping)
        return None
    
    #Changes the RCon password
    async def changePassword(self, password):
        if (type(password) != str):
            raise Exception('Expected parameter 1 to be string, got %s' % type(password))
        await self.send("RConPassword password")
        return None
    
    #(Re)load the BE ban list from bans.txt
    async def loadBans(self):
        await self.send('loadBans')
        return None

    #Gets a list of all players currently on the server
    async def getPlayers(self):
        await self.send('players')
        result = await self.waitForResponse()
        return result[1] #strip timedate

    #Gets a list of all players currently on the server as an array
    async def getPlayersArray(self):
        playersRaw = await self.getPlayers()
        players = self.cleanList(playersRaw)
        str = re.findall(r"(\d+)\s+(\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+\b)\s+(\d+)\s+([0-9a-fA-F]+)\(\w+\)\s([\S ]+)", players)
        return self.formatList(str)
    
    #Gets a list of all bans
    async def getMissions(self):
        await self.send('missions')
        return await self.waitForResponse()

    #Ban a player's BE GUID from the server. If time is not specified or 0, the ban will be permanent.
    #If reason is not specified the player will be kicked with the message "Banned".
    async def banPlayer(self, player, reason = 'Banned', time = 0):
        if (type(player) != str and type(player) != int):
            raise Exception('Expected parameter 1 to be integer or string, got %s' % type(player))
        if (type(reason) != str or type(time) != int):
            raise Exception('Wrong parameter type(s)!')
        await self.send("ban "+str(player)+" "+str(time)+" "+reason)
        if (self.options['autosaveBans']):
            self.writeBans()
        return None

    #Same as "banPlayer", but allows to ban a player that is not currently on the server
    async def addBan(self, player, reason = 'Banned', time = 0):
        if (type(player) != str or type(reason) != str or type(time) != int):
            raise Exception('Wrong parameter type(s)!')
        await self.send("addBan "+player+" "+str(time)+" "+reason)
        if (self.options['autosaveBans']):
            self.writeBans()
        return None

    #Removes a ban
    async def removeBan(self, banId):
        if (type(banId) != int):
            raise Exception('Expected parameter 1 to be integer, got %s' % type(banId))
        await self.send("removeBan "+str(banId))
        if (self.options['autosaveBans']):
            self.writeBans()
        return None

    #Gets an array of all bans
    async def getBansArray(self):
        bansRaw = await self.getBans()
        bans = self.cleanList(bansRaw[1])
        str = re.findall(r'(\d+)\s+([0-9a-fA-F]+)\s([perm|\d]+)\s([\S ]+)', bans)
        #PHP preg_match_all("#(\d+)\s+([0-9a-fA-F]+)\s([perm|\d]+)\s([\S ]+)#im", bans, str)
        return self.formatList(str)

    #Gets a list of all bans
    async def getBans(self):
        await self.send('bans')
        return await self.waitForResponse()

    #Removes expired bans from bans file
    async def writeBans(self):
        await self.send('writeBans')
        return None

    #Gets the current version of the BE server
    #@return string The BE server version
    async def getBEServerVersion(self):
        await self.send('version')
        return await self.waitForResponse()


###################################################################################################
#####                                  event handler                                           ####
###################################################################################################
    def add_Event(self, name: str, func):
        events = ["on_command_fail", "on_disconnect", "login_Sucess", "login_fail", "received_ServerMessage", "received_CommandMessage"]
        if(name in events):
            self.Events.append([name,func])
        else:
            raise Exception("Failed to add unkown event: "+name)
            
    def check_Event(self, parent, *args):
        for event in self.Events:
            func = event[1]
            #print(func,pass_self, args)
            if(event[0]==parent):
                    func(args)
###################################################################################################
#####                                  event functions                                         ####
###################################################################################################

    def on_disconnect(self):
        self.check_Event("on_disconnect")
        
    def login_Sucess(self):
        self.check_Event("login_Sucess")
        
    def login_fail(self):
        self.disconnect()
        self.check_Event("login_fail")
     
    def received_ServerMessage(self, packet, message):
        self.serverMessage.append([datetime.datetime.now(), message])
        #print()
        self.sendReciveConfirmation(packet[8]) #confirm with sequence id from packet  
        self.check_Event("received_ServerMessage", message)
    
    #waitForResponse() handles all inbound packets, you can still fetch them here though.
    def received_CommandMessage(self, packet, message):
        if(self.String2Hex(message[0]) =="00"): #is multi packet
            self.MultiPackets.append(message[3:])
            if(int(self.String2Hex(message[1]),16)-1 == int(self.String2Hex(message[2]),16)):
                self.serverCommandData.append([datetime.datetime.now(), "".join(self.MultiPackets)])
                self.MultiPackets = []
        else: #Normal Package
            #print(self.String2Hex(message))
            self.serverCommandData.append([datetime.datetime.now(), message])
        self.check_Event("received_CommandMessage", message)
            
    def on_command_fail(self):
        self.check_Event("on_command_fail")
###################################################################################################
#####                                  common functions                                        ####
###################################################################################################
    #returns when a new command package was receive
    async def waitForResponse(self):
        d = len(self.serverCommandData)
        timeout = self.options['timeoutSec'] * 10 #10 = one second
        for i in range(0,timeout):
            if(d < len(self.serverCommandData)): #new command package was received
                self.sendLock = False #release the lock
                return self.serverCommandData.pop()
            await asyncio.sleep(0.1)
        self.on_command_fail()
        self.sendLock = False
        raise Exception("ERROR, command timed out")
        
            
    def sendReciveConfirmation(self, sequence):
        if (self.disconnected):
            raise Exception('Failed to send command, because the connection is closed!')
        
        #calculate CRC32
        str = bytes((chr(255)+chr(2)+sequence).encode(self.codec))
        msgCRC = ('%x' % zlib.crc32(str)).zfill(8)
        msgCRC = [msgCRC[-2:], msgCRC[-4:-2], msgCRC[-6:-4], msgCRC[0:2]]
        
        #generate send message
        msg = 'BE'+chr(int(msgCRC[0],16))+chr(int(msgCRC[1],16))+chr(int(msgCRC[2],16))+chr(int(msgCRC[3],16))+chr(int('ff',16))+chr(int("02",16))+sequence
        if (self.writeToSocket(msg) == False):
            raise Exception('Failed to send confirmation!')
    
    async def listenForData(self):
        while (self.disconnected == False):
            answer = ""
            try:
                answer = self.socket.recv(102400).decode(self.codec)
                header =  answer[:7]
                crc32_checksum = header[2:-1]
                body = codecs.decode(""+self.String2Hex(answer[9:]), "hex").decode() #some encoding magic (iso-8859-1(with utf-8 chars) --> utf-8)
                packet_type = self.String2Hex(answer[7])
                if(packet_type=="02"): 
                    self.received_ServerMessage(answer, body)
                if(packet_type=="01"):
                    self.received_CommandMessage(answer, body)
                if(packet_type=="00"): #"Login packet"
                    if (ord(answer[len(answer)-1]) == 0): #Raise error when login failed
                        self.login_fail()
                        raise Exception('Login failed, wrong password or wrong port!')
                    else:
                        self.login_Sucess()
            except Exception as e: 
                if(type(e) != BlockingIOError): #ignore "no data recevied" error
                    traceback.print_exc()
            if(answer==""):
                await asyncio.sleep(0.5)
                
            
    async def keepAliveLoop(self):
        while (self.disconnected == False):
            try:
                await self.getBEServerVersion() #self.keepAlive()
            except Exception as e:
                traceback.print_exc()
                self.disconnect() #connection lost
            await asyncio.sleep(20) #package needs to be send every min:1s, max:44s 
  
    #Keep the stream alive. Send package to BE server. Use function before 45 seconds.
    def keepAlive(self):
        if (self.options['debug']):
            print('--Keep connection alive--'+"\n")
        #loginMsg = 'BE'+chr(int(authCRC[0],16))+chr(int(authCRC[1],16))+chr(int(authCRC[2],16))+chr(int(authCRC[3],16))
        keepalive = 'BE'+chr(int("be",16))+chr(int("dc",16))+chr(int("c2",16))+chr(int("58",16))
        keepalive += chr(int('ff', 16))+chr(int('01',16))+chr(int('00',16))
        #print("Alive:",self.String2Hex(keepalive))
        if (self.writeToSocket(keepalive) == False):
            raise Exception('Failed to send command!')
            return False #Failed
            
        return True #Completed

    #Converts BE text "array" list to array
    def formatList(self, str):
        #Create return array
        result = []
        #Loop True the main arrays, each holding a value
        for pair in str:
            #Combines each main value into new array
            result.append([])
            for val in pair:
                result[-1].append(val.strip())
        return result

    #Remove control characte	rs
    def cleanList(self, str):
        return re.sub('/[\x00-\x09\x0B\x0C\x0E-\x1F\x7F]/', '', str)
