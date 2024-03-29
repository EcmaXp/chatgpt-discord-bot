""""
ChatGPT Discord Bot
Apache License 2.0
Copyright (c) 2023 EcmaXp
"""

from __future__ import annotations

import io
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

__author__ = "EcmaXp <ecmaxp@ecmaxp.kr>"
__version__ = "0.2"

COMPRESS_THRESHOLD_TOKEN = 1024
MAX_TOTAL_TOKEN = 4096
MAX_PROMPT_TOKEN = 8192

class Chat:
    def __init__(self, history: list[dict] = None, context: commands.Context = None):
        self.history = history or []
        self.context = context
        self.last_completion = None
        self.openai = openai.AsyncOpenAI(api_key=openai.api_key)
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

    async def completion(self, *, max_tokens: int = MAX_TOTAL_TOKEN):
        max_tokens = min(max(self.get_max_tokens(), 0), max_tokens)
        if not max_tokens:
            raise ValueError("All tokens are used up, start a new chat please.")

        completion = await self.openai.chat.completions.create(
            model=self.get_model(),
            messages=self.get_messages(),
            max_tokens=max_tokens,
            user=self.user or "",
        )
        return completion

    async def ask(self, text: Optional[str] = None, *, max_tokens: int = MAX_TOTAL_TOKEN):
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
        return MAX_TOTAL_TOKEN - self.get_tokens() - 1

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
            usage = self.last_completion.usage
            print(f"{usage.completion_tokens = }")
            print(f"{usage.prompt_tokens = }")
            print(f"{usage.total_tokens = }")

    async def compress_large_messages(
        self,
        threshold_tokens: int = COMPRESS_THRESHOLD_TOKEN,
        max_prompt_tokens: int = MAX_PROMPT_TOKEN,
    ):
        if self.get_tokens() < max_prompt_tokens:
            return

        model = self.get_model()
        for pos, item in enumerate(self.history[3:-3]):
            if self.get_tokens() < max_prompt_tokens:
                break

            if item["role"] == "system":
                continue
            elif item["tokens"] > threshold_tokens:
                item["content"] = await self.get_summary(item["content"])
                item["tokens"] = get_tokens(model, item["content"])

    @staticmethod
    @alru_cache(maxsize=1024, typed=True)
    async def get_summary(text: str) -> str:
        chat = Chat()
        chat.user = "summary by system"
        model = chat.get_model()
        print(f"Summarizing: {get_tokens(model, text)}")
        summary = await chat.ask("Summarize the following:" + text)
        print(
            f"Summarized: {get_tokens(model, text)} -> {get_tokens(model, summary)}; {chat.last_completion.usage.total_tokens} tokens used."
        )
        return summary


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
        question="The message to send to the model",
    )
    async def chatgpt(
        self, context: commands.Context, *, question: Optional[str] = None
    ):
        if not question and not context.message.reference:
            question = "Hello, world!"

        self.assign_interaction(context, question)

        try:
            chat = await self.build_chat(context, question)
            if chat[-1]["role"] == "system":
                await self.reply(context, "[SYSTEM] System message is set.")
                return

            async with context.typing():
                await self.preprocessing_chat(context, chat)
                answer = await chat.ask()
                await self.reply(context, answer)
                chat.print(context.message)
        except Exception as e:
            self.bot.logger.exception(e)  # noqa
            await self.reply(context, f":warning: **{type(e).__name__}**: {e}")

        await self.update_presence()

    async def preprocessing_chat(self, context: commands.Context, chat: Chat):
        title = f"{context.author} @ {datetime.now().replace(microsecond=0)}"

        before_tokens = chat.get_tokens()
        print(f"{title}: Requesting {before_tokens} tokens")

        await chat.compress_large_messages(
            threshold_tokens=COMPRESS_THRESHOLD_TOKEN,
            max_prompt_tokens=MAX_PROMPT_TOKEN,
        )
        after_tokens = chat.get_tokens()
        discarded_tokens = before_tokens - after_tokens
        if discarded_tokens:
            print(
                f"{title}: Requesting {after_tokens} tokens; discarded {discarded_tokens} tokens"
            )

    async def update_presence(self):
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

    async def reply(self, context: commands.Context, answer: str) -> discord.Message:
        if len(answer) >= 2000:
            lines = []
            for line in answer.splitlines():
                while line:
                    lines.append(line[:80])
                    line = line[80:]

            answer = "\n".join(lines)
            answer_fp = io.BytesIO(answer.encode("utf-8"))
            answer_file = discord.File(answer_fp, "message.txt")
            reply = await context.reply(file=answer_file)
        else:
            reply = await context.reply(answer)

        self.reply_ids[context.message.id].add(reply.id)
        return reply

    def assign_interaction(self, context: commands.Context, question: str):
        if (
            getattr(context.message.type, "value", context.message.type)
            == discord.MessageType.chat_input_command
        ):
            context.message.content = question
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
        elif (
            message.type == discord.MessageType.reply
            and self.bot.user in message.mentions
        ):
            invoked_prefix = ""
        else:
            return ctx

        invoker = target_command
        ctx.invoked_with = invoker
        ctx.prefix = invoked_prefix
        ctx.command = self.bot.get_command(invoker)
        return ctx

    async def build_chat(self, context: commands.Context, question: str) -> Chat:
        model = self.bot.config["openai_chatgpt_model"]  # noqa

        bot_member = context.guild.get_member(context.bot.user.id)
        bot_mention = f"@{bot_member.display_name}"

        messages = []
        for message in await self.fetch_all_messages(context.message, 64):
            role = "assistant" if message.author == self.bot.user else "user"
            if message == context.message:
                text = question
            else:
                text = cast(str, message.clean_content)

            text = removeprefix(text, bot_mention).strip()

            if text.lower().startswith("[system]"):
                if role == "user":
                    role = "system"
                    text = text[len("[system]") :].strip()
                elif role == "assistant":
                    continue
                else:
                    raise ValueError("Unknown role")

            if message.attachments:
                text += "\n\n" + (await self.fetch_attachment(message))
                if get_tokens(model, text) > 1024 * 3:
                    raise ValueError("Attachment too large")

            if role == "system":
                messages.insert(0, {"role": role, "content": text})
            else:
                messages.append({"role": role, "content": text})

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
