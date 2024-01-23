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

# TODO: replace with dataclasses(?)


class NetworkParams(TypedDict):
    max_allowed_subnets: int
    max_allowed_modules: int
    max_registrations_per_block: int
    unit_emission: int
    tx_rate_limit: int
    vote_threshold: int
    vote_mode: str
    max_proposals: int
    max_name_length: int
    burn_rate: int
    min_burn: int
    min_stake: int
    min_weight_stake: int


class SubnetParams(TypedDict):
    name: str
    founder: Ss58Address
    founder_share: int
    immunity_period: int
    incentive_ratio: int
    max_allowed_uids: int
    max_allowed_weights: int
    min_allowed_weights: int
    max_stake: int
    min_stake: int
    tempo: int
    self_vote: bool
    trust_ratio: int
    vote_mode: str
    vote_threshold: int
    max_weight_age: int


# redundant "TypedDict" inheritance because of pdoc warns.
# see https://github.com/mitmproxy/pdoc/blob/26d40827ddbe1658e8ac46cd092f17a44cf0287b/pdoc/doc.py#L691-L692
class SubnetParamsWithEmission(SubnetParams, TypedDict):
    """SubnetParams with emission field.
    """
    emission: int
    """Subnet emission percentage (0-100).
    """
