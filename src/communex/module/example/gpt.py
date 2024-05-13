import json
from enum import Enum
from os import getenv

from fastapi import HTTPException
from openai import OpenAI

from communex.module.module import Module, endpoint
from communex.module.server import ModuleServer

OPENAI_API_KEY = getenv("OPENAI_API_KEY")


class OpenAIModels(str, Enum):
    three = "gpt-3.5-turbo"


class OpenAIModule(Module):
    def __init__(self) -> None:
        super().__init__()
        self.client = OpenAI(api_key=OPENAI_API_KEY)  #  type: ignore

    @endpoint
    def prompt(self, text: str, model: OpenAIModels):
        response = self.client.chat.completions.create(  # type: ignore
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system",
                    "content": "You are a helpful assistant designed to output JSON."},
                {"role": "user", "content": text},
            ],
        )
        answers: list[dict[str, str]] = []
        for msg in response.choices:  # type: ignore
            finish_reason = msg.finish_reason  # type: ignore
            if finish_reason != "stop":
                raise HTTPException(418, finish_reason)
            content = msg.message.content  # type: ignore
            if content:
                answers.append(json.loads(content))  # type: ignore

        return {"Answer": answers}


if __name__ == "__main__":
    import uvicorn

    from communex.compat.key import classic_load_key

    model = OpenAIModule()
    key = classic_load_key("test")
    model_server = ModuleServer(model, key)
    app = model_server.get_fastapi_app()

    uvicorn.run(app, host="127.0.0.1", port=8000)
