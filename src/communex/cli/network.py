from typing import Any, cast

import typer
from rich.console import Console

from communex.types import NetworkParams, SubnetParams
from communex.misc import get_global_params
from cexpl.commune.key import Key

from ._common import make_client, print_table_from_plain_dict

network_app = typer.Typer()


@network_app.command()
def last_block(hash: bool = False):
    """
    Gets the last block
    """

    console = Console()
    client = make_client()

    info = "number" if not hash else "hash"

    block = client.get_block()
    block_info = None
    if block:
        block_info = block["header"][info]

    console.print(block_info)


@network_app.command()
def list_params():
    """
    Gets global params
    """

    console = Console()
    client = make_client()

    with console.status("Getting global network params ...",):
        global_params = get_global_params(client)

    general_params: dict[str, Any] = cast(dict[str, Any], global_params)
    print_table_from_plain_dict(general_params, ["Global params", "Value"], console)


@network_app.command()
def list_proposals():
    console = Console()
    client = make_client()

    with console.status("Getting proposals..."):
        proposals = client.query_map_proposals()

    for proposal_id, proposal in proposals.items():
        print_table_from_plain_dict(proposal, [f"Proposal id: {proposal_id}", "Params"], console)


@network_app.command()
def propose_globally(
    key: str,
    max_allowed_subnets: int,
    max_allowed_modules: int,
    max_registrations_per_block: int,
    unit_emission: int,
    tx_rate_limit: int,
    vote_threshold: int,
    vote_mode: str,
    max_proposals: int,
    max_name_length: int,
    burn_rate: int,
    min_burn: int,
    min_stake: int,
    min_weight_stake: int,
):
    """
    Adds a global proposal to the network.
    """

    console = Console()
    client = make_client()

    resolved_key = Key.resolve_key(key)

    proposal: NetworkParams = {"max_allowed_subnets": max_allowed_subnets,
                               "max_allowed_modules": max_allowed_modules,
                               "max_registrations_per_block": max_registrations_per_block,
                               "unit_emission": unit_emission,
                               "tx_rate_limit": tx_rate_limit,
                               "vote_threshold": vote_threshold,
                               "vote_mode": vote_mode,
                               "max_proposals": max_proposals,
                               "max_name_length": max_name_length,
                               "burn_rate": burn_rate,
                               "min_burn": min_burn,
                               "min_stake": min_stake,
                               "min_weight_stake": min_weight_stake}

    with console.status("Adding a proposal..."):
        client.add_global_proposal(resolved_key, proposal)

# ! THESE ARE BETA COMMANDS (might not have full substrate support)


@network_app.command()
def propose_on_subnet(
    key: str,
    name: str,
    founder: str,
    founder_share: int,
    immunity_period: int,
    incentive_ratio: int,
    max_allowed_uids: int,
    max_allowed_weights: int,
    min_allowed_weights: int,
    max_stake: int,
    min_stake: int,
    tempo: int,
    self_vote: bool,
    trust_ratio: int,
    vote_mode: str,
    vote_threshold: int,
    max_weight_age: int,
):
    """
    Adds a proposal to a specific subnet.
    """

    console = Console()
    client = make_client()

    resolve_founder = Key.resolve_key_ss58(founder)
    resolved_key = Key.resolve_key(key)

    proposal: SubnetParams = {"name": name,
                              "founder": resolve_founder,
                              "founder_share": founder_share,
                              "immunity_period": immunity_period,
                              "incentive_ratio": incentive_ratio,
                              "max_allowed_uids": max_allowed_uids,
                              "max_allowed_weights": max_allowed_weights,
                              "min_allowed_weights": min_allowed_weights,
                              "max_stake": max_stake,
                              "min_stake": min_stake,
                              "tempo": tempo,
                              "self_vote": self_vote,
                              "trust_ratio": trust_ratio,
                              "vote_mode": vote_mode,
                              "vote_threshold": vote_threshold,
                              "max_weight_age": max_weight_age,
                              }

    with console.status("Adding a proposal..."):
        client.add_subnet_proposal(resolved_key, proposal)


@network_app.command()
def vote_proposal(key: str, proposal_id: int):
    console = Console()
    client = make_client()

    resolved_key = Key.resolve_key(key)
    with console.status(f"Voting on a proposal {proposal_id}..."):
        client.vote_on_proposal(resolved_key, proposal_id)


@network_app.command()
def unvote_proposal(key: str, proposal_id: int):
    console = Console()
    client = make_client()

    resolved_key = Key.resolve_key(key)
    with console.status(f"Unvoting on a proposal {proposal_id}..."):
        client.unvote_on_proposal(resolved_key, proposal_id)
