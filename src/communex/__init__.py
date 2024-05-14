"""
The CommuneX library package.

Submodules:
    * `communex.client`: A lightweigh yet faster client for the Commune network.
    * `.compat`: Compatibility layer for the *classic* `commune` library.
    * `.types`: CommuneX common types.
    * `.key`: Key related functions.

.. include:: ../../README.md
"""

import importlib.metadata

if not __package__:
    __version__ = "0.0.0"
else:
    __version__ = importlib.metadata.version(__package__)
