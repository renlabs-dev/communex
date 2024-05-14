import re

import pytest
from typer.testing import CliRunner

from communex.cli.root import app
from tests.conftest import InvokeCli
from tests.str_utils import clean


@pytest.fixture(scope="module")
def module_list_result():
    
    runner = CliRunner()
    try:
        result = runner.invoke(app, ["module", "list"], env={"COLUMNS": "200"})
        assert result.exception is None
        yield result
    finally:
        pass


def test_cli_module_info_no_balance_slow(module_list_result, invoke_cli: InvokeCli):
    assert module_list_result.exit_code == 0
    
    match = re.search(r'name: (\S+)', module_list_result.stdout)
    
    assert match
    
    a_module_name = match.group(1)
    
    assert a_module_name
    
    result = invoke_cli(["module", "info", a_module_name])
    
    assert result.exception is None
    assert result.exit_code == 0
    
    output = clean(result.stdout)
    
    assert "uid" in output
    assert "key" in output
    assert "name" in output
    assert "address" in output
    assert "emission" in output
    assert "incentive" in output
    assert "dividends" in output
    assert "stake_from" in output
    assert "regblock" in output
    assert "last_update" in output
    assert "balance" in output
    assert "stake" in output
    assert "delegation_fee" in output

    
    
def test_cli_module_info_with_balance_slow(module_list_result, invoke_cli: InvokeCli):
    assert module_list_result.exit_code == 0
    
    match = re.search(r'name: (\S+)', module_list_result.stdout)
    assert match
    a_module_name = match.group(1)
    assert a_module_name
    
    result = invoke_cli(["module", "info", a_module_name, "--balance"])
    
    assert result.exception is None
    assert result.exit_code == 0
    
    output = clean(result.stdout)
    
    assert "uid" in output
    assert "key" in output
    assert "name" in output
    assert "address" in output
    assert "emission" in output
    assert "incentive" in output
    assert "dividends" in output
    assert "stake_from" in output
    assert "regblock" in output
    assert "last_update" in output
    assert "balance" in output
    assert "stake" in output
    assert "delegation_fee" in output

def test_cli_module_list_no_balance_slow(module_list_result):
    assert module_list_result.exit_code == 0
    
    output = clean(module_list_result.stdout)
    
    assert "module" in output
    assert "uid" in output
    assert "key" in output
    assert "name" in output
    assert "address" in output
    assert "emission" in output
    assert "incentive" in output
    assert "dividends" in output
    assert "stake_from" in output
    assert "regblock" in output
    assert "last_update" in output
    assert "balance" in output
    assert "stake" in output
    assert "delegation_fee" in output
    

def test_cli_module_list_with_balance_slow(invoke_cli: InvokeCli):
    result = invoke_cli(["module", "list", "--balances"])
    
    assert result.exception is None
    assert result.exit_code == 0
    
    output = clean(result.stdout)
    
    assert "module" in output
    assert "uid" in output
    assert "key" in output
    assert "name" in output
    assert "address" in output
    assert "emission" in output
    assert "incentive" in output
    assert "dividends" in output
    assert "stake_from" in output
    assert "regblock" in output
    assert "last_update" in output
    assert "balance" in output
    assert "stake" in output
    assert "delegation_fee" in output
    

def test_cli_module_register(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")
    result = invoke_cli(["module", "register", "[NAME]", "[IP]", "[PORT]"])
    
    assert result.exit_code == 0
    
    
def test_cli_module_serve(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")
    result = invoke_cli(["module", "serve", "[NAME]", "[TYPE]", "[KEY]"])
    
    assert result.exit_code == 0
    

def test_cli_module_update(invoke_cli: InvokeCli):
    pytest.skip("Not implemented yet")
    result = invoke_cli(["module", "update", "[KEY]", "[NAME]", "[ADDRESS]"])
    
    assert result.exit_code == 0