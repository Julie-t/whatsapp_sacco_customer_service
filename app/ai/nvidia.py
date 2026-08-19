from app.ai.providers.nvidia import NVIDIAProvider


class LLM:
    def __init__(self, provider: NVIDIAProvider | None = None):
        self.provider = provider or NVIDIAProvider()

    async def generate(self, messages: list[dict]) -> str:
        return await self.provider.generate(messages)
