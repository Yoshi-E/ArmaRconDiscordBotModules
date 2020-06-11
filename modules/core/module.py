from discord.ext import commands
from discord.ext.commands import has_permissions, CheckFailure
import discord


from modules.core import CoreConfig, CommandChecker
from modules.core.httpServer import server

class Commandconfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


        self.cfg = self.bot.CoreConfig.cfg
        
    @CommandChecker.command(  name='config_reload',
                        brief="reloads the config",
                        description="reloads the config from disk")
    async def config_reload(self, ctx):
        self.cfg.load()
        await ctx.send("Reloaded!")      

    @CommandChecker.command(  name='setpush',
                        brief="Sets the channel the bots sends status updates to",
                        description="Sets the channel the bots sends status updates to")
    async def set_push(self, ctx):
        self.cfg["PUSH_CHANNEL"] = int(ctx.channel.id)
        await ctx.send("Channel set")    
        
def setup(bot):
    bot.add_cog(Commandconfig(bot))
