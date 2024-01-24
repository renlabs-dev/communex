from typing import Optional
import typer

from .balance import balance_app
from .key import key_app
from .misc import misc_app
from .module import module_app
from .network import network_app
from .subnet import subnet_app

app = typer.Typer()

app.add_typer(key_app, name="key", help="General operations")
app.add_typer(balance_app, name="balance", help="Balance operations")
app.add_typer(misc_app, name="misc", help="Misc operations")
app.add_typer(module_app, name="module", help="Module operations")
app.add_typer(network_app, name="network", help="Network operations")
app.add_typer(subnet_app, name="subnet", help="Subnet operations")


@app.callback()
def main(json: Optional[bool] = False):
    """
    Communex CLI
    """
