import re
from typing import Any, cast

import typer
from typer import Context

from communex.cli._common import (
    make_custom_context,
    print_table_from_plain_dict,
    print_table_standardize,
    transform_subnet_params
    )
from communex.compat.key import resolve_key_ss58, try_classic_load_key
from communex.errors import ChainTransactionError
from communex.misc import IPFS_REGEX, get_map_subnets_params
from communex.types import SubnetParamsWithVoteMode, VoteMode, BurnConfiguration

subnet_app = typer.Typer(no_args_is_help=True)


@subnet_app.command()
def list(ctx: Context):
    """
    Gets subnets.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Getting subnets ..."):
        subnets = get_map_subnets_params(client)

    keys, values = subnets.keys(), subnets.values()
    display_values = map(transform_subnet_params, values)
    subnets_with_netuids = [
        {"netuid": key, **value} for key, value in zip(keys, display_values)
    ]

    for dict in subnets_with_netuids:  # type: ignore
        print_table_from_plain_dict(
            dict, ["Params", "Values"], context.console)  # type: ignore


@subnet_app.command()
def distribution(ctx: Context):
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Getting emission distribution..."):
        subnets_emission = client.query_map_subnet_emission()
        subnet_consensus = client.query_map_subnet_consensus()
        subnet_names = client.query_map_subnet_names()
        total_emission = sum(subnets_emission.values())
        subnet_emission_percentages = {
            key: value / total_emission * 100 for key, value in subnets_emission.items()
        }

    # Prepare the data for the table
    table_data: dict[str, Any] = {
        "Subnet": [],
        "Name": [],
        "Consensus": [],
        "Emission %": []
    }

    for subnet, emission_percentage in subnet_emission_percentages.items():
        if emission_percentage > 0:
            table_data["Subnet"].append(str(subnet))
            table_data["Name"].append(subnet_names.get(subnet, "N/A"))
            table_data["Consensus"].append(subnet_consensus.get(subnet, "N/A"))
            table_data["Emission %"].append(f"{round(emission_percentage, 2)}%")

    print_table_standardize(table_data, context.console)


@subnet_app.command()
def legit_whitelist(ctx: Context):
    """
    Gets the legitimate whitelist of modules for the general subnet 0
    """

    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Getting legitimate whitelist ..."):
        whitelist = cast(dict[str, int], client.query_map_legit_whitelist())

    print_table_from_plain_dict(
        whitelist, ["Module", "Recommended weight"], context.console
    )


@subnet_app.command()
def info(ctx: Context, netuid: int):
    """
    Gets subnet info.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status(f"Getting subnet with netuid '{netuid}'..."):

        subnets = get_map_subnets_params(client)
        subnet = subnets.get(netuid, None)

    if subnet is None:
        raise ValueError("Subnet not found")

    general_subnet: dict[str, Any] = cast(dict[str, Any], subnet)
    print_table_from_plain_dict(
        general_subnet, ["Params", "Values"], context.console)


@subnet_app.command()
def register(
    ctx: Context,
    key: str,
    name: str,
    metadata: str = typer.Option(None)
):
    """
    Registers a new subnet.
    """
    context = make_custom_context(ctx)
    resolved_key = try_classic_load_key(key)
    client = context.com_client()

    with context.progress_status("Registering subnet ..."):
        response = client.register_subnet(resolved_key, name, metadata)

    if response.is_success:
        context.info(f"Successfully registered subnet {name}")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@subnet_app.command()
