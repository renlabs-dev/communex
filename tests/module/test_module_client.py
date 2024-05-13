from re import escape

import pytest
from substrateinterface import Keypair

from communex.errors import NetworkTimeoutError
from communex.key import check_ss58_address, generate_keypair
from communex.module.client import ModuleClient
from tests.module.conftest import TEST_HOST, TEST_PORT


def test_client_host_port(serve, client: ModuleClient):
    assert client.host == TEST_HOST
    assert client.port == TEST_PORT


def test_client_key(serve, client: ModuleClient, client_keypair):
    assert client.key.public_key == client_keypair.public_key
    assert client.key.private_key == client_keypair.private_key
    assert client.key.mnemonic == client_keypair.mnemonic


@pytest.mark.anyio
async def test_client_send_request_success(serve, server_keypair: Keypair, client: ModuleClient):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    result = await client.call("prompt", server_ss58_address, {"msg": "all good?"})

    assert "error" not in result

    assert result == {'output': 'An answer example for the prompt "all good?"'}


@pytest.mark.anyio
async def test_client_send_request_fail_wrong_address(serve, client: ModuleClient):
    wrong_ss58_address = check_ss58_address(generate_keypair().ss58_address)

    with pytest.raises(Exception) as exception_info:   
        _ = await client.call("prompt", wrong_ss58_address, {"msg": "all good?"})

    assert exception_info.match("Unexpected status code: 401, response: {'error': {'code': 401, 'message': 'Wrong target_key in body'}}")


@pytest.mark.anyio
async def test_client_send_request_fail_fn_does_not_exist(serve, server_keypair: Keypair, client: ModuleClient):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)

    with pytest.raises(Exception) as exception_info:   
        _ = await client.call("inexistent_fn_name", server_ss58_address, {"msg": "toc toc?"})

    assert exception_info.match("Unexpected status code: 404, response: {'detail': 'Not Found'}")


@pytest.mark.anyio
async def test_client_send_request_fail_timeout(serve, server_keypair: Keypair, client: ModuleClient):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)

    with pytest.raises(NetworkTimeoutError) as exception_info:   
        _ = await client.call("prompt_slow", server_ss58_address, {"msg": "all slow? :p"}, timeout=1)

    assert exception_info.match(escape("The call took longer than the timeout of 1 second(s)"))
