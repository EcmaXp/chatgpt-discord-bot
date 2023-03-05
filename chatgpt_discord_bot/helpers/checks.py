""""
Copyright © Krypton 2019-2023 - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized discord bot in Python programming language.

Version: 5.5.0
"""

from typing import Callable, TypeVar

from discord.ext import commands

from chatgpt_discord_bot.exceptions import UserBlacklisted, UserNotOwner
from chatgpt_discord_bot.helpers import db_manager

T = TypeVar("T")


async def is_owner(context: commands.Context) -> bool:
    """
    This is a custom check to see if the user executing the command is an owner of the bot.
    """
    if context.author.id not in context.bot.config["owners"]:
        raise UserNotOwner
    return True


async def not_blacklisted(context: commands.Context) -> bool:
    """
    This is a custom check to see if the user executing the command is blacklisted.
    """
    if await db_manager.is_blacklisted(context.author.id):
        raise UserBlacklisted
    return True
