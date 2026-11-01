"""Provider 注册表：按平台 key 找到对应适配器。"""
from __future__ import annotations

from .gemini_provider import GeminiProvider
from .dmxapi_provider import DMXAPIProvider
from .base import Provider
from .codex_provider import CodexProvider
from .deepseek_provider import DeepSeekProvider
from .doubao_provider import DoubaoProvider
from .kimi_provider import KimiProvider
from .openai_provider import OpenAIProvider
from .volc_provider import VolcProvider
from .zhipu_member_provider import ZhipuMemberProvider
from .zhipu_provider import ZhipuProvider

PROVIDERS: dict[str, type[Provider]] = {
    "openai": OpenAIProvider,
    "dmxapi": DMXAPIProvider,
    "codex": CodexProvider,
    "gemini": GeminiProvider,
    "doubao": DoubaoProvider,
    "zhipu": ZhipuProvider,
    "zhipu_member": ZhipuMemberProvider,
    "kimi": KimiProvider,
    "deepseek": DeepSeekProvider,
    "volc": VolcProvider,
}

__all__ = ["PROVIDERS", "Provider"]