def update(
    ctx: Context,
    netuid: int,
    key: str,
    founder: str = typer.Option(None),
    founder_share: int = typer.Option(None),
    name: str = typer.Option(None),
    metadata: str = typer.Option(None),
    immunity_period: int = typer.Option(None),
    incentive_ratio: int = typer.Option(None),
    max_allowed_uids: int = typer.Option(None),
    max_allowed_weights: int = typer.Option(None),
    min_allowed_weights: int = typer.Option(None),
    max_weight_age: int = typer.Option(None),
    tempo: int = typer.Option(None),
    trust_ratio: int = typer.Option(None),
    maximum_set_weight_calls_per_epoch: int = typer.Option(None),

    # GovernanceConfiguration
    vote_mode: VoteMode = typer.Option(None),

    bonds_ma: int = typer.Option(None),

    # BurnConfiguration
    min_burn: int = typer.Option(None),
    max_burn: int = typer.Option(None),
    adjustment_alpha: int = typer.Option(None),
    target_registrations_interval: int = typer.Option(None),
    target_registrations_per_interval: int = typer.Option(None),
    max_registrations_per_interval: int = typer.Option(None),

    min_validator_stake: int = typer.Option(None),
    max_allowed_validators: int = typer.Option(None),
):
    """
    Updates a subnet.
    """
    context = make_custom_context(ctx)
    client = context.com_client()
    resolved_key = try_classic_load_key(key)

    module_burn_config: BurnConfiguration = cast(BurnConfiguration, {
        'min_burn': min_burn,
        'max_burn': max_burn,
        'adjustment_alpha': adjustment_alpha,
        'target_registrations_interval': target_registrations_interval,
        'target_registrations_per_interval': target_registrations_per_interval,
        'max_registrations_per_interval': max_registrations_per_interval
    })

    subnet = cast(SubnetParamsWithVoteMode, {
        'name': name,
        'tempo': tempo,
        'min_allowed_weights': min_allowed_weights,
        'max_allowed_weights': max_allowed_weights,
        'max_allowed_uids': max_allowed_uids,
        'max_weight_age': max_weight_age,
        'trust_ratio': trust_ratio ,
        'founder_share': founder_share ,
        'incentive_ratio': incentive_ratio ,
        'founder': resolve_key_ss58(founder),
        'maximum_set_weight_calls_per_epoch':
            client.query("MaximumSetWeightCallsPerEpoch")
                if maximum_set_weight_calls_per_epoch is None # type: ignore
                else maximum_set_weight_calls_per_epoch,
        'bonds_ma': client.query("BondsMovingAverage") if bonds_ma is None else bonds_ma, # type: ignore
        'immunity_period': immunity_period ,
        'min_validator_stake': min_validator_stake ,
        'max_allowed_validators': max_allowed_validators ,
        'module_burn_config': module_burn_config,
        'subnet_metadata': metadata,
        'vote_mode': vote_mode,
    })

    with context.progress_status("Updating subnet ..."):
        response = client.update_subnet(
            key=resolved_key, params=subnet, netuid=netuid
        )

    if response.is_success:
        context.info(
            f"Successfully updated subnet {subnet.get('name')} with netuid {netuid}"
        )
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@subnet_app.command()
def propose_on_subnet(
    ctx: Context,
    key: str,
    netuid: int,
    cid: str,
    founder: str = typer.Option(None),
    founder_share: int = typer.Option(None),
    metadata: str = typer.Option(None),
    name: str = typer.Option(None),
    immunity_period: int = typer.Option(None),
    incentive_ratio: int = typer.Option(None),
    max_allowed_uids: int = typer.Option(None),
    max_allowed_weights: int = typer.Option(None),
    min_allowed_weights: int = typer.Option(None),
    max_weight_age: int = typer.Option(None),
    tempo: int = typer.Option(None),
    trust_ratio: int = typer.Option(None),
    maximum_set_weight_calls_per_epoch: int = typer.Option(None),
    bonds_ma: int = typer.Option(None),

    vote_mode: VoteMode = typer.Option(None, help="0 for Authority, 1 for Vote"),

    # BurnConfiguration
    min_burn: int = typer.Option(None),
    max_burn: int = typer.Option(None),
    adjustment_alpha: int = typer.Option(None),
    target_registrations_interval: int = typer.Option(None),
    target_registrations_per_interval: int = typer.Option(None),
    max_registrations_per_interval: int = typer.Option(None),

    min_validator_stake: int = typer.Option(None),
    max_allowed_validators: int = typer.Option(None),
):
    """
    Adds a proposal to a specific subnet.
    """
    context = make_custom_context(ctx)
    if not re.match(IPFS_REGEX, cid):
        context.error(f"CID provided is invalid: {cid}")
        exit(1)
    else:
        ipfs_prefix = "ipfs://"
        cid = ipfs_prefix + cid

    context = make_custom_context(ctx)
    client = context.com_client()
    resolved_key = try_classic_load_key(key)

    module_burn_config: BurnConfiguration = cast(BurnConfiguration, {
        'min_burn': min_burn,
        'max_burn': max_burn,
        'adjustment_alpha': adjustment_alpha,
        'target_registrations_interval': target_registrations_interval,
        'target_registrations_per_interval': target_registrations_per_interval,
        'max_registrations_per_interval': max_registrations_per_interval
    })

    subnet = cast(SubnetParamsWithVoteMode, {
        'name': name,
        'tempo': tempo,
        'min_allowed_weights': min_allowed_weights,
        'max_allowed_weights': max_allowed_weights,
        'max_allowed_uids': max_allowed_uids,
        'max_weight_age': max_weight_age,
        'trust_ratio': trust_ratio ,
        'founder_share': founder_share ,
        'incentive_ratio': incentive_ratio ,
        'founder': resolve_key_ss58(founder),
        'maximum_set_weight_calls_per_epoch':
            client.query("MaximumSetWeightCallsPerEpoch")
                if maximum_set_weight_calls_per_epoch is None # type: ignore
                else maximum_set_weight_calls_per_epoch,
        'bonds_ma': client.query("BondsMovingAverage") if bonds_ma is None else bonds_ma, # type: ignore
        'immunity_period': immunity_period ,
        'min_validator_stake': min_validator_stake ,
        'max_allowed_validators': max_allowed_validators ,
        'module_burn_config': module_burn_config,
        'subnet_metadata': metadata,
        'vote_mode': vote_mode,
    })

    resolved_key = try_classic_load_key(key)
    with context.progress_status("Adding a proposal..."):
        client.add_subnet_proposal(
            resolved_key,
            params = dict(subnet),
            ipfs = cid,
            netuid = netuid
        )

    context.info("Proposal added.")


