import re
from typing import Any, TypeVar, cast

from communex._common import transform_stake_dmap
from communex.balance import to_nano
from communex.cli._common import transform_subnet_params
from communex.client import CommuneClient
from communex.key import check_ss58_address
from communex.types import (
    BurnConfiguration,
    GovernanceConfiguration,
    ModuleInfoWithOptionalBalance,
    NetworkParams,
    Ss58Address,
    SubnetParamsMaps,
    SubnetParamsWithEmission,
)

IPFS_REGEX = re.compile(r"^Qm[1-9A-HJ-NP-Za-km-z]{44}$")

T = TypeVar("T")


def get_map_modules(
    client: CommuneClient,
    netuid: int = 0,
    include_balances: bool = False,
) -> dict[str, ModuleInfoWithOptionalBalance]:
    """
    Gets all modules info on the network
    """

    request_dict: dict[Any, Any] = {
        "SubspaceModule": [
            ("StakeFrom", []),
            ("Keys", [netuid]),
            ("Name", [netuid]),
            ("Address", [netuid]),
            ("RegistrationBlock", [netuid]),
            ("DelegationFee", []),
            ("Emission", []),
            ("Incentive", []),
            ("Dividends", []),
            ("LastUpdate", []),
            ("Metadata", [netuid]),
            ("StakeTo", []),
        ],
    }
    if include_balances:
        request_dict["System"] = [("Account", [])]
    bulk_query = client.query_batch_map(request_dict)
    (
        ss58_to_stakefrom,
        uid_to_key,
        uid_to_name,
        uid_to_address,
        uid_to_regblock,
        ss58_to_delegationfee,
        uid_to_emission,
        uid_to_incentive,
        uid_to_dividend,
        uid_to_lastupdate,
        ss58_to_balances,
        ss58_to_metadata,
    ) = (
        bulk_query.get("StakeFrom", {}),
        bulk_query.get("Keys", {}),
        bulk_query["Name"],
        bulk_query["Address"],
        bulk_query["RegistrationBlock"],
        bulk_query["DelegationFee"],
        bulk_query["Emission"],
        bulk_query["Incentive"],
        bulk_query["Dividends"],
        bulk_query["LastUpdate"],
        bulk_query.get("Account", {}),
        bulk_query.get("Metadata", {}),
    )
    result_modules: dict[str, ModuleInfoWithOptionalBalance] = {}
    ss58_to_stakefrom = transform_stake_dmap(ss58_to_stakefrom)
    for uid, key in uid_to_key.items():
        key = check_ss58_address(key)
        name = uid_to_name[uid]
        address = uid_to_address[uid]
        emission = uid_to_emission[netuid][uid]
        incentive = uid_to_incentive[netuid][uid]
        dividend = uid_to_dividend[netuid][uid]
        regblock = uid_to_regblock[uid]
        stake_from = ss58_to_stakefrom.get(key, [])
        last_update = uid_to_lastupdate[netuid][uid]
        delegation_fee = ss58_to_delegationfee.get(
            key, 5
        )  # 5% default delegation fee
        metadata = ss58_to_metadata.get(key, None)

        balance = None
        if include_balances and ss58_to_balances is not None:  # type: ignore
            balance_dict = ss58_to_balances.get(key, None)
            if balance_dict is not None:
                assert isinstance(balance_dict["data"], dict)
                balance = balance_dict["data"]["free"]
            else:
                balance = 0
        stake = sum(stake for _, stake in stake_from)

        module: ModuleInfoWithOptionalBalance = {
            "uid": uid,
            "key": key,
            "name": name,
            "address": address,
            "emission": emission,
            "incentive": incentive,
            "dividends": dividend,
            "stake_from": stake_from,
            "regblock": regblock,
            "last_update": last_update,
            "balance": balance,
            "stake": stake,
            "delegation_fee": delegation_fee,
            "metadata": metadata,
        }

        result_modules[key] = module
    return result_modules


