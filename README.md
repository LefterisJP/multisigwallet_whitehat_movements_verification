# What is this?

This is a repository containing code for an independent verification of the data concerning the whitehat movements on the 19th of July concerning the [Ethereum Parity wallet vulnerability](https://www.reddit.com/r/ethereum/comments/6obofq/a_modified_version_of_a_common_multisig_had_a/).

# How to run it?

Use python. I assume you know how to use it. Requirements are all the pyethereum/pyethapp stuff. Also you will need an ethereum node synced in the mainnet on the local host and with rpc open. You can tweak values in the script.

# What is the result?

A CSV file containing addresses of multisig wallets and the amount in WEI that was taken from them by the whitehat movements between `start_block` and `end_block`. This data considers `start_block` as `4044976` and `end_block` as `4048770`.
