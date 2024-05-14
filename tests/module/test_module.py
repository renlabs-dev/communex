from communex.module.module import EndpointDefinition, Module, endpoint


class SomeModule(Module):
    @endpoint
    def get_uppercased(self, msg: str):
        return {"msg": msg.upper()}


def test_module_get_endpoints():
    a_module = SomeModule()

    endpoints = a_module.get_endpoints()

    assert "get_uppercased" in endpoints

    assert isinstance(endpoints["get_uppercased"], EndpointDefinition)

    assert callable(endpoints['get_uppercased'].fn)

    assert endpoints['get_uppercased'].fn(a_module, msg="example") == {"msg": "EXAMPLE"}
