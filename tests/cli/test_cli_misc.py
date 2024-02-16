import re
import random

from tests.conftest import InvokeCli
from tests.str_utils import clean


TEST_KEY_ALIAS = "dev01"
TEST_SS58_ADDRESS = "5EA6Dd3vejQco2FZomoAQgxacsTp7ZPFuR25TwxTiUKbkep1"

unit_options = ["default", "joule", "j", "nano", "n"]



def test_cli_misc_circulating_supply_slow(invoke_cli: InvokeCli):
    joule_pattern = r'^\d+,\d{3},\d{3}\.\d+ J\b'
    nano_pattern = r'\d+'

    balance_pattern = {
        "default": joule_pattern,
        "joule": joule_pattern,
        "j": joule_pattern,
        "nano":nano_pattern,
        "n": nano_pattern,
    }
    
    cmd = ["misc", "circulating-supply"]
    
    unit = random.choice(unit_options)
    if unit != "default":
        cmd += ["--unit", unit]
    
    result = invoke_cli(cmd)
    
    assert result.exception is None
    
    assert result.exit_code == 0
    assert re.match(balance_pattern[unit], result.stdout)


def test_cli_misc_apr_slow(invoke_cli: InvokeCli):
    result = invoke_cli(["misc", "apr"])
    
    assert result.exit_code == 0
    
    
    output = clean(result.stdout)
    assert re.search(r'Predicted staking APR with fee: \d+ , is: \d+.\d+%.', output)
    assert re.search(r'Lowest possible APR \(all miner profits are reinvested\) is: \d+.\d+%.', output)