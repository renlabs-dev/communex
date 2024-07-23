import json

import pytest
import requests
from tests.module.conftest import TEST_HOST, TEST_PORT, random_keypair

from communex.key import Keypair, check_ss58_address
from communex.module._protocol import (create_method_endpoint,
                                       create_request_data)
from communex.module._signer import TESTING_MNEMONIC
from communex.module.server import ModuleServer


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
    
    assert result.status_code == 404
    assert result.json() == {'detail': 'Not Found'}


def test_module_server_call_blacklisted(serve, server_keypair: Keypair, some_module_server: ModuleServer):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    
    my_keypair = random_keypair()
    blacklisted = check_ss58_address(my_keypair.ss58_address)
    some_module_server.add_to_blacklist(blacklisted)
    
    method_endpoint = module_endpoint("prompt")
    params = {
        "msg": "all good?"
    }
    
    serialized_data, headers = create_request_data(my_keypair, target_key=server_ss58_address, params=params)
    
    result = requests.post(method_endpoint, headers=headers, json=json.loads(serialized_data))
    
    assert result.status_code == 403
    assert result.json() == {"error": {"code": 403, "message": "You are blacklisted"}}


def test_module_server_call_not_blacklisted(serve, server_keypair: Keypair, some_module_server: ModuleServer):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    
    my_keypair = random_keypair()
    some_module_server.add_to_blacklist("some other address") # type: ignore
    
    method_endpoint = module_endpoint("prompt")
    params = {
        "msg": "all good?"
    }
    
    serialized_data, headers = create_request_data(my_keypair, target_key=server_ss58_address, params=params)
    
    result = requests.post(method_endpoint, headers=headers, json=json.loads(serialized_data))
    
    assert result.status_code == 200
    assert result.json() == {'output': 'An answer example for the prompt "all good?"'}


def test_module_server_call_whitelisted(serve, server_keypair: Keypair, my_keypair: Keypair, some_module_server: ModuleServer):
    server_ss58_address = check_ss58_address(server_keypair.ss58_address)
    
    my_keypair = random_keypair()
    whitelisted = check_ss58_address(my_keypair.ss58_address)
    some_module_server.add_to_whitelist(whitelisted)
    
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
    some_module_server.add_to_whitelist("some other address") # type: ignore
    
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
    ss58 = check_ss58_address(my_keypair.ss58_address)
    some_module_server.add_to_blacklist(ss58)
    some_module_server.add_to_whitelist(ss58)
    
    method_endpoint = module_endpoint("prompt")
    params = {
        "msg": "all good?"
    }
    
    serialized_data, headers = create_request_data(my_keypair, target_key=server_ss58_address, params=params)
    
    result = requests.post(method_endpoint, headers=headers, json=json.loads(serialized_data))
    
    assert result.status_code == 403
    assert result.json() == {"error": {"code": 403, "message": "You are blacklisted"}}
