import logging
import asyncio
from datetime import datetime
import signal
import sys
from pathlib import Path
from monstr.exception import ConfigurationError
from monstr.client.client import Client, ClientPool
from monstr.util import util_funcs
from monstr.encrypt import Keys
from monstr.signing import BasicKeySigner
from nostr_bots.bitcoind import BitcoindBot, BitcoindRPC
from src.nostr_bots.util import load_toml
from nostr_bots.acceptors import AuthListAccept


# working directory
WORK_DIR = f'{Path.home()}/.nostrpy/'
# config file
CONFIG_FILE = f'bitcoin_bot.toml'
# default relay
DEFAULT_RELAY = 'ws://localhost:8081'
# default key - if None it'll be generated each run
USE_KEY = 'nsec1fnyygyh57chwf7zhw3mwmrltc2hatfwn0hldtl4z5axv4netkjlsy0u220'

# for connecting to bitcoind
BITCOIND_NETWORK = 'test'            #   not yet used have to manually change port
# probably better this comes from the toml file....
BITCOIND_USER = None
BITCOIND_PASSWORD = None

# default bitcoind config
BITCOIND_WALLET = 'cormorant'
BITCOIND_HOST = 'http://localhost'
BITCOIND_PORT = 8332
# BITCOIND_PORT = 18332


def get_args() -> dict:
    ret = {
        'work-dir': WORK_DIR,
        'conf': CONFIG_FILE,
        'keys': USE_KEY,
        'relays': DEFAULT_RELAY,
        'bitcoind-host': BITCOIND_HOST,
        'bitcoind-wallet': BITCOIND_WALLET,
        'bitcoind-port': BITCOIND_PORT,
        'bitcoind-user': BITCOIND_USER,
        'bitcoind-password': BITCOIND_PASSWORD
    }

    # update from toml file
    ret.update(load_toml(ret['conf'], ret['work-dir']))

    # TODO - parse args cli
    # ret.update(get_cmdline_args(ret))

    use_keys = Keys.get_key(ret['keys'])
    if use_keys is None or use_keys.private_key_hex() is None:
        raise ConfigurationError(f'{ret["keys"]} bad key value or public key only')

    ret['keys'] = use_keys

    return ret


async def run_bot(args):
    # just the keys, change to profile?
    keys: Keys = args['keys']

    # relays we'll watch
    relays = args['relays']

    # bitcoin connection stuff - note this will probably become bitcoin_ after we add argparse
    bitcoin_host = args['bitcoind-host']
    bitcoin_port = args['bitcoind-port']
    # this should probably just be default wallet to use (or always expected passed in on call?)
    bitcoin_wallet = args['bitcoind-wallet']
    bitcoin_url = f'{bitcoin_host}:{bitcoin_port}/wallet/{bitcoin_wallet}'
    bitcoin_user = args['bitcoind-user']
    bitcoin_password = args['bitcoind-password']

    # actually create the client pool
    def on_connect(the_client: Client):
        watch_filter = {
             'kinds': [bot.kind],
             '#p': [keys.public_key_hex()],
             'since': util_funcs.date_as_ticks(datetime.now())
        }
        if bot.inbox:
            watch_filter = {
                'kinds': [bot.inbox.kind],
                'authors': [bot.inbox.pub_key],
                'since': util_funcs.date_as_ticks(datetime.now())
            }
        print(watch_filter)
        the_client.subscribe(sub_id='bot_watch',
                             handlers=[bot],
                             filters=watch_filter)

    clients = ClientPool(clients=relays.split(','),
                         on_connect=on_connect)

    # accept request from these keys - this could come from file/config
    # or even from monitoring a nostr list event
    my_accept = AuthListAccept([
        '5c4bf3e548683d61fb72be5f48c2dff0cf51901b9dd98ee8db178efe522e325f'
    ])


    inbox = None
    # need to get cmd
    # inbox = Inbox(keys=Keys.get_key('nsec1g6exndqqcrmwxrkhkn0d4xer9hvr3nmnd8umm4kf2ml7vrqvgl7qyccx5k'),
    #               use_kind=20888)
    # inbox.set_share_map(for_keys=keys,
    #                     to_keys=[Keys.get_key('npub1t39l8e2gdq7kr7mjhe053skl7r84ryqmnhvca6xmz780u53wxf0swj0fey')])


    # actually create the bot
    bot = BitcoindBot(signer=BasicKeySigner(keys),
                      clients=clients,
                      bitcoin_rpc=BitcoindRPC(
                          url=bitcoin_url,
                          user=bitcoin_user,
                          password=bitcoin_password
                      ),
                      inbox=inbox,
                      event_acceptors=[my_accept])

    # start the clients
    print(f'monitoring for events from or to account {keys.public_key_hex()} on relays {relays}')
    def sigint_handler(signal, frame):
        clients.end()
        sys.exit(0)

    signal.signal(signal.SIGINT, sigint_handler)
    await clients.run()


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    try:
        asyncio.run(run_bot(get_args()))
    except ConfigurationError as ce:
        print(ce)
