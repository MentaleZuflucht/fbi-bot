import discord
import logging.config
import os
import asyncio
from config import setup_logging, COG_FOLDER_PATH
from discord.ext import commands
from database import init_database

setup_logging()
bot_logger = logging.getLogger('bot')
bot_logger.info('Logging setup complete')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot_logger.info('Intents setup complete')

bot = commands.Bot(command_prefix='!', intents=intents)


async def main():
    """
    Loads all cog extensions and starts the Discord bot.
    """
    try:
        init_database()
        bot_logger.info('Database initialized successfully')
    except Exception as e:
        bot_logger.error(f'Failed to initialize database: {e}')
        return

    # Load all cog extensions
    for filename in os.listdir(COG_FOLDER_PATH):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')

    await bot.start(os.getenv('TOKEN'))

asyncio.run(main())
