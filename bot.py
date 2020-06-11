import discord
import traceback
from discord.ext import commands
from modules.core import utils
import time
import subprocess
import inspect
# Make bot join server:
# https://discordapp.com/oauth2/authorize?client_id=xxxxxx&scope=bot
# API Reference
#https://discordpy.readthedocs.io/en/rewrite/ext/commands/api.html#event-reference

#Order of modules is important
#Partent modules have to be loaded first
#modules = ["errorhandle","core", "rcon", "rcon_database"]
modules = ["errorhandle","core", "rcon", "rcon_ban_msg", "rcon_ingamge_cmd", "rcon_database", "jmw"]

bot = commands.Bot(command_prefix="!", pm_help=True)
bot.CoreConfig = utils.CoreConfig(bot)
 
def load_modules():
    for extension in modules:
        try:
            bot.load_extension("modules."+extension+".module")
        except (discord.ClientException, ModuleNotFoundError):
            print('Failed to load extension: '+extension)
            traceback.print_exc()

    #We are using a custom wrapper for the discord.ext.commands
    #In the process the commands are losing information about the parameters
    #We are setting the parameters from cache:
    for cmd in utils.CoreConfig.bot.commands:
        for func in utils.CommandChecker.registered_func:
            if(str(cmd) == str(func.name)):
                signature = inspect.signature(func)
                cmd.params = signature.parameters.copy() 
                break

###################################################################################################
#####                                  Initialization                                          ####
###################################################################################################     


@bot.event
async def on_ready():

    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print(bot.guilds)
    
    print('------------')
    bot.CoreConfig.load_role_permissions()

def main():
    load_modules()

    #checking depencies 
    if("Commandconfig" in bot.cogs.keys()):
        cfg = bot.cogs["Commandconfig"].cfg
    else: 
        sys.exit("Module 'Commandconfig' not loaded, but required")
    try:
        bot.run(cfg["TOKEN"])
    except KeyError:
        print("")
        input("Please configure the bot on the settings page. [ENTER to terminte the bot]")
     

     
if __name__ == '__main__':
    while True:
        main()
        if(hasattr(bot, "restarting") and bot.restarting == True):
            print("Restarting")
            
            time.sleep(1)
            subprocess.Popen("python" + " bot.py", shell=True)
        
            
