import pytest

from tests.conftest import InvokeCli
from tests.str_utils import clean


def test_cli_subnet_info_slow(invoke_cli: InvokeCli):
    result = invoke_cli(["subnet", "info", "0"])
    
    output = clean(result.stdout)
    
    assert result.exit_code == 0
    
    assert "name commune" in output
    assert "founder 5HarzAYD37Sp3vJs385CLvhDPN52Cb1Q352yxZnDZchznPaS" in output
    assert "founder_share" in output
    assert "immunity_period" in output
    assert "incentive_ratio" in output
    assert "max_allowed_uids" in output
    assert "max_allowed_weights" in output
    assert "min_allowed_weights" in output
    assert "max_stake" in output
    assert "min_stake" in output
    assert "tempo" in output
    assert "trust_ratio" in output
    assert "vote_mode" in output
    assert "vote_threshold" in output
    assert "emission" in output
    assert "max_weight_age" in output
    

def test_cli_subnet_list_slow(invoke_cli: InvokeCli):
    result = invoke_cli(["subnet", "list"])
    assert result.exit_code == 0    
    
    output = clean(result.stdout)
    
    assert "netuid" in output
    assert "name" in output
    assert "founder" in output
    assert "founder_share" in output
    assert "immunity_period" in output
    assert "incentive_ratio" in output
    assert "max_allowed_uids" in output
    assert "max_allowed_weights" in output
    assert "min_allowed_weights" in output
    assert "max_stake" in output
    assert "min_stake" in output
    assert "tempo" in output
    assert "trust_ratio" in output
    assert "vote_mode" in output
    assert "vote_threshold" in output
    assert "emission" in output
    assert "max_weight_age" in output
    

def test_cli_subnet_update(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")
    result = invoke_cli(["subnet", "update"])
    assert result.exit_code == 0
