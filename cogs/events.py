from discord.ext import commands
import logging

events_logger = logging.getLogger('cogs.events')


class Events(commands.Cog):
    """
    A cog that handles various Discord events and bot interactions.

    This cog manages events such as bot startup, member joins, and message monitoring.
    It also handles word tracking and user management functionality.

    Attributes:
        bot: The Discord bot instance
        config: The bot configuration settings
    """
    def __init__(self, bot):
        """
        Initialize the Events cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        events_logger.info('Events cog initialized')

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Event handler for when the bot is ready.
        """
        events_logger.info('Bot is ready')


async def setup(bot):
    """
    Set up the Events cog.

    Args:
        bot: The Discord bot instance to add this cog to
    """
    await bot.add_cog(Events(bot))
    events_logger.info('Events cog loaded')
