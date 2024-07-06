import pytest
from tests.conftest import InvokeCli
from tests.key_config import (TEST_FAKE_MNEM_DO_NOT_USE_THIS,
                              TEST_TEMPORARY_KEY, delete_temporary_key)
from tests.str_utils import clean

from communex.key import is_ss58_address


@pytest.fixture()
def temporary_key(invoke_cli: InvokeCli):
    try:
        result = invoke_cli(["key", "create", TEST_TEMPORARY_KEY])
        
        _, address, _, name, _ = result.stdout.split("'")
        
        yield address, name, result
    finally:
        delete_temporary_key()


@pytest.fixture()
def temporary_key_from_mnemonic(invoke_cli: InvokeCli):
    try:
        result = invoke_cli(["key", "regen", TEST_TEMPORARY_KEY, TEST_FAKE_MNEM_DO_NOT_USE_THIS])
        
        print(result.stdout)
        
        _, address, _, name, _ = result.stdout.split("`")
        
        yield address, name, result
    finally:
        delete_temporary_key()



def test_cli_key_create(temporary_key):
    key, name, result = temporary_key
    
    # faiing: query system account
    
    assert result.exception is None
    assert result.exit_code == 0
    
    assert "Generated key with public address" in result.stdout
    assert f"Key successfully stored with name '{TEST_TEMPORARY_KEY}'." in result.stdout
    
    assert is_ss58_address(key)
    assert name == TEST_TEMPORARY_KEY


def test_cli_key_balances_slow(invoke_cli: InvokeCli, temporary_key):
    _, key_name, _ = temporary_key
    
    result = invoke_cli(["key", "balances"])
    
    assert result.exception is None
    assert result.exit_code == 0

    stdout = clean(result.stdout)
    
    assert clean("┃ key         ┃ free  ┃ staked ┃ all   ┃") in stdout
    assert clean(f"│ {key_name} │ 0.0 J │ 0.0 J  │ 0.0 J │") in stdout
    

def test_cli_key_list(invoke_cli: InvokeCli, temporary_key):
    address, name, _ = temporary_key
    
    result = invoke_cli(["key", "list"])
    
    assert result.exit_code == 0
    
    stdout = clean(result.stdout)
    
    assert clean("┃ Key     ┃ Address   ┃") in stdout
    assert clean(f"│ {name} │ {address}     │") in stdout


def test_cli_key_save(invoke_cli: InvokeCli):
    try:
        result = invoke_cli(["key", "regen", TEST_TEMPORARY_KEY, TEST_FAKE_MNEM_DO_NOT_USE_THIS])
        
        assert result.exit_code == 0

        assert "Loaded mnemonic with public address " in result.stdout
        assert "`5EA6Dd3vejQco2FZomoAQgxacsTp7ZPFuR25TwxTiUKbkep1`." in result.stdout
        assert f"Key stored with name `{TEST_TEMPORARY_KEY}` successfully." in result.stdout
    finally:
        delete_temporary_key()


def test_cli_key_show(invoke_cli: InvokeCli, temporary_key_from_mnemonic):
    address, name, _ = temporary_key_from_mnemonic
    
    result = invoke_cli(["key", "show", name])
    
    assert result.exit_code == 0
    
    print(result.stdout)
    
    output = clean(result.stdout)
    
    assert clean("┃ Key           ┃ Value            ┃") in output
    assert clean(f"│ path         │ {name}           │") in output
    assert clean("│ mnemonic      │ [SENSITIVE-MODE] │") in output
    assert clean("│ public_key    │ 5c93f7facb586801be42e9450646bc3183ac14d62b00c7036837d4d366c0… │") in output
    assert clean("│ private_key   │ [SENSITIVE-MODE] │") in output
    assert clean(f"│ ss58_address │ {address}        │") in output
    assert clean("│ seed_hex      │ [SENSITIVE-MODE] │") in output
    assert clean("│ ss58_format   │ 42               │") in output
    assert clean("│ crypto_type   │ 1                │") in output
    assert clean("│ derive_path   │ None             │") in output


def test_cli_key_show_private_option(invoke_cli: InvokeCli, temporary_key_from_mnemonic):
    address, name, _ = temporary_key_from_mnemonic
    
    result = invoke_cli(["key", "show", name, "--show-private"])
    
    assert result.exit_code == 0
    
    print(result.stdout)
    
    output = clean(result.stdout)
    
    assert clean("┃ Key           ┃ Value                                                            ┃") in output
    assert clean(f"│ path         │ {name}                                                           │") in output
    assert clean(f"│ mnemonic     │ {TEST_FAKE_MNEM_DO_NOT_USE_THIS}                                 │") in output
    assert clean("│ public_key    │ 5c93f7facb586801be42e9450646bc3183ac14d62b00c7036837d4d366c0…    │") in output
    assert clean("│ private_key   │ faf234e8bde612045e892a3312f5d03335805d7da2d617cec25947f47aa55d0be969db358ba3b741932379cce96e247849b70b0bc6968503fed7de28597b5483 │") in output
    assert clean(f"│ ss58_address │ {address}                                                        │") in output
    assert clean("│ seed_hex      │ 890f730118632739aea624e1bebd76d557f6cd7b1779fa2507902d1a65265964 │") in output
    assert clean("│ ss58_format   │ 42                                                               │") in output
    assert clean("│ crypto_type   │ 1                                                                │") in output
    assert clean("│ derive_path   │ None                                                             │") in output


# TODO
def test_cli_key_stakefrom(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")


# TODO
def test_cli_key_staketo(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")


# TODO
def test_cli_key_total_balance(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")


# TODO
def test_cli_key_total_free_balance(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")


# TODO
def test_cli_key_total_staked_balance(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")
