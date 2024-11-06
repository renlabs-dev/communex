from typing import Protocol

from communex.errors import PasswordNotProvidedError


class PasswordProvider(Protocol):
    def get_password(self, key_name: str) -> str | None:
        """
        Provides a password for the given key name, if it is know. If not,
        returns None. In that case, `ask_password` can be called to ask for the
        password depending on the implementation.
        """
        return None

    def ask_password(self, key_name: str) -> str:
        """
        Either provides a password for the given key or raises an
        PasswordNotProvidedError error.
        """
        raise PasswordNotProvidedError(
            f"Password not provided for key '{key_name}'"
        )


class NoPassword(PasswordProvider):
    pass


class Password(PasswordProvider):
    def __init__(self, password: str):
        self._password = password

    def get_password(self, key_name: str) -> str:
        return self._password

    def ask_password(self, key_name: str) -> str:
        return self._password
