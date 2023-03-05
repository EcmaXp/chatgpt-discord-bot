from __future__ import annotations

from functools import lru_cache

import tiktoken


@lru_cache(maxsize=256, typed=True)
def get_tokens(model: str, text: str) -> int:
    chatgpt_model_encoding = tiktoken.encoding_for_model(model)
    return len(chatgpt_model_encoding.encode(text))
