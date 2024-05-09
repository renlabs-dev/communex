import pytest
import json
import requests
import datetime
from typing import Any

from tests.module.conftest import TEST_HOST, TEST_PORT, random_keypair

from communex.key import Keypair
from communex.types import Ss58Address
from communex.module.server import ModuleServer
from communex.module._signer import sign, TESTING_MNEMONIC
from communex.key import check_ss58_address


def serialize(data: Any) -> bytes:
    txt = json.dumps(data)
    return txt.encode()


def iso_timestamp_now() -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    iso_now = now.isoformat()
    return iso_now


def create_headers(signature: bytes, my_key: Keypair, timestamp_iso: str):
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature.hex(),
        "X-Key": my_key.public_key.hex(),
        "X-Crypto": str(my_key.crypto_type),
        "X-Timestamp": timestamp_iso,
    }
    return headers


def create_request_data(
    my_key: Keypair,
    target_key: Ss58Address,
    params: dict
) -> tuple[bytes, bytes]:
    timestamp_iso = iso_timestamp_now()
    
    params["target_key"] = target_key

    request_data = {
        "params": params,
    }

    serialized_data = serialize(request_data)
    request_data["timestamp"] = timestamp_iso
    serialized_stamped_data = serialize(request_data)
    signature = sign(my_key, serialized_stamped_data)
    
    headers = create_headers(signature, my_key, timestamp_iso)
    
    return serialized_data, headers


def create_method_endpoint(host: str, port: str, method_name: str) -> str:
    return f"http://{host}:{port}/method/{method_name}"


def module_endpoint(method_name: str) -> str:
    return create_method_endpoint(TEST_HOST, TEST_PORT, method_name)


@pytest.fixture()
def my_keypair():
    return Keypair.create_from_mnemonic(TESTING_MNEMONIC)


def test_module_server_call_success(serve, server_keypair: Keypair, my_keypair: Keypair):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    
    method_endpoint = module_endpoint("prompt")
    params = {
        "msg": "all good?"
    }
    
    serialized_data, headers = create_request_data(my_keypair, target_key=server_ss58_address, params=params)
    
    result = requests.post(method_endpoint, headers=headers, json=json.loads(serialized_data))
    
    # assert result.status_code == 100
    assert result.status_code == 200
    assert result.json() == {'output': 'An answer example for the prompt "all good?"'}
    

def test_module_server_call_invalid_fn(serve, server_keypair: Keypair, my_keypair: Keypair):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    
    method_endpoint = module_endpoint("a_non_existent_endpoint")
    params = {
        "msg": "all good?"
    }
    
    serialized_data, headers = create_request_data(my_keypair, target_key=server_ss58_address, params=params)
    
    result = requests.post(method_endpoint, headers=headers, json=json.loads(serialized_data))
    
    # assert result.status_code == 100
    assert result.status_code == 404
    assert result.json() == {'detail': 'Not Found'}
    

def test_module_server_call_blacklisted(serve, server_keypair: Keypair, my_keypair: Keypair, some_module_server: ModuleServer):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    some_module_server.add_to_blacklist(my_keypair.ss58_address)
    
    method_endpoint = module_endpoint("prompt")
    params = {
        "msg": "all good?"
    }
    
    serialized_data, headers = create_request_data(my_keypair, target_key=server_ss58_address, params=params)
    
    result = requests.post(method_endpoint, headers=headers, json=json.loads(serialized_data))
    
    # assert result.status_code == 100
    assert result.status_code == 403
    assert result.json() == {"error": {"code": 403, "message": "You are blacklisted"}}




def test_module_server_call_blacklisted(serve, server_keypair: Keypair, some_module_server: ModuleServer):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    
    my_keypair = random_keypair()
    some_module_server.add_to_blacklist(my_keypair.ss58_address)
    
    method_endpoint = module_endpoint("prompt")
    params = {
        "msg": "all good?"
    }
    
    serialized_data, headers = create_request_data(my_keypair, target_key=server_ss58_address, params=params)
    
    result = requests.post(method_endpoint, headers=headers, json=json.loads(serialized_data))
    
    assert result.status_code == 403
    assert result.json() == {"error": {"code": 403, "message": "You are blacklisted"}}


def test_module_server_call_whitelisted(serve, server_keypair: Keypair, my_keypair: Keypair, some_module_server: ModuleServer):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    
    my_keypair = random_keypair()
    some_module_server.add_to_whitelist(my_keypair.ss58_address)
    
    method_endpoint = module_endpoint("prompt")
    params = {
        "msg": "success?"
    }
    
    serialized_data, headers = create_request_data(my_keypair, target_key=server_ss58_address, params=params)
    
    result = requests.post(method_endpoint, headers=headers, json=json.loads(serialized_data))
    
    assert result.status_code == 200
    assert result.json() == {'output': 'An answer example for the prompt "success?"'}
    

def test_module_server_call_not_whitelisted(serve, server_keypair: Keypair, my_keypair: Keypair, some_module_server: ModuleServer):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    
    my_keypair = random_keypair()
    some_module_server.add_to_whitelist("some other address")
    
    method_endpoint = module_endpoint("prompt")
    params = {
        "msg": "all good?"
    }
    
    serialized_data, headers = create_request_data(my_keypair, target_key=server_ss58_address, params=params)
    
    result = requests.post(method_endpoint, headers=headers, json=json.loads(serialized_data))
    
    assert result.status_code == 403
    assert result.json() == {"error": {"code": 403, "message": "You are not whitelisted"}}


def test_module_server_call_blacklist_overcomes_whitelist(serve, server_keypair: Keypair, my_keypair: Keypair, some_module_server: ModuleServer):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    
    my_keypair = random_keypair()
    some_module_server.add_to_blacklist(my_keypair.ss58_address)
    some_module_server.add_to_whitelist(my_keypair.ss58_address)
    
    method_endpoint = module_endpoint("prompt")
    params = {
        "msg": "all good?"
    }
    
    serialized_data, headers = create_request_data(my_keypair, target_key=server_ss58_address, params=params)
    
    result = requests.post(method_endpoint, headers=headers, json=json.loads(serialized_data))
    
    assert result.status_code == 403
    assert result.json() == {"error": {"code": 403, "message": "You are blacklisted"}}
