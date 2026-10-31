"""Provider 注册表：按平台 key 找到对应适配器。"""
from __future__ import annotations

from .base import Provider
from .chatgpt_plus_provider import ChatGPTPlusProvider
from .codex_provider import CodexProvider
from .doubao_provider import DoubaoProvider
from .kimi_provider import KimiProvider
from .openai_provider import OpenAIProvider
from .volc_provider import VolcProvider
from .zhipu_member_provider import ZhipuMemberProvider
from .zhipu_provider import ZhipuProvider

PROVIDERS: dict[str, type[Provider]] = {
    "openai": OpenAIProvider,
    "chatgpt_plus": ChatGPTPlusProvider,
    "codex": CodexProvider,
    "doubao": DoubaoProvider,
    "zhipu": ZhipuProvider,
    "zhipu_member": ZhipuMemberProvider,
    "kimi": KimiProvider,
    "volc": VolcProvider,
}

__all__ = ["PROVIDERS", "Provider"]
