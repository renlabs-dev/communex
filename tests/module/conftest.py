from contextlib import contextmanager
from threading import Thread
from time import sleep

import pytest
import uvicorn
from substrateinterface import Keypair

from communex.key import generate_keypair
from communex.module import Module, endpoint
from communex.module.client import ModuleClient
from communex.module.server import ModuleServer
from tests.key_config import TEST_FAKE_MNEM_DO_NOT_USE_THIS

TEST_HOST = "127.0.0.1"
TEST_PORT = 5555


def random_keypair():
    return Keypair.create_from_mnemonic(Keypair.generate_mnemonic())


class SomeModule(Module):
    @endpoint
    def prompt(self, msg: str):
        return {"output": f"An answer example for the prompt \"{msg}\""}

    @endpoint
    def prompt_slow(self, msg: str):
        sleep(2)
        return {"output": f"An slow answer for the prompt \"{msg}\""}

class ThreadServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass

    @contextmanager
    def run_in_thread(self):
        thread = Thread(target=self.run)
        thread.start()
        try:
            while not self.started:
                sleep(1e-3)
            yield
        finally:
            self.should_exit = True
            thread.join()


@pytest.fixture(scope="module")
def server_keypair() -> Keypair: 
    keypair = Keypair.create_from_mnemonic(TEST_FAKE_MNEM_DO_NOT_USE_THIS)
    return keypair


@pytest.fixture(scope="module")
def some_module_server(server_keypair: Keypair):
    a_module = SomeModule()
    server = ModuleServer(a_module, server_keypair, subnets_whitelist=None)
    return server


@pytest.fixture(scope="module")
def serve(some_module_server: ModuleServer):
    config = uvicorn.Config(host=TEST_HOST, port=TEST_PORT, log_level="info", app=some_module_server.get_fastapi_app())

    server = ThreadServer(config=config)
    with server.run_in_thread():
        print("server started")
        yield
    print("server stopped")


@pytest.fixture(scope="module")
def client_keypair() -> Keypair: 
    keypair = generate_keypair()
    return keypair


@pytest.fixture()
def client(client_keypair: Keypair) -> ModuleClient:
    client = ModuleClient(host=TEST_HOST, port=TEST_PORT, key=client_keypair)

    return client


# as we want to run async test, we need to mark the test with @pytest.mark.anyio, and define the anyio_backend fixture with the backend we want to use.
@pytest.fixture
def anyio_backend():
    return 'asyncio'
