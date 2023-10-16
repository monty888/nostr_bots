import logging
import asyncio
from datetime import datetime
import signal
import sys
from monstr.exception import ConfigurationError
from monstr.client.client import Client, ClientPool
from monstr.event.event import Event
from monstr.util import util_funcs
from monstr.encrypt import Keys
from bots.basic import BotEventHandler


# default relay
DEFAULT_RELAY = 'ws://localhost:8081'
# default key - if None it'll be generated each run
USE_KEY = 'nsec1fnyygyh57chwf7zhw3mwmrltc2hatfwn0hldtl4z5axv4netkjlsy0u220'


class IPBot(BotEventHandler):

    async def make_response(self, client: Client, sub_id, evt: Event) -> Event:
        ret = self.get_reply_event(evt)

        # any shell method to get ip will do us, we'll use curl - hopefully it exists
        proc = await asyncio.create_subprocess_exec(
            'dig', '@resolver4.opendns.com', 'myip.opendns.com', '+short',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        ret.content = stdout.decode()
        return ret


def get_args() -> dict:
    ret = {
        'keys': USE_KEY,
        'relays': DEFAULT_RELAY
    }

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

    # kinds will reply to
    kind = Event.KIND_ENCRYPT

    # actually create the client pool
    def on_connect(the_client: Client):
        the_client.subscribe(sub_id='bot_watch',
                             handlers=[bot],
                             filters={
                                 'kinds': [kind],
                                 '#p': [keys.public_key_hex()],
                                 'since': util_funcs.date_as_ticks(datetime.now())
                             })

    clients = ClientPool(clients=relays.split(','),
                         on_connect=on_connect)

    # actually create the bot
    bot = IPBot(keys=keys,
                clients=clients,
                encrypt_kinds=[])

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
