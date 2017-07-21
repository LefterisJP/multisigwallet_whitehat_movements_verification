import json
import operator
import csv
from collections import defaultdict

from ethereum.abi import ContractTranslator, decode_abi
from pyethapp.rpc_client import JSONRPCClient
from pyethapp.jsonrpc import quantity_encoder

from constants import wallet_abi
host = "127.0.0.1"
port = 8545


def output_to_csv(name, data):
    with open(name, 'wb') as f:
        w = csv.writer(f)
        w.writerow(['multisig_address', 'amount_in_wei'])
        sorted_by_value = sorted(
            data.items(),
            key=operator.itemgetter(1),
            reverse=True
        )
        w.writerows(sorted_by_value)


class TokenHolder():

    def __init__(self, filename):
        self.tokens = self.load_tokens(filename)

    def load_tokens(self, filename):
        with open(filename, 'r') as f:
            tokens = json.loads(f.read())

        cleaned_tokens = dict()
        for token in tokens:
            cleaned_tokens[token['address'].lower()] = token

        return cleaned_tokens

    def address_is_token(self, address):
        address = address.lower()
        token_name = None
        if address in self.tokens:
            token_name = self.tokens[address]

        return token_name


class Client():

    def __init__(self):
        self.client = JSONRPCClient(
            privkey=None,
            host=host,
            port=port,
            print_communication=False,
        )
        self.wallet_translator = ContractTranslator(wallet_abi)

    def get_block(self, num):
        return self.client.call(
            'eth_getBlockByNumber',
            quantity_encoder(num),
            True
        )

    def decode_execute(self, txdata):
        # get rid of signature and 0x
        txdata = txdata[10:]

        # unfortunately the pyethapp way does not work
        # fndata = c.wallet_translator.function_data['execute']
        # return decode_abi(fndata['encode_types'], txdata.decode('hex'))

        # ... but decoding each arg individually does work
        sent_to = decode_abi(['address'], txdata.decode('hex')[:32])[0]
        amount_in_wei = decode_abi(['uint256'], txdata.decode('hex')[32:64])[0]

        # Reason pyethapp full decoding does not work is for some input
        # the bytes decoding fails with
        # AssertionError: Wrong data size for string/bytes object
        # TODO: Report bug ...
        try:
            data = decode_abi(['bytes'], txdata.decode('hex')[64:])[0]
        except:
            data = ''
        #     import pdb
        #     pdb.set_trace()

        return sent_to, amount_in_wei, data


if __name__ == "__main__":
    c = Client()
    tokens = TokenHolder('tokens.json')

    whitehat = "0x1dba1131000664b884a1ba238464159892252d3a"
    start_block = 4044976
    end_block = 4048770
    blocknum = start_block
    mapping = defaultdict(int)
    print('Verification Started')
    while blocknum <= end_block:
        print('Processing block: {}'.format(blocknum))

        transactions = c.get_block(blocknum)['transactions']
        for tx in transactions:
            is_whitehat_execute = (
                (tx['from'] == whitehat or tx['to'] == whitehat) and
                tx['input'].startswith('0xb61d27f6')
            )
            if is_whitehat_execute:
                sent_to, wei, data = c.decode_execute(tx['input'])
                mapping[tx['to']] += wei

        blocknum += 1

    filename = 'multisig_data.csv'
    output_to_csv(filename, mapping)
    print('Verification ended. Written file: {}'.format(filename))
