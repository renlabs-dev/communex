import re
from string import hexdigits

import pytest

from tests.conftest import InvokeCli
from tests.str_utils import clean

TEST_KEY_ALIAS = "dev01"


def test_cli_network_last_block_slow(invoke_cli: InvokeCli):
    result = invoke_cli(["network", "last-block"])
    
    assert result.exit_code == 0
    assert re.match(r"^\d+\n$", result.stdout)
    

def test_cli_network_last_block_hash_slow(invoke_cli: InvokeCli):
    result = invoke_cli(["network", "last-block", "--hash"])
    
    def isHexHash(s):
        prefix = "0x"
        
        if not s.startswith(prefix):
            return False
        
        s = s[len(prefix):]
            
        hex_digits = set(hexdigits)
        
        return all(c in hex_digits for c in s)
        
    
    assert result.exit_code == 0
    assert isHexHash(clean(result.stdout))


def test_cli_network_list_proposals_slow(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")
    result = invoke_cli(["network", "list-proposals"])
    
    output = clean(result.stdout)
    assert result.exit_code == 0
    
    assert re.search(r"Proposal id: \d+", output)
    assert "subnet_params" in output
    assert "global_params" in output
    assert "netuid 0" in output
    assert "votes" in output
    assert "participants" in output
    assert "accepted" in output
    assert "data" in output
    assert "mode" in output


def test_cli_network_params_slow(invoke_cli: InvokeCli):
    result = invoke_cli(["network", "params"])
    assert result.exit_code == 0
    
    output = clean(result.stdout)
    
    assert "max_allowed_modules" in output
    assert "max_allowed_subnets" in output
    assert "max_registrations_per_block" in output
    assert "unit_emission" in output
    assert "tx_rate_limit" in output
    assert "vote_threshold" in output
    assert "vote_mode" in output
    assert "max_proposals" in output
    assert "max_name_length" in output
    assert "burn_rate" in output
    assert "min_burn" in output
    assert "min_stake" in output
    assert "min_weight_stake" in output


def test_cli_network_propose_globally(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")
    result = invoke_cli(["network", "propose-globally"])
    assert result.exit_code == 0


def test_cli_network_propose_on_subnet(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")
    result = invoke_cli(["network", "propose-on-subnet"])
    assert result.exit_code == 0


def test_cli_network_vote_proposal(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")
    result = invoke_cli(["network", "vote-proposal", "[key]", "0"])
    assert result.exit_code == 0


def test_cli_network_vote_proposal_not_allowed_slow(invoke_cli: InvokeCli):
    """Vote proposal is not allowed if key has no voting power."""
    pytest.skip("Not implemented yet")
    result = invoke_cli(["network", "vote-proposal", TEST_KEY_ALIAS, "0"])
    assert result.exit_code == 1

    assert type(result.exception).__name__ == "ChainTransactionError"
    assert "'VotingPowerIsZero'" in str(result.exception)
    

def test_cli_network_unvote_proposal(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")
    result = invoke_cli(["network", "unvote-proposal"])
    assert result.exit_code == 0
    
    
def test_cli_network_unvote_proposal_not_allowed_slow(invoke_cli: InvokeCli):
    """Unvote proposal is not allowed for non-registered vote."""
    result = invoke_cli(["network", "unvote-proposal", TEST_KEY_ALIAS, "0"])
    
    assert result.exit_code == 1
    
    assert type(result.exception).__name__ == "ChainTransactionError"
    assert "'VoterIsNotRegistered'" in str(result.exception)