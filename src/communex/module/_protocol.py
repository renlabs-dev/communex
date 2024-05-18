import datetime
import json
from typing import Any

from substrateinterface import Keypair  # type: ignore

from communex.types import Ss58Address
from ._signer import sign

def serialize(data: Any) -> bytes:
    txt = json.dumps(data)
    return txt.encode()


def iso_timestamp_now() -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    iso_now = now.isoformat()
    return iso_now


def create_headers(signature: bytes, my_key: Keypair, timestamp_iso: str):
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature.hex(),
        "X-Key": my_key.public_key.hex(),
        "X-Crypto": str(my_key.crypto_type),
        "X-Timestamp": timestamp_iso,
    }
    return headers


def create_request_data(
    my_key: Keypair,
    target_key: Ss58Address,
    params: Any
) -> tuple[bytes, dict[str, str]]:
    timestamp_iso = iso_timestamp_now()
    
    params["target_key"] = target_key

    request_data = {
        "params": params,
    }

    serialized_data = serialize(request_data)
    request_data["timestamp"] = timestamp_iso
    serialized_stamped_data = serialize(request_data)
    signature = sign(my_key, serialized_stamped_data)
    
    headers = create_headers(signature, my_key, timestamp_iso)
    
    return serialized_data, headers


def create_method_endpoint(host: str, port: str | int, method_name: str) -> str:
    return f"http://{host}:{port}/method/{method_name}"
