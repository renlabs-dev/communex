# Communex

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Discord Chat](https://img.shields.io/badge/discord-join%20chat-blue.svg)](https://discord.com/invite/DgjvQXvhqf)
[![PyPI version](https://badge.fury.io/py/communex.svg)](https://pypi.org/project/communex/)

## Why Communex

Communex serves as an alternative library/SDK to the original [Commune
Ai](https://github.com/commune-ai/commune) codebase, offering a streamlined and
user-friendly experience. It is designed for simplicity and scalable development. Its
decentralized approach underlines the versatile and adaptive nature of the
Commune framework, catering to a broad range of machine learning and blockchain
applications.

## Installation

To add `communex` to your Poetry project, run:

```sh
poetry add communex
```

or install it directly with `pip` with:

```sh
pip install communex
```

## CLI Usage

You can install completions by:

```sh
comx --install-completion
comx --show-completion
source ~/.bashrc  # Reload Bash / Zsh configuration to take effect.
```

To navigate the cli, follow this structure:

```sh
comx [OPTIONS] COMMAND [ARGS]
```

There are six essential subcommands:

- **balance** transfer, stake, unstake, to showing balance operations
- **key** creating, saving (AKA regenerating), listing, to showing balance operations
- **module** info, list, register, serve, update
- **network** block, parameters, proposals / proposing, voting operations
- **subnet** info, list, update
- **misc** apr, circulating supply

```sh
comx subcommand [OPTIONS] COMMAND [ARGS]...
```

### Examples

#### Retrieving Balance

```sh
comx balance show 5FgfC2DY4yreEWEughz46RZYQ8oBhHVqD9fVq6gV89E6z4Ea [--netuid] [--unit]# Staked, free, total balance.
```

#### Creating a Key

```sh
comx key create key_name
```

#### Retrieving Key Info

```sh
comx key show [--private]
```

####  Listing Keys

```sh
comx key list # Lists the names and addresses on a disk.
```

#### List Keys With Balances

```sh
comx key balances [--netuid] [--unit] [sort-balance] # Lists keys stored on a disk with their balance (staked, free, sum), ability to sort by the different type of balance.
```

#### Retrieving Module Information

```sh
comx module info vali::calc [--balance] # Note that the module has to be registered on the network. Otherwise, an error will be thrown.
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
comx misc circulating-supply [--unit] # Gets all tokens then were ever emitted - burned
```
