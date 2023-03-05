from __future__ import annotations

from hashlib import sha256
from typing import List, Optional

import discord
import openai
import tiktoken
from async_lru import alru_cache
from discord import app_commands
from discord.ext import commands
from discord.ext.commands.view import StringView

from chatgpt_discord_bot.helpers import checks


class ChatGPT(commands.Cog, name="chatgpt"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="chatgpt",
        aliases=["chat", "gpt", "gpt3"],
        description="Talk to a ChatGPT model",
    )
    @commands.check(checks.not_blacklisted)
    @app_commands.describe(
        text="The message to send to the model",
    )
    async def chatgpt(self, context: commands.Context, *, text: Optional[str] = None):
        chatgpt_model = self.bot.config["openai_chatgpt_model"]  # noqa
        chatgpt_model_encoding = tiktoken.encoding_for_model(chatgpt_model)

        if not text and not context.message.reference:
            text = "Hello, world!"

        messages = await self.build_messages(context, text)

        async with context.typing():
            completion = await openai.ChatCompletion.acreate(
                model=chatgpt_model,
                messages=messages,
                user=sha256(str(context.author.id).encode()).hexdigest(),
            )
            answer = completion.choices[0].message.content
            await context.reply(answer)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.process_commands_for_mention_or_reply(message)

    async def process_commands_for_mention_or_reply(self, message: discord.Message):
        # This is a modified version of commands.Bot.process_commands
        if message.author.bot:
            return

        if not self.bot.config["chatgpt_allow_mention"]:  # noqa
            return

        ctx = await self.get_context_for_mention_or_reply(message, self.chatgpt.name)
        await self.bot.invoke(ctx)

    async def get_context_for_mention_or_reply(
        self,
        message: discord.Message,
        target_command: str,
    ) -> Optional[commands.Context]:
        # This is a modified version of commands.Context.from_message
        view = StringView(message.content)
        ctx = commands.Context(prefix=None, view=view, bot=self.bot, message=message)

        prefix = commands.when_mentioned(self.bot, message)
        prefix = tuple(prefix.rstrip() for prefix in prefix)  # strip whitespace
        if message.content.startswith(prefix):
            invoked_prefix = discord.utils.find(view.skip_string, prefix)
        elif message.type == discord.MessageType.reply:
            invoked_prefix = ""
        else:
            return ctx

        invoker = target_command
        ctx.invoked_with = invoker
        ctx.prefix = invoked_prefix
        ctx.command = self.bot.get_command(invoker)
        return ctx

    async def build_messages(self, context: commands.Context, text: str) -> list[dict]:
        bot_member = context.guild.get_member(context.bot.user.id)
        bot_mention = f"@{bot_member.display_name}"

        messages = []
        for history in await self.fetch_all_history(context.message, 64):
            history_text = history.clean_content
            if history == context.message:  # last message
                history_text = text
            elif history_text.startswith(bot_mention):
                history_text = history_text[len(bot_mention) :]

            messages.append(
                {
                    "role": "assistant" if history.author == self.bot.user else "user",
                    "content": history_text.strip(),
                }
            )

        return messages

    async def fetch_all_history(
        self,
        message: discord.Message,
        limit: int,
    ) -> List[discord.Message]:
        messages = []
        for i in range(limit):
            messages.append(message)
            if message.reference:
                message = await self.fetch_reference_message(message)
            else:
                break

        return messages[::-1]

    @alru_cache(maxsize=256, typed=True, ttl=3600)
    async def fetch_reference_message(
        self, message: discord.Message
    ) -> Optional[discord.Message]:
        reference = message.reference
        if reference.cached_message:
            return reference.cached_message
        else:
            return await message.channel.fetch_message(reference.message_id)


async def setup(bot):
    await bot.add_cog(ChatGPT(bot))
