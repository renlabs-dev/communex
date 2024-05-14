from typing import TypedDict

import sr25519  # type: ignore
from substrateinterface import Keypair, KeypairType  # type: ignore
from substrateinterface.exceptions import ConfigurationError  # type: ignore

# Random key mnemonic for testing
TESTING_MNEMONIC = "electric suffer nephew rough gentle decline fun body tray account vital clinic"


def sign(keypair: Keypair, data: bytes) -> bytes:
    match keypair.crypto_type:
        case KeypairType.SR25519:
            signature: bytes = sr25519.sign(  # type: ignore
                (keypair.public_key, keypair.private_key), data)  # type: ignore
        case _:
            raise Exception(f"Crypto type {keypair.crypto_type} not supported")

    return signature  # type: ignore


def verify(
        pubkey: bytes,
        crypto_type: int,
        data: bytes,
        signature: bytes,
) -> bool:
    match crypto_type:
        case KeypairType.SR25519:
            crypto_verify_fn = sr25519.verify  # type: ignore
        case _:
            raise ConfigurationError("Crypto type not supported")

    verified: bool = crypto_verify_fn(signature, data, pubkey)  # type: ignore

    if not verified:
        # Another attempt with the data wrapped, as discussed in https://github.com/polkadot-js/extension/pull/743
        # Note: As Python apps are trusted sources on its own, no need to wrap data when signing from this lib
        verified: bool = crypto_verify_fn(  # type: ignore
            signature, b'<Bytes>' + data + b'</Bytes>', pubkey)

    return verified  # type: ignore


class SignDict(TypedDict):
    """
    DEPRECATED
    """
    data: str
    crypto_type: int
    signature: str
    address: str


def sign_with_metadate(keypair: Keypair, data: bytes):
    """
    DEPRECATED
    """
    signature = sign(keypair, data)
    sig_hex: str = signature.hex()
    return {
        'address': keypair.ss58_address,
        'crypto_type': keypair.crypto_type,
        'data': data.decode(),
        'signature': sig_hex,
    }
