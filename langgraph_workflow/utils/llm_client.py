class LLMClient:
    def __init__(self, provider, api_key, endpoint=None, temperature=0.2):
        self.provider = provider
        self.api_key = api_key
        self.endpoint = endpoint
        self.temperature = temperature

    def generate(self, prompt: str) -> dict:
        # 这里只做接口占位，实际应接入OpenAI/Anthropic/Gemini等API
        # 返回格式: {'steps': '...', 'expected': '...'}
        return {'steps': f'【模拟】{prompt}', 'expected': '【模拟】预期结果'}
