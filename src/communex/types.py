"""
Common types for the communex module.
"""

from typing import NewType, TypedDict

Ss58Address = NewType("Ss58Address", str)
"""Substrate SS58 address.

The `SS58 encoded address format`_ is based on the Bitcoin Base58Check format,
but with a few modification specifically designed to suite Substrate-based
chains.

.. _SS58 encoded address format:
    https://docs.substrate.io/reference/address-formats/
"""


# TODO: replace with dataclasses

# == Burn related
MinBurn = NewType("MinBurn", int)
MaxBurn = NewType("MaxBurn", int)
BurnConfig = NewType("BurnConfig", dict[MinBurn, MaxBurn])


class GovernanceConfiguration(TypedDict):
    proposal_cost: int
    proposal_expiration: int
    vote_mode: int # 0: Authority, 1: Vote
    proposal_reward_treasury_allocation: float
    max_proposal_reward_treasury_allocation: int
    proposal_reward_interval: int



class NetworkParams(TypedDict):
    # max
    max_name_length: int
    min_name_length: int # dont change the position
    max_allowed_subnets: int
    max_allowed_modules: int
    max_registrations_per_block: int
    max_allowed_weights: int

    # mins
    floor_delegation_fee: int
    floor_founder_share: int
    min_weight_stake: int

    # S0 governance
    curator: Ss58Address
    general_subnet_application_cost: int

    # Other
    subnet_immunity_period: int
    min_burn: int
    max_burn: int
    governance_config: GovernanceConfiguration

    kappa: int
    rho: int


class SubnetParamsMaps(TypedDict):
    netuid_to_founder: dict[int, Ss58Address]
    netuid_to_founder_share: dict[int, int]
    netuid_to_incentive_ratio: dict[int, int]
    netuid_to_max_allowed_uids: dict[int, int]
    netuid_to_max_allowed_weights: dict[int, int]
    netuid_to_min_allowed_weights: dict[int, int]
    netuid_to_max_weight_age: dict[int, int]
    netuid_to_name: dict[int, str]
    netuid_to_tempo: dict[int, int]
    netuid_to_trust_ratio: dict[int, int]
    netuid_to_bonds_ma: dict[int, int]
    netuid_to_maximum_set_weight_calls_per_epoch: dict[int, int]
    netuid_to_target_registrations_per_interval: dict[int, int]
    netuid_to_target_registrations_interval: dict[int, int]
    netuid_to_emission: dict[int, int]
    netuid_to_max_registrations_per_interval: dict[int, int]
    netuid_to_adjustment_alpha: dict[int, int]
    netuid_to_min_immunity_stake: dict[int, int]
    netuid_to_immunity_period: dict[int, int]
    netuid_to_governance_configuration: dict[int, GovernanceConfiguration]


class SubnetParams(TypedDict):
    name: str
    tempo: int
    min_allowed_weights: int
    max_allowed_weights: int
    max_allowed_uids: int
    max_weight_age: int
    trust_ratio: int
    founder_share: int
    incentive_ratio: int
    founder: Ss58Address
    maximum_set_weight_calls_per_epoch: int | None
    bonds_ma: int | None
    target_registrations_interval: int
    target_registrations_per_interval: int
    max_registrations_per_interval: int
    adjustment_alpha: int
    min_immunity_stake: int
    immunity_period: int
    governance_config: GovernanceConfiguration


# redundant "TypedDict" inheritance because of pdoc warns.
# see https://github.com/mitmproxy/pdoc/blob/26d40827ddbe1658e8ac46cd092f17a44cf0287b/pdoc/doc.py#L691-L692
class SubnetParamsWithEmission(SubnetParams, TypedDict):
    """SubnetParams with emission field."""

    emission: int
    """Subnet emission percentage (0-100).
    """


class ModuleInfo(TypedDict):
    uid: int
    key: Ss58Address
    name: str
    address: str  # "<ip>:<port>"
    emission: int
    incentive: int
    dividends: int
    stake_from: list[tuple[str, int]]  # TODO: type key with Ss58Address
    regblock: int  # block number
    last_update: int  # block number
    stake: int
    delegation_fee: int
    metadata: str


class ModuleInfoWithBalance(ModuleInfo):
    balance: int


class ModuleInfoWithOptionalBalance(ModuleInfo):
    balance: int | None
