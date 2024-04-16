# CommuneX

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Discord Chat](https://img.shields.io/badge/discord-join%20chat-blue.svg)](https://go.agicommies.org/commune-discord)
[![PyPI version](https://badge.fury.io/py/communex.svg)](https://pypi.org/project/communex/)

- [Why CommuneX](#why-communex)
- [Installation with `pip`](#installation-with-pip)
- [Installation with Nix](#installation-with-nix)
- [Features](#features)
  - [Planned](#planned)
- [CLI Usage](#cli-usage)
  - [Examples](#examples)
  - [Completions](#completions)
- [Contributing](#contributing)
- [Commune compatibility](#commune-compatibility)

## Why CommuneX

CommuneX serves as an alternative library/SDK to the original [Commune
Ai](https://github.com/commune-ai/commune) codebase, offering a streamlined and
user-friendly experience. It is designed for simplicity and scalable
development. To learn more [visit docs](https://docs.communex.ai/communex)

## Installation with `pip`

Requirements: Python 3.10+

Install the `communex` Python package directly with `pip`:

```sh
pip install communex
```

Or add it to your Poetry project with:

```sh
poetry add communex
```

## Installation with Nix

To install `communex` the communex cli with Nix
```sh
nix profile install .
```

## Features

- [x] Commands
  - [x] Key management
  - [x] Transfering and staking tokens
  - [x] Module management
  - [x] Client to interact with served modules
  - [x] Module class and server
  - [x] Governance participation 

### Planned

- [ ] Module API extraction and documentation generator

## CLI Usage

The CLI commands are structured as follows:

```sh
comx [OPTIONS] COMMAND [ARGS]
```

There are six top-level subcommands:

- **balance**: transfer, stake, unstake and showing balance operations
- **key**: creating, saving (AKA regenerating), listing and showing balance
  operations
- **module**: info, list, register, serve, update
- **network**: block, parameters, proposals / proposing, voting operations
- **subnet**: info, list, update
- **misc**: apr, circulating supply

```sh
comx subcommand [OPTIONS] COMMAND [ARGS]...
```

### Examples

#### Retrieving Balance

```sh
# Show staked, free and total balance.
comx balance show 5FgfC2DY4yreEWEughz46RZYQ8oBhHVqD9fVq6gV89E6z4Ea 
```

#### Creating a Key

```sh
comx key create key_name
```

#### Retrieving Key Info

```sh
comx key show key_name

# Add the `--show-private` flag to show sentitive fields like private key.
comx key show key_name --show-private
```

#### Listing Keys

```sh
# Lists the names and addresses of keys stored on disk.
comx key list 
```

#### List Keys With Balances

```sh
# Lists keys stored on disk with their balance (free, staked and total).
comx key balances
```

#### Retrieving Module Information

```sh
# Note that the module has to be registered on the network.
comx module info vali::calc [--balance] 
```

#### Retrieving Global Parameters

```sh
comx network params
```

#### Retrieving Subnet Parameters

```sh
comx subnet list
```

#### Retrieving Circulating Supply

```sh
# Gets all tokens then were ever emitted minus burned tokens.
comx misc circulating-supply 
```

### Completions

You can enable completions for your shell by running:

```sh
# On bash
comx --install-completion bash
# On zsh
comx --install-completion zsh
```

## Contributing

Bug reports and pull requests and other forms of contribution are welcomed and
encouraged!  :)

To report a bug or request a feature, please [open an issue on GitHub].

If you have any questions, feel free to ask on the [CommuneX Discord channel] or
post on our [GitHub discussions page].

To contribute to the codebase, using Poetry you can install the development dependencies with:

```sh
poetry install --with dev
```

it can [require some enviroment-specific binaries to be installed][ruff-installation]

## Commune compatibility

Yes, `communex` is compatible with the `commune` library/CLI. However, there are
important considerations to note. `communex` verifies the integrity of your
keys, which means that mixing certain types of keys is not permissible.
Specifically, if you possess node keys or other similar types that are not
designed to receive tokens, you to relocate them outside of the key
directory.

---

[open an issue on GitHub]: https://github.com/agicommies/communex/issues/new/choose
[CommuneX Discord channel]: https://go.agicommies.org/communex-channel
[GitHub discussions page]: https://github.com/agicommies/communex/discussions
[ruff-installation]: https://docs.astral.sh/ruff/installation/
