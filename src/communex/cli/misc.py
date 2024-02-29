import typer
from rich.console import Console

from communex.balance import from_nano
from communex.client import CommuneClient

from ._common import BalanceUnit, format_balance, make_client

misc_app = typer.Typer()


def circulating_tokens(c_client: CommuneClient) -> int:
    """
    Gets total circulating supply
    """

    query_all = c_client.query_batch_map(
        {
            "SubspaceModule": [("TotalStake", [])],
            "System": [("Account", [])], })

    balances, stake = query_all["Account"], query_all["TotalStake"]
    format_balances: dict[str, int] = {key: value['data']['free']
                                       for key, value in balances.items()
                                       if 'data' in value and 'free' in value['data']}

    total_balance = sum(format_balances.values())
    total_stake = sum(stake.values())

    return total_stake + total_balance


@misc_app.command()
def circulating_supply(unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets the value of all keys on the network, stake + balances
    """

    console = Console()
    client = make_client()

    with console.status("Getting circulating supply, across all subnets..."):
        supply = circulating_tokens(client)

    console.print(format_balance(supply, unit))


@misc_app.command()
def apr(fee: int = 0):
    """
    Gets the current staking APR on validators.
    The miner reinvest rate & fee are specified in percentages.
    """

    console = Console()
    client = make_client()

    # adjusting the fee to the correct format
    # the default validator fee on the commune network is 20%
    fee_to_float = fee / 100

    # network parameters
    block_time = 8  # seconds
    seconds_in_a_day = 86400
    blocks_in_a_day = seconds_in_a_day / block_time

    with console.status("Getting staking APR..."):

        unit_emission = client.get_unit_emission()
        # 50% of the total emission goes to stakers
        daily_token_rewards = blocks_in_a_day * from_nano(unit_emission) / 2

        staked = client.query_batch_map(
            {
                "SubspaceModule": [("TotalStake", [])],
            }
        )["TotalStake"]

        total_staked_tokens = from_nano(sum(staked.values()))

        _apr = (daily_token_rewards * (1 - fee_to_float) * 365) / total_staked_tokens * 100

        console.print(
            f"Fee {fee} | APR {_apr:.2f}%."
        )
