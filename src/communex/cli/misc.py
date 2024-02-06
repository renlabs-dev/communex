import typer
from rich.console import Console

from communex.balance import from_nano
from communex.client import CommuneClient
from communex.misc import get_map_modules
from communex.raw_ws_ops import query_batch_map

from ._common import BalanceUnit, format_balance, make_client

misc_app = typer.Typer()


def calculate_apr(daily_rewards: float, total_staked: float, miner_reinvestment_rate: float, fee_percentage: float = 0) -> float:
    """
    Calculating the approximate APR for staking.
    - Make sure to pass all parameters in the same unit!
    - Fee percentage should be a decimal (e.g., for 20% fee, use 0.20)
    """

    daily_staker_reward = daily_rewards / 2
    daily_miner_reward = daily_rewards / 2

    # Adjusting the daily staker reward based on the fee
    daily_staker_reward_after_fee = daily_staker_reward * (1 - fee_percentage)

    annual_staker_reward = daily_staker_reward_after_fee * 365

    adjusted_total_staked = total_staked + \
        sum(daily_miner_reward * miner_reinvestment_rate for _ in range(365))
    apr = (annual_staker_reward / adjusted_total_staked) * 100

    return apr


def circulating_tokens(c_client: CommuneClient) -> int:
    """
    Gets total circulating supply
    """

    with c_client.get_conn() as substrate:
        query_all = query_batch_map(substrate,
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
def apr(netuid: int = 0, miner_reinvest: int = 85, fee: int = 0):
    """
    Gets the current staking APR on validators.
    The miner reinvest rate & fee are specified in percentages.
    """

    console = Console()
    client = make_client()

    daily_token_rewards = 250_000

    # APROXIMATE RATE THAT MINERS REINVEST INTO VALIDATOR STAKING
    # adjust to the correct format
    miner_reinvesment_rate: float = miner_reinvest / 100

    # adjusting the fee to the correct format
    # the default validator fee on the commune network is 20%
    fee_to_float: float = fee / 100

    with console.status("Calculating staking APR, getting current network information..."):
        modules = get_map_modules(client, netuid=netuid)
        modules_to_list = [value for _, value in modules.items()]

    # filter by modules that obviously set weights
    validators_stake = sum([module["stake"]
                           for module in modules_to_list if module["dividends"] > 100])

    total_staked_tokens = from_nano(validators_stake)
    apr_lowest = calculate_apr(daily_token_rewards, total_staked_tokens, 1, fee_to_float)
    apr = calculate_apr(daily_token_rewards, total_staked_tokens,
                        miner_reinvesment_rate, fee_to_float)

    console.print(
        f"Predicted staking APR with fee: {fee} , is: {apr:.2f}%.\n"
        f"Lowest possible APR (all miner profits are reinvested) is: {apr_lowest:.2f}%.")
