from typing import Optional
import typer
from typing_extensions import Annotated

from communex import __version__

from .balance import balance_app
from .key import key_app
from .misc import misc_app
from .module import module_app
from .network import network_app
from .subnet import subnet_app

app = typer.Typer()

app.add_typer(key_app, name="key", help="Key operations")
app.add_typer(balance_app, name="balance", help="Balance operations")
app.add_typer(misc_app, name="misc", help="Other operations")
app.add_typer(module_app, name="module", help="Module operations")
app.add_typer(network_app, name="network", help="Network operations")
app.add_typer(subnet_app, name="subnet", help="Subnet operations")


def _version_callback(value: bool):
    if value:
        print(f"CommuneX {__version__}")
        raise typer.Exit()

@app.callback()
def main(json: Optional[bool] = False,
    version: Annotated[
        Optional[bool], typer.Option("--version", callback=_version_callback)
    ] = None,
):
    """
    CommuneX CLI Version: {0}

    This command line interface is under development and subject to change.
    """
main.__doc__ = main.__doc__.format(__version__)
