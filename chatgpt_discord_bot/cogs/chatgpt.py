from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from typing import List, Optional, cast

import discord
import openai
from async_lru import alru_cache
from discord import app_commands
from discord.ext import commands
from discord.ext.commands.view import StringView

from chatgpt_discord_bot import config
from chatgpt_discord_bot.helpers import checks
from chatgpt_discord_bot.helpers.openai import get_tokens
from chatgpt_discord_bot.helpers.utils import removeprefix


class Chat:
    def __init__(self, history: list[dict] = None, context: commands.Context = None):
        self.history = history or []
        self.context = context
        self.last_completion = None
        self.config = context.bot.config if context else config
        self.user = (
            sha256(str(context.author.id).encode()).hexdigest() if context else None
        )

        for item in self.history:
            if item.get("tokens") is None:
                item["tokens"] = get_tokens(self.get_model(), item["content"])

    def __bool__(self):
        return bool(self.history)

    def __len__(self):
        return len(self.history)

    def __getitem__(self, index):
        return self.history[index]

    def __iter__(self):
        return iter(self.history)

    async def completion(self, *, max_tokens: int = 4096):
        max_tokens = min(max(self.get_max_tokens(), 0), max_tokens)
        if not max_tokens:
            raise ValueError("All tokens are used up, start a new chat please.")

        completion = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=self.get_messages(),
            max_tokens=max_tokens,
            user=self.user or "",
        )
        return completion

    async def ask(self, text: Optional[str] = None, *, max_tokens: int = 4096):
        if text is not None:
            self.add_message("user", text)
        completion = await self.completion(max_tokens=max_tokens)
        response = completion.choices[0].message.content.strip()
        if self.config:
            self.config["chatgpt_tokens_count"] += completion.usage.total_tokens
        self.last_completion = completion
        self.add_message("assistant", response)
        return response

    def add_message(self, role: str, content: str):
        self.history.append(
            {
                "role": role,
                "content": content,
                "tokens": get_tokens(self.get_model(), content),
            }
        )

    def get_model(self) -> str:
        return self.config["openai_chatgpt_model"]

    def get_messages(self) -> list[dict]:
        return [
            {"role": item["role"], "content": item["content"]} for item in self.history
        ]

    def get_max_tokens(self) -> int:
        return 4096 - self.get_tokens() - 1

    def get_tokens(self) -> int:
        return 2 + sum(item["tokens"] + 5 for item in self.history)

    def copy(self):
        return Chat(deepcopy(self.history), self.context)

    def print(self, message: discord.Message | None = None):
        print()
        if getattr(message, "jump_url", None):
            print("#", message.jump_url)
        print(f"{message.author} @ {datetime.now().replace(microsecond=0)}:")
        for no, item in enumerate(self.history):
            print(f"{item['role']}: {item['content']}")

        if self.last_completion is not None:
            for key, value in self.last_completion.usage.items():
                print(f"{key}: {value}")


class ChatGPT(commands.Cog, name="chatgpt"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reply_ids: dict[int, set] = defaultdict(set)
        self.interactions: dict[int, commands.Context] = {}
        self.bot.config.setdefault("chatgpt_tokens_count", 0)  # noqa

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
        if not text and not context.message.reference:
            text = "Hello, world!"

        self.assign_interaction(context, text)

        chat = await self.build_chat(context)
        async with context.typing():
            answer = await chat.ask()
            reply = await context.reply(answer)
            chat.print(context.message)

        self.reply_ids[context.message.id].add(reply.id)

        chatgpt_tokens_count = self.bot.config["chatgpt_tokens_count"]  # noqa
        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name=(
                    f"{chatgpt_tokens_count:,} tokens"
                    f" = {chatgpt_tokens_count / 1000 * 0.002:,.2f} $"
                ),
            )
        )

    def assign_interaction(self, context: commands.Context, text: str):
        if (
            getattr(context.message.type, "value", context.message.type)
            == discord.MessageType.chat_input_command
        ):
            context.message.content = text
            self.interactions[context.message.id] = context

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.process_commands_for_mention_or_reply(message)

    @commands.Cog.listener()
    async def on_message_edit(
        self,
        before_message: discord.Message,
        message: discord.Message,
    ):
        if message.id in self.reply_ids:
            reply_ids = self.reply_ids.pop(message.id, None)
            if reply_ids:
                await message.channel.delete_messages(
                    [
                        message.channel.get_partial_message(reply_id)
                        for reply_id in reply_ids
                    ]
                )

        await self.on_message(message)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.id in self.reply_ids:
            reply_ids = self.reply_ids.pop(message.id, None)
            if reply_ids:
                await message.channel.delete_messages(
                    [
                        message.channel.get_partial_message(reply_id)
                        for reply_id in reply_ids
                    ]
                )

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

    async def build_chat(self, context: commands.Context) -> Chat:
        model = self.bot.config["openai_chatgpt_model"]  # noqa

        bot_member = context.guild.get_member(context.bot.user.id)
        bot_mention = f"@{bot_member.display_name}"

        messages = []
        for message in await self.fetch_all_messages(context.message, 64):
            text = cast(str, message.clean_content)

            if message.attachments:
                text += "\n\n" + (await self.fetch_attachment(message))
                if get_tokens(model, text) > 1024 * 3:
                    raise ValueError("Attachment too large")

            messages.append(
                {
                    "role": "assistant" if message.author == self.bot.user else "user",
                    "content": removeprefix(text, bot_mention).strip(),
                }
            )

        return Chat(messages, context)

    async def fetch_all_messages(
        self,
        message: discord.Message,
        limit: int,
    ) -> List[discord.Message]:
        messages = []
        for i in range(limit):
            messages.append(message)
            if message.reference:
                message = await self.fetch_reference_message(message)
            elif message.interaction:
                interaction = self.interactions.get(message.interaction.id)
                if interaction is None:
                    break

                message = interaction.message  # noqa
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

    @alru_cache(maxsize=64, typed=True, ttl=3600)
    async def fetch_attachment(self, message: discord.Message) -> str:
        if len(message.attachments) > 1:
            raise ValueError("Too many attachments")

        for attachment in message.attachments:
            if attachment.size > 1024 * 64:
                raise ValueError("Attachment too large")
            elif not attachment.filename.endswith((".txt", ".py")):
                raise ValueError("Attachment is not text")

            content = await attachment.read()
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                raise ValueError("Attachment is not text (utf-8)")


async def setup(bot):
    await bot.add_cog(ChatGPT(bot))