@subnet_app.command()
def submit_general_subnet_application(
    ctx: Context, key: str, application_key: str, cid: str
):
    """
    Submits a legitimate whitelist application to the general subnet, netuid 0.
    """

    context = make_custom_context(ctx)
    if not re.match(IPFS_REGEX, cid):
        context.error(f"CID provided is invalid: {cid}")
        exit(1)

    client = context.com_client()

    resolved_key = try_classic_load_key(key)
    resolved_application_key = resolve_key_ss58(application_key)

    # append the ipfs hash
    ipfs_prefix = "ipfs://"
    cid = ipfs_prefix + cid

    with context.progress_status("Adding a application..."):
        client.add_dao_application(resolved_key, resolved_application_key, cid)


@subnet_app.command()
def add_custom_proposal(
    ctx: Context,
    key: str,
    cid: str,
    netuid: int,
):
    """
    Adds a custom proposal to a specific subnet.
    """

    context = make_custom_context(ctx)
    if not re.match(IPFS_REGEX, cid):
        context.error(f"CID provided is invalid: {cid}")
        exit(1)

    client = context.com_client()

    resolved_key = try_classic_load_key(key)

    # append the ipfs hash
    ipfs_prefix = "ipfs://"
    cid = ipfs_prefix + cid

    with context.progress_status("Adding a proposal..."):
        client.add_custom_subnet_proposal(resolved_key, cid, netuid=netuid)


@subnet_app.command()
def list_curator_applications(
    ctx: Context
):
    """
    Lists all curator applications.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Querying applications..."):
        apps = client.query_map_curator_applications()
    print(apps)
