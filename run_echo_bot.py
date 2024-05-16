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
from monstr.inbox import Inbox
from bots.basic import BotEventHandler


# default relay
DEFAULT_RELAY = 'ws://localhost:8081'
# default key - if None it'll be generated each run
USE_KEY = 'nsec1fnyygyh57chwf7zhw3mwmrltc2hatfwn0hldtl4z5axv4netkjlsy0u220'


class EchoBot(BotEventHandler):

    async def make_response(self, client: Client, sub_id, evt: Event) -> Event:
        ret = self.get_reply_event(evt)
        ret.content = evt.content
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
    kinds = [Event.KIND_TEXT_NOTE, Event.KIND_ENCRYPT]

    # test inbox
    inbox_k = Keys()
    print(inbox_k.private_key_bech32())
    # Note with an ibox you need to know who will contact you (that is provide view keys)
    # my_box = Inbox(keys=inbox_k)
    my_box = None


    # actually create the client pool
    def on_connect(the_client: Client):
        the_client.subscribe(sub_id='bot_watch',
                             handlers=[bot],
                             filters={
                                 'kinds': kinds,
                                 'since': util_funcs.date_as_ticks(datetime.now())
                             })

    clients = ClientPool(clients=relays.split(','),
                         on_connect=on_connect)



    # actually create the bot
    bot = EchoBot(keys=keys,
                  clients=clients,
                  inbox=my_box)

    # start the clients
    print(f'monitoring for events from or to account {keys.public_key_bech32()} on relays {relays}')
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
