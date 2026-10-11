"""Provider client implementations for ai_core.

Concrete ``LLMClient`` protocol implementations live here. No domain
may import these directly — domains access models exclusively through
``ai_core.LLMClientFactory`` (`docs/09_Migration_Analysis.md` §3.3).
"""

from app.ai_core.providers.openai import OpenAIProvider, ProviderError

__all__ = ["OpenAIProvider", "ProviderError"]
