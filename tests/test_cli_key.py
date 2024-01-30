from typer.testing import CliRunner

import re
from pathlib import Path
import pytest

from communex.cli import app
from communex.key import is_ss58_address


runner = CliRunner()

TEST_TEMPORARY_KEY = "warn_temporary_key_983"

TEST_FAKE_MNEM_DO_NOT_USE_THIS = "spy odor tomato foam supreme double vanish minute quarter anxiety wagon hundred"



def delete_temporary_key():
    """ WARNING: this function deletes the key from the disk. USE WITH CAUTION."""

    path = Path(Path.home(), ".commune", "key", TEST_TEMPORARY_KEY+".json")
    if path.exists():
        path.unlink()


# remove all weird non-alphanumeric characters, sucha as table borders
clean_pattern = re.compile("[^a-zA-Z0-9_\\s'\"-]", re.UNICODE)


def clean(text: str) -> str:
    """ removes extra spaces and weird non-alphanumeric characters from a string."""
    text = re.sub(clean_pattern, '', text)

    return " ".join(text.split())


@pytest.fixture()
def temporary_key():
    try:
        result = runner.invoke(app, ["key", "create", TEST_TEMPORARY_KEY])
        
        _, address, _, name, _ = result.stdout.split("'")
        
        yield address, name, result
    finally:
        delete_temporary_key()


@pytest.fixture()
def temporary_key_from_mnemonic():
    try:
        result = runner.invoke(app, ["key", "save", TEST_TEMPORARY_KEY, TEST_FAKE_MNEM_DO_NOT_USE_THIS])
        
        print(result.stdout)
        
        _, address, _, name, _ = result.stdout.split("`")
        
        yield address, name, result
    finally:
        delete_temporary_key()


def test_cli_key_create(temporary_key):
    key, name, result = temporary_key
    
    assert result.exit_code == 0
    
    assert "Generated key with public address" in result.stdout
    assert f"Key successfully stored with name '{TEST_TEMPORARY_KEY}'." in result.stdout
    
    assert is_ss58_address(key)
    assert name == TEST_TEMPORARY_KEY


def test_cli_key_balances_slow(temporary_key):
    _, key_name, _ = temporary_key
    
    result = runner.invoke(app, ["key", "balances"], color=False)
    
    assert result.exit_code == 0

    stdout = clean(result.stdout)
    
    assert clean("┃ key         ┃ free  ┃ staked ┃ all   ┃") in stdout
    assert clean(f"│ {key_name} │ 0.0 J │ 0.0 J  │ 0.0 J │") in stdout
    

def test_cli_key_list(temporary_key):
    address, name, _ = temporary_key
    
    result = runner.invoke(app, ["key", "list"], color=False)
    
    assert result.exit_code == 0
    
    stdout = clean(result.stdout)
    
    assert clean("┃ Key     ┃ Address   ┃") in stdout
    assert clean(f"│ {name} │ {address}     │") in stdout


def test_cli_key_save():
    try:
        result = runner.invoke(app, ["key", "save", TEST_TEMPORARY_KEY, TEST_FAKE_MNEM_DO_NOT_USE_THIS])
        
        assert result.exit_code == 0

        assert "Loaded key with public address " in result.stdout
        assert "`5EA6Dd3vejQco2FZomoAQgxacsTp7ZPFuR25TwxTiUKbkep1`." in result.stdout
        assert f"Key stored with name `{TEST_TEMPORARY_KEY}` successfully." in result.stdout
    finally:
        delete_temporary_key()


def test_cli_key_show(temporary_key_from_mnemonic):
    address, name, _ = temporary_key_from_mnemonic
    
    result = runner.invoke(app, ["key", "show", name])
    
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


def test_cli_key_show_private_option(temporary_key_from_mnemonic):
    address, name, _ = temporary_key_from_mnemonic
    
    result = runner.invoke(app, ["key", "show", name, "--show-private"], env={"COLUMNS": "200"})
    
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
def test_cli_key_stakefrom():
    pass


# TODO
def test_cli_key_staketo():
    pass


# TODO
def test_cli_key_total_balance():
    pass


# TODO
def test_cli_key_total_free_balance():
    pass


# TODO
def test_cli_key_total_staked_balance():
    pass
