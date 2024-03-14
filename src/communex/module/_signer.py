import json
from typing import Any, TypedDict

from substrateinterface import Keypair, KeypairType  # type: ignore

import sr25519  # type: ignore
from scalecodec.base import ScaleBytes  # type: ignore
from scalecodec.utils.ss58 import ss58_decode  # type: ignore
from substrateinterface.exceptions import ConfigurationError # type: ignore
import ed25519_zebra  # type: ignore
import sr25519  # type: ignore
from substrateinterface.utils.ecdsa_helpers import (  # type: ignore
    ecdsa_sign, ecdsa_verify)


# random mnemonic for testing
TESTING_MNEMONIC = "electric suffer nephew rough gentle decline fun body tray account vital clinic"



class SignDict(TypedDict):
    data: str
    crypto_type: int
    signature: str
    address: str


def serialize(data: Any) -> bytes:
    txt = json.dumps(data)
    return txt.encode()

def sign(keypair: Keypair, data: bytes) -> bytes:
    match keypair.crypto_type:
        case KeypairType.SR25519:
            signature: bytes = sr25519.sign(  # type: ignore
                (keypair.public_key, keypair.private_key), data)  # type: ignore
        case _:
            raise Exception(f"Crypto type {keypair.crypto_type} not supported")

    return signature  # type: ignore

def sign_to_dict(keypair: Keypair, data: bytes) -> SignDict:

    signature = sign(keypair, data)

    sig_hex: str = signature.hex()

    return {
        'data': data.decode(),
        'crypto_type': keypair.crypto_type,
        'signature': sig_hex,
        'address': keypair.ss58_address,
    }


def sign_with_metadate(keypair: Keypair, data: bytes):
    signature = sign(keypair, data)
    sig_hex: str = signature.hex()
    return {
        'address': keypair.ss58_address,
        'crypto_type': keypair.crypto_type,
        'data': data.decode(),  # TODO: this might fail depending on the string? use b64?
        'signature': sig_hex,
    }