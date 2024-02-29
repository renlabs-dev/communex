import pytest
from typer.testing import CliRunner, Result # type: ignore

from communex.cli import app

from typing import Callable


InvokeCli = Callable[[list[str]], Result]


@pytest.fixture()
def invoke_cli() -> InvokeCli:
    runner = CliRunner()
    
    def invoke(command: list[str]) -> Result:
        return runner.invoke(app, command, env={"COLUMNS": "200"})
    
    return invoke
