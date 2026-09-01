from app.ai.providers.groq import GroqProvider


class LLM:
    def __init__(self, provider: GroqProvider | None = None):
        self.provider = provider or GroqProvider()

    async def generate(self, messages: list[dict]) -> str:
        return await self.provider.generate(messages)
