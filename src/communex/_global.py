"""
These are global state variables.

Global variables are the root of all evil, so this is temporary.

TODO: Remove the global variable file.
"""

from communex.util import create_state_fn

get_use_testnet = create_state_fn(bool)
