from openai import OpenAI
from fastapi import HTTPException
from enum import Enum
import json

from ..module import Module, endpoint, ModuleServer


class OpenAIModels(str, Enum):
    three = "gpt-3.5-turbo"


class OpenAIModule(Module):
    def __init__(self) -> None:
        super().__init__()
        self.client = OpenAI()


    @endpoint
    def prompt(self, text: str, model: OpenAIModels):
        response = self.client.chat.completions.create(
            model=model,
            response_format = {"type": "json_object"},
            messages= [
                {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                {"role": "user", "content": text}
            ]
        )
        answers: list[dict[str, str]] = []
        for msg in response.choices:
            finish_reason = msg.finish_reason
            if finish_reason != "stop":
                raise HTTPException(418, finish_reason)
            content = msg.message.content
            if content:
                answers.append(json.loads(content))

        return {"Answer": answers}



if __name__ == "__main__":
    import uvicorn

    model = OpenAIModule()
    model_server = ModuleServer(model)
    app = model_server.get_fastapi_app()

    uvicorn.run(app, host="127.0.0.1", port=8000) #type: ignore
