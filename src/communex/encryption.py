import struct

import cryptography.hazmat.primitives.serialization as crypt_serialization
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# def int_from_hex_bytes_be(data: str) -> int:
#     # return int.from_bytes(bytes.fromhex(data), 'big')
#     return int(data, 16)


def bytes_from_hex(data: str) -> bytes:
    return bytes.fromhex(data)


def encrypt_weights(
    key: tuple[bytes, bytes],
    data: list[tuple[int, int]],
    validator_key: list[int],
) -> bytes:
    # Create RSA public key
    public_numbers = rsa.RSAPublicNumbers(
        n=int.from_bytes(key[0], "big"),
        e=int.from_bytes(key[1], "big"),
    )
    rsa_key = public_numbers.public_key()

    # Encode data
    encoded = (
        (len(data)).to_bytes(4, "big")
        + b"".join(
            uid.to_bytes(2, "big") + weight.to_bytes(2, "big")
            for uid, weight in data
        )
        + bytes(validator_key)
    )

    # Calculate max chunk size
    max_chunk_size = rsa_key.key_size // 8 - 11  # 11 bytes for PKCS1v15 padding

    # Encrypt in chunks
    encrypted = b""
    for i in range(0, len(encoded), max_chunk_size):
        chunk = encoded[i : i + max_chunk_size]
        encrypted += rsa_key.encrypt(chunk, padding.PKCS1v15())

    return encrypted


def decrypt_weights(
    private_key: rsa.RSAPrivateKey, encrypted: bytes
) -> tuple[list[tuple[int, int]], list[int]] | None:
    # Decrypt in chunks
    decrypted = b""
    chunk_size = private_key.key_size // 8
    for i in range(0, len(encrypted), chunk_size):
        chunk = encrypted[i : i + chunk_size]
        try:
            decrypted += private_key.decrypt(chunk, padding.PKCS1v15())
        except InvalidSignature:
            return None

    # Read the decrypted data
    cursor = 0

    def read_u32() -> int | None:
        nonlocal cursor
        if cursor + 4 > len(decrypted):
            return None
        value = struct.unpack(">I", decrypted[cursor : cursor + 4])[0]
        cursor += 4
        return value

    def read_u16() -> int | None:
        nonlocal cursor
        if cursor + 2 > len(decrypted):
            return None
        value = struct.unpack(">H", decrypted[cursor : cursor + 2])[0]
        cursor += 2
        return value

    length = read_u32()
    if length is None:
        return None

    weights: list[tuple[int, int]] = []
    for _ in range(length):
        uid = read_u16()
        weight = read_u16()
        if uid is None or weight is None:
            return None
        weights.append((uid, weight))

    key = list(decrypted[cursor:])

    return weights, key


def _test():
    weights = [(1, 2), (3, 4)]
    validator_key = [11, 22, 33, 44]

    pub_key_n_hex = "d740d02640e98befc21238399205e9dba5b711d237d06df06cc2af6f92c39d76292e90c34d04939e3a3e18520482b762be6ae8859f0f9f13d075b000a8892bfc0225729bc9fcd84d2c4149347231557f4678241aaf3c080a47c33aa1f4c90aee7cacf694ddeebe9abbbf231a9fdba410afbbc8f7a3e9f776a26504ce4a1982e9"

    pub_key_e_hex = "010001"

    rsa_key_pem = b"""
-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQDXQNAmQOmL78ISODmSBenbpbcR0jfQbfBswq9vksOddikukMNN
BJOeOj4YUgSCt2K+auiFnw+fE9B1sACoiSv8AiVym8n82E0sQUk0cjFVf0Z4JBqv
PAgKR8M6ofTJCu58rPaU3e6+mru/Ixqf26QQr7vI96Pp93aiZQTOShmC6QIDAQAB
AoGBAIixPf2s5yLYZLPRRK34V2QGvlTw3ETeK/nFQEdoOhT6fnh1sbBtIZkvf1NO
clLYRjqKBZMlSXRJzu2NkT11rpm1hTTuc99w0SjZDHFpj0TppXtagmJYwHBYt5Ac
oNan6ALTlUbxEHtIj4rGghJAJBOVTq0pi8PdVgAQgq3cArUBAkEA2f9SFOmDWN7w
PO6yHZfj7e8i65W8v4HZXV/EWv3kCZW5KZsM3OBlqqx1txIljxF146C7ZpBLLQEK
ubVOqKqPsQJBAPzHBuczD6GziSbN9sjgj4sAxGwExp8Z747rxGVlB56ak68aqFt1
GDuwib0NIrrDUuGlQUKIWUm6amSwu/UJbLkCQDsZS8Bdmf0y20A5mdIKBoHPrdDe
VEA6zJnSx6G/aN3sWDleTntm3kkJ3hPWeJYzrpkaTxO8FJVLzgOQkpWJP9ECQQD1
q0EsRlX05BZx3k7w4D7h67b6/JFFY+GNV9qiaNRE8xqBXjkt2dnZeTQExtVwChFt
ODz6uqV8oG5yucmS1rwRAkA1KjcZDPBRZ05wlf8VZuJjWYIRbVx3PBpQJPbtW7Vg
fvRuW5JF+WZtGddyU4751JNNNhmwbwGmsmphy7EOHHaC
-----END RSA PRIVATE KEY-----
"""

    # encrypted_hex = "acb87f05bb9d8bd6fd91614a8cfe44bd383d5d27ddd44f58788dc01775123413157f4040dbf8be719c160df01bbc1ea01e321a929990c558c29deb89ca348ed049f04a3ad1470a914ea884114b2889a1f1dce2f42542167d85d129bba44b6f71e6bc197d048fbd0ea08d013d9279c26d675bb7fba63928fd2dc13f886879c629"
    # encrypted_ref = bytes_from_hex(encrypted_hex)

    # ======================================================================== #

    private_key = crypt_serialization.load_pem_private_key(
        rsa_key_pem, password=None
    )
    assert isinstance(private_key, rsa.RSAPrivateKey)
    pub_key_n = bytes_from_hex(pub_key_n_hex)
    pub_key_e = bytes_from_hex(pub_key_e_hex)

    encrypted = encrypt_weights((pub_key_n, pub_key_e), weights, validator_key)

    decrypted = decrypt_weights(private_key, encrypted)
    assert decrypted is not None
    (weights_dec, key_dec) = decrypted
    print(f"weights_dec = {weights_dec}")
    print(f"key_dec = {key_dec}")

    assert weights_dec == weights
    assert key_dec == validator_key


if __name__ == "__main__":
    _test()
