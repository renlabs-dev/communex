# Module spec stuff

## Input

```txt
# should we allow positional?
params: ["Qual tamanho médio de mafagafo?"] 

params: {"prompt": "Qual tamanho médio de mafagafo?", "model": "gpt-4"}
```

---

```py
def answer(self, prompt: str, model: str = 'gpt-3.5-turbo'):
    ...
```

=== transforms to ===>

```py
class m(BaseModel):
    prompt: str
    model: str = 'gpt-3.5-turbo'
```