def to_snake_case(d: dict[str, T]) -> dict[str, T]:
    """
    Converts a dictionary with camelCase keys to snake_case keys
    """

    def snakerize(camel: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", camel).lower()

    snaked: dict[str, T] = {snakerize(k): v for k, v in d.items()}
    return snaked


def get_map_displayable_subnets(client: CommuneClient):
    subnets = get_map_subnets_params(client)
    display_values = transform_subnet_params(subnets)
    return display_values


def get_map_subnets_params(
    client: CommuneClient, block_hash: str | None = None
) -> dict[int, SubnetParamsWithEmission]:
    """
    Gets all subnets info on the network
    """
    bulk_query = client.query_batch_map(
        {
            "SubspaceModule": [
                ("ImmunityPeriod", []),
                ("MinAllowedWeights", []),
                ("MaxAllowedWeights", []),
                ("Tempo", []),
                ("MaxAllowedUids", []),
                ("Founder", []),
                ("FounderShare", []),
                ("IncentiveRatio", []),
                ("TrustRatio", []),
                ("SubnetNames", []),
                ("MaxWeightAge", []),
                ("BondsMovingAverage", []),
                ("MaximumSetWeightCallsPerEpoch", []),
                ("MinValidatorStake", []),
                ("MaxAllowedValidators", []),
                ("ModuleBurnConfig", []),
                ("SubnetMetadata", []),
            ],
            "GovernanceModule": [
                ("SubnetGovernanceConfig", []),
            ],
            "SubnetEmissionModule": [
                ("SubnetEmission", []),
            ],
        },
        block_hash,
    )
    subnet_maps: SubnetParamsMaps = {
        "netuid_to_emission": bulk_query["SubnetEmission"],
        "netuid_to_tempo": bulk_query["Tempo"],
        "netuid_to_min_allowed_weights": bulk_query["MinAllowedWeights"],
        "netuid_to_max_allowed_weights": bulk_query["MaxAllowedWeights"],
        "netuid_to_max_allowed_uids": bulk_query["MaxAllowedUids"],
        "netuid_to_founder": bulk_query["Founder"],
        "netuid_to_founder_share": bulk_query["FounderShare"],
        "netuid_to_incentive_ratio": bulk_query["IncentiveRatio"],
        "netuid_to_trust_ratio": bulk_query["TrustRatio"],
        "netuid_to_name": bulk_query["SubnetNames"],
        "netuid_to_max_weight_age": bulk_query["MaxWeightAge"],
        "netuid_to_bonds_ma": bulk_query.get("BondsMovingAverage", {}),
        "netuid_to_maximum_set_weight_calls_per_epoch": bulk_query.get(
            "MaximumSetWeightCallsPerEpoch", {}
        ),
        "netuid_to_governance_configuration": bulk_query[
            "SubnetGovernanceConfig"
        ],
        "netuid_to_immunity_period": bulk_query["ImmunityPeriod"],
        "netuid_to_min_validator_stake": bulk_query.get(
            "MinValidatorStake", {}
        ),
        "netuid_to_max_allowed_validators": bulk_query.get(
            "MaxAllowedValidators", {}
        ),
        "netuid_to_module_burn_config": bulk_query.get("ModuleBurnConfig", {}),
        "netuid_to_subnet_metadata": bulk_query.get("SubnetMetadata", {}),
    }
    result_subnets: dict[int, SubnetParamsWithEmission] = {}

    for netuid, name in subnet_maps["netuid_to_name"].items():
        subnet: SubnetParamsWithEmission = {
            "name": name,
            "founder": subnet_maps["netuid_to_founder"][netuid],
            "founder_share": subnet_maps["netuid_to_founder_share"][netuid],
            "incentive_ratio": subnet_maps["netuid_to_incentive_ratio"][netuid],
            "max_allowed_uids": subnet_maps["netuid_to_max_allowed_uids"][
                netuid
            ],
            "max_allowed_weights": subnet_maps["netuid_to_max_allowed_weights"][
                netuid
            ],
            "min_allowed_weights": subnet_maps["netuid_to_min_allowed_weights"][
                netuid
            ],
            "tempo": subnet_maps["netuid_to_tempo"][netuid],
            "trust_ratio": subnet_maps["netuid_to_trust_ratio"][netuid],
            "emission": subnet_maps["netuid_to_emission"][netuid],
            "max_weight_age": subnet_maps["netuid_to_max_weight_age"][netuid],
            "bonds_ma": subnet_maps["netuid_to_bonds_ma"].get(netuid, None),
            "maximum_set_weight_calls_per_epoch": subnet_maps[
                "netuid_to_maximum_set_weight_calls_per_epoch"
            ].get(netuid, 30),
            "governance_config": subnet_maps[
                "netuid_to_governance_configuration"
            ][netuid],
            "immunity_period": subnet_maps["netuid_to_immunity_period"][netuid],
            "min_validator_stake": subnet_maps[
                "netuid_to_min_validator_stake"
            ].get(netuid, to_nano(50_000)),
            "max_allowed_validators": subnet_maps[
                "netuid_to_max_allowed_validators"
            ].get(netuid, 50),
            "module_burn_config": cast(
                BurnConfiguration,
                subnet_maps["netuid_to_module_burn_config"].get(netuid, None),
            ),
            "subnet_metadata": subnet_maps["netuid_to_subnet_metadata"].get(
                netuid, None
            ),
        }

        result_subnets[netuid] = subnet

    return result_subnets


def get_global_params(c_client: CommuneClient) -> NetworkParams:
    """
    Returns global parameters of the whole commune ecosystem
    """

    query_all = c_client.query_batch(
        {
            "SubspaceModule": [
                ("MaxNameLength", []),
                ("MinNameLength", []),
                ("MaxAllowedSubnets", []),
                ("MaxAllowedModules", []),
                ("MaxRegistrationsPerBlock", []),
                ("MaxAllowedWeightsGlobal", []),
                ("FloorDelegationFee", []),
                ("FloorFounderShare", []),
                ("MinWeightStake", []),
                ("Kappa", []),
                ("Rho", []),
                ("SubnetImmunityPeriod", []),
                ("SubnetBurn", []),
            ],
            "GovernanceModule": [
                ("GlobalGovernanceConfig", []),
                ("GeneralSubnetApplicationCost", []),
                ("Curator", []),
            ],
        }
    )
    global_config = cast(
        GovernanceConfiguration, query_all["GlobalGovernanceConfig"]
    )
    global_params: NetworkParams = {
        "max_allowed_subnets": int(query_all["MaxAllowedSubnets"]),
        "max_allowed_modules": int(query_all["MaxAllowedModules"]),
        "max_registrations_per_block": int(
            query_all["MaxRegistrationsPerBlock"]
        ),
        "max_name_length": int(query_all["MaxNameLength"]),
        "min_weight_stake": int(query_all["MinWeightStake"]),
        "floor_delegation_fee": int(query_all["FloorDelegationFee"]),
        "max_allowed_weights": int(query_all["MaxAllowedWeightsGlobal"]),
        "curator": Ss58Address(query_all["Curator"]),
        "min_name_length": int(query_all["MinNameLength"]),
        "floor_founder_share": int(query_all["FloorFounderShare"]),
        "general_subnet_application_cost": int(
            query_all["GeneralSubnetApplicationCost"]
        ),
        "kappa": int(query_all["Kappa"]),
        "rho": int(query_all["Rho"]),
        "subnet_immunity_period": int(query_all["SubnetImmunityPeriod"]),
        "subnet_registration_cost": int(query_all["SubnetBurn"]),
        "governance_config": {
            "proposal_cost": int(global_config["proposal_cost"]),
            "proposal_expiration": int(global_config["proposal_expiration"]),
            "vote_mode": global_config["vote_mode"],
            "proposal_reward_treasury_allocation": int(
                global_config["proposal_reward_treasury_allocation"]
            ),
            "max_proposal_reward_treasury_allocation": int(
                global_config["max_proposal_reward_treasury_allocation"]
            ),
            "proposal_reward_interval": int(
                global_config["proposal_reward_interval"]
            ),
        },
    }
    return global_params


def concat_to_local_keys(
    balance: dict[str, int], local_key_info: dict[str, Ss58Address]
) -> dict[str, int]:
    key2: dict[str, int] = {
        key_name: balance.get(key_address, 0)
        for key_name, key_address in local_key_info.items()
    }

    return key2


def local_keys_to_freebalance(
    c_client: CommuneClient,
    local_keys: dict[str, Ss58Address],
) -> dict[str, int]:
    query_all = c_client.query_batch_map(
        {
            "System": [("Account", [])],
        }
    )
    balance_map = query_all["Account"]

    format_balances: dict[str, int] = {
        key: value["data"]["free"]
        for key, value in balance_map.items()
        if "data" in value and "free" in value["data"]
    }

    key2balance: dict[str, int] = concat_to_local_keys(
        format_balances, local_keys
    )

    return key2balance


def local_keys_to_stakedbalance(
    c_client: CommuneClient,
    local_keys: dict[str, Ss58Address],
) -> dict[str, int]:
    staketo_map = c_client.query_map_staketo()

    format_stake: dict[str, int] = {
        key: sum(stake for _, stake in value)
        for key, value in staketo_map.items()
    }

    key2stake: dict[str, int] = concat_to_local_keys(format_stake, local_keys)

    return key2stake


def local_keys_to_stakedfrom_balance(
    c_client: CommuneClient,
    local_keys: dict[str, Ss58Address],
) -> dict[str, int]:
    stakefrom_map = c_client.query_map_stakefrom()

    format_stake: dict[str, int] = {
        key: sum(stake for _, stake in value)
        for key, value in stakefrom_map.items()
    }

    key2stake: dict[str, int] = concat_to_local_keys(format_stake, local_keys)
    key2stake = {key: stake for key, stake in key2stake.items()}
    return key2stake


def local_keys_allbalance(
    c_client: CommuneClient,
    local_keys: dict[str, Ss58Address],
) -> tuple[dict[str, int], dict[str, int]]:
    query_all = c_client.query_batch_map(
        {
            "System": [("Account", [])],
            "SubspaceModule": [
                ("StakeTo", []),
            ],
        }
    )

    balance_map, staketo_map = (
        query_all["Account"],
        transform_stake_dmap(query_all["StakeTo"]),
    )

    format_balances: dict[str, int] = {
        key: value["data"]["free"]
        for key, value in balance_map.items()
        if "data" in value and "free" in value["data"]
    }
    key2balance: dict[str, int] = concat_to_local_keys(
        format_balances, local_keys
    )
    format_stake: dict[str, int] = {
        key: sum(stake for _, stake in value)
        for key, value in staketo_map.items()
    }

    key2stake: dict[str, int] = concat_to_local_keys(format_stake, local_keys)

    key2balance = {
        k: v
        for k, v in sorted(
            key2balance.items(), key=lambda item: item[1], reverse=True
        )
    }

    key2stake = {
        k: v
        for k, v in sorted(
            key2stake.items(), key=lambda item: item[1], reverse=True
        )
    }

    return key2balance, key2stake


if __name__ == "__main__":
    from communex._common import get_node_url

    client = CommuneClient(get_node_url(use_testnet=True))
    get_global_params(client)
