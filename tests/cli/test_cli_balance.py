import random
import re

import pytest

from communex.key import is_ss58_address
from tests.conftest import InvokeCli
from tests.str_utils import clean

TEST_KEY_ALIAS = "dev01"
TEST_SS58_ADDRESS = "5EA6Dd3vejQco2FZomoAQgxacsTp7ZPFuR25TwxTiUKbkep1"

unit_options = ["default", "joule", "j", "nano", "n"]

joule_pattern = r'\d+\.\d+ J'
nano_pattern = r'\d+'

balance_pattern = {
    "default": joule_pattern,
    "joule": joule_pattern,
    "j": joule_pattern,
    "nano":nano_pattern,
    "n": nano_pattern,
}

def test_cli_balance_all_balance_slow(invoke_cli: InvokeCli):
    for key in [TEST_KEY_ALIAS, TEST_SS58_ADDRESS]:
        cmd = ["balance", "all-balance", key]
        
        unit = random.choice(unit_options)
        
        if unit != "default":
            cmd += ["--unit", unit]
        
        result = invoke_cli(cmd)
        
        assert result.exit_code == 0
        
        assert re.match(f"^{balance_pattern[unit]}\\n$", result.stdout)
        


def test_cli_balance_free_balance_slow(invoke_cli: InvokeCli):
    for key in [TEST_KEY_ALIAS, TEST_SS58_ADDRESS]:
        cmd = ["balance", "free-balance", key]
        
        unit = random.choice(unit_options)
        
        if unit != "default":
            cmd += ["--unit", unit]
        
        result = invoke_cli(cmd)
        
        assert result.exit_code == 0
        
        assert re.match(f"^{balance_pattern[unit]}\\n$", result.stdout)
    


def test_cli_balance_get_staked_slow(invoke_cli: InvokeCli):
    for key in [TEST_KEY_ALIAS, TEST_SS58_ADDRESS]:
        cmd = ["balance", "get-staked", key]
        
        unit = random.choice(unit_options)
        
        if unit != "default":
            cmd += ["--unit", unit]
        
        result = invoke_cli(cmd)
        
        assert result.exit_code == 0
        
        assert re.match(f"^{balance_pattern[unit]}\\n$", result.stdout)


def test_cli_balance_show_slow(invoke_cli: InvokeCli):
    for key in [TEST_KEY_ALIAS, TEST_SS58_ADDRESS]:
        cmd = ["balance", "show", key]
        
        unit = random.choice(unit_options)
        if unit != "default":
                cmd += ["--unit", unit]
                
        result = invoke_cli(cmd)
        
        assert result.exit_code == 0
        
        output  = clean(result.stdout)
        
        
        ss58_key = re.match(r"Balances of key (\w+)", output).group(1) # type: ignore
        
        assert is_ss58_address(ss58_key)
        
        assert re.search(f"Free: {balance_pattern[unit]}", output)
        assert re.search(f"Staked: {balance_pattern[unit]}", output)
        assert re.search(f"Total: {balance_pattern[unit]}", output)
    
    

def test_cli_balance_staked_balance_slow(invoke_cli: InvokeCli):
    for key in [TEST_KEY_ALIAS, TEST_SS58_ADDRESS]:
        cmd = ["balance", "staked-balance", key]
        
        unit = random.choice(unit_options)
        
        if unit != "default":
            cmd += ["--unit", unit]
        
        result = invoke_cli(cmd)
        
        assert result.exit_code == 0
        
        assert re.match(f"^{balance_pattern[unit]}\\n$", result.stdout)
    

def test_cli_balance_stake(invoke_cli: InvokeCli):
    pytest.skip("Not implemented")


def test_cli_balance_transfer(invoke_cli: InvokeCli):
    pytest.skip("Not implemented")


def test_cli_balance_transfer_stake(invoke_cli: InvokeCli):
    pytest.skip("Not implemented")


def test_cli_balance_unstake(invoke_cli: InvokeCli):
    pytest.skip("Not implemented")
