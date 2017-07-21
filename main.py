import json
import operator
import csv
import string
from collections import defaultdict

from ethereum.abi import ContractTranslator, decode_abi
from pyethapp.rpc_client import JSONRPCClient
from pyethapp.jsonrpc import quantity_encoder

from constants import wallet_abi
host = "127.0.0.1"
port = 8545
WHITEHAT = "0x1dba1131000664b884a1ba238464159892252d3a"
printable = set(string.printable)


class TokenHolder():

    def __init__(self, filename):
        self.tokens = self.load_tokens(filename)

    def load_tokens(self, filename):
        with open(filename, 'r') as f:
            tokens = json.loads(f.read())

        self.tokens_list = tokens
        cleaned_tokens = dict()
        for token in tokens:
            cleaned_tokens[token['address'].lower()] = token

        return cleaned_tokens

    def address_is_token(self, address):
        if not address.startswith('0x'):
            address = '0x' + address

        address = address.lower()
        token_name = None
        if address in self.tokens:
            token_name = self.tokens[address]['symbol']

        return token_name


class Mapping():

    def __init__(self, tokens):
        self.mapping = dict()
        self.tokens = tokens

    def add_eth(self, address, value):
        if address not in self.mapping:
            self.mapping[address] = dict()
            self.mapping[address]['ether'] = value
        else:
            self.mapping[address]['ether'] = self.mapping[address]['ether'] + value

    def add_token(self, address, token_name, value):
        if address not in self.mapping:
            self.mapping[address] = dict()
            self.mapping[address][token_name] = value
        else:
            self.mapping[address][token_name] = self.mapping[address][token_name] + value

    def output_to_csv(self, name):
        with open(name, 'wb') as f:
            w = csv.writer(f)
            header_row = ['multisig_address', 'amount_in_wei']
            for token_data in self.tokens.tokens_list:
                # need to get rid of unicode chars in some token symbols. *cough* beercoin *cough*
                header_row.append(filter(lambda x: x in printable,token_data['symbol']))

            w.writerow(header_row)
            data = list()
            for address, map_data in self.mapping.iteritems():
                entry = [address, map_data['ether']]
                for token_data in self.tokens.tokens_list:
                    if token_data['symbol'] in self.mapping[address]:
                        decimal = 18 - token_data['decimal']
                        value = self.mapping[address][token_data['symbol']] / (10 ** decimal)
                        entry.append(value)
                    else:
                        entry.append(0)
                data.append(tuple(entry))

            sorted_data = sorted(data, key=lambda tup: tup[1], reverse=True)
            w.writerows(sorted_data)


class Client():

    def __init__(self, tokens):
        self.client = JSONRPCClient(
            privkey=None,
            host=host,
            port=port,
            print_communication=False,
        )
        self.wallet_translator = ContractTranslator(wallet_abi)
        self.tokens = tokens

    def get_block(self, num):
        return self.client.call(
            'eth_getBlockByNumber',
            quantity_encoder(num),
            True
        )

    def get_transaction(self, hash):
        return self.client.eth_getTransactionByHash(hash)

    def decode_token_transfer(self, txdata, to_address):
        if len(txdata) < 8 or txdata[:8] != 'a9059cbb':
            return None, None

        # get rid of signature
        txdata = txdata[8:]

        # here we got ourselves a token transfer
        # transfer(address _from, uint256 _value)
        token_name = self.tokens.address_is_token(to_address)
        if token_name is None:
            print('WARNING: Unknown token {} transferred'.format(to_address))
            return None, None

        hexdata = txdata.decode('hex')
        transfer_to = decode_abi(['address'], hexdata[:32])[0]
        transfer_value = decode_abi(['uint256'], hexdata[32:])[0]

        if '0x' + transfer_to != WHITEHAT:
            print('WARNING: {} token sent to non-whitehat address'.format(token_name))

        return transfer_value

    def decode_execute(self, txdata):
        # get rid of signature and 0x
        txdata = txdata[10:]

        # unfortunately the pyethapp way does not work
        # fndata = c.wallet_translator.function_data['execute']
        # return decode_abi(fndata['encode_types'], txdata.decode('hex'))

        # ... but decoding each arg individually does work
        sent_to = decode_abi(['address'], txdata.decode('hex')[:32])[0]
        amount_in_wei = decode_abi(['uint256'], txdata.decode('hex')[32:64])[0]

        token_value = self.decode_token_transfer(txdata[256:], sent_to)

        return sent_to, amount_in_wei, token_value


if __name__ == "__main__":
    tokens = TokenHolder('tokens.json')
    c = Client(tokens)
    mapping = Mapping(tokens)

    start_block = 4044976
    # end_block = 4048770
    end_block = start_block + 100
    blocknum = start_block
    print('Verification Started')
    while blocknum <= end_block:
        print('Processing block: {}'.format(blocknum))

        transactions = c.get_block(blocknum)['transactions']
        for tx in transactions:
            is_whitehat_execute = (
                (tx['from'] == WHITEHAT or tx['to'] == WHITEHAT) and
                tx['input'].startswith('0xb61d27f6')
            )
            if is_whitehat_execute:
                sent_to, wei, token_from, token_value = c.decode_execute(tx['input'])
                if token_from is None:
                    mapping.add_eth(tx['to'], wei)
                else:
                    mapping.add_token(sent_to, token_value)

        blocknum += 1

    filename = 'multisig_data.csv'
    mapping.output_to_csv(filename)
    print('Verification ended. Written file: {}'.format(filename))
