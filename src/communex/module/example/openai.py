from communex.module import Module, endpoint

# prompt: str = 'sup?',
# model: str = 'gpt-3.5-turbo',
# presence_penalty: float = 0.0,
# frequency_penalty: float = 0.0,
# temperature: float = 0.9,
# max_tokens: int = 100,def endpoint(fn: Any):
# top_p: float = 1,
# choice_idx: int = 0,
# api_key: str = None,
# retry: bool = True,
# role: str = 'user',
# history: list = None,


class OpenAI(Module):
    @endpoint
    def generate(self, prompt: str, model: str = 'gpt-3.5-turbo'):
        print(f"Answering: `{prompt}` with model `{model}`")
