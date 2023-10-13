import logging
import asyncio
import aiohttp
import json
from abc import ABC, abstractmethod
from aiohttp import ClientSession
from datetime import datetime
from monstr.client.client import Client, ClientPool
from monstr.client.event_handlers import EventHandler,DeduplicateAcceptor
from monstr.event.event import Event
from monstr.encrypt import Keys
from monstr.util import util_funcs

# default relay if not otherwise given
# DEFAULT_RELAY = 'wss://nostr-pub.wellorder.net,wss://nos.lol'
DEFAULT_RELAY = 'ws://localhost:8081'
# DEFAULT_RELAY = 'wss://nostr-pub.wellorder.net'
# bot account priv_k - to remove hardcode
USE_KEY = 'nsec1fnyygyh57chwf7zhw3mwmrltc2hatfwn0hldtl4z5axv4netkjlsy0u220'
# what kind to use - probably you what something in the NIP16 emphereal range
USE_KIND = 20888
# for connecting to bitcoind
BITCOIND_NETWORK = 'test'            #   not yet used have to manually change port
BITCOIND_USER = 'monty'              #
BITCOIND_PASSWORD = 'Fl09q6kMFioOKyICCtXY5CJ082aawgS4SrIGFC7yxGE=' # to remove also

# this needs proper config based on bitcoin_netowrk which we're not using yet
BITCOIND_WALLET = 'test'
BITCOIND_HOST = 'http://localhost'
BITCOIND_PORT = 8332
# BITCOIND_PORT = 18332
BITCOIND_URL = f'{BITCOIND_HOST}:{BITCOIND_PORT}/wallet/{BITCOIND_WALLET}'


def get_args():
    return {
        'relays': DEFAULT_RELAY,
        'bot_account': Keys(USE_KEY),
        'use_kind': USE_KIND,
        'bitcoind_url': BITCOIND_URL,
        'bitcoind_user': BITCOIND_USER,
        'bitcoind_password': BITCOIND_PASSWORD
    }


class CommandMapper(ABC):

    def __init__(self, command_map: dict):
        self._command_map = command_map

    def is_command(self, name: str) -> bool:
        return name in self._command_map

    @abstractmethod
    def is_cmd_auth(self, name, pub_k: str) -> bool:
        pass

    async def do_command(self, name: str, args: []) -> dict:
        return await self._command_map[name](args)


class BotEventHandler(EventHandler):

    def __init__(self,
                 as_user: Keys,
                 clients: ClientPool,
                 command_map: CommandMapper,
                 kind: int,
                 encrypt: bool):
        self._as_user = as_user
        self._clients = clients
        self._store = None

        self._command_map = command_map

        self._kind = kind

        self._encrypt = encrypt

        super().__init__(event_acceptors=[DeduplicateAcceptor()])

    def _make_reply_tags(self, src_evt: Event) -> []:
        """
            minimal tagging just that we're replying to sec_evt and tag in the creater pk so they see our reply
        """
        return [
            ['p', src_evt.pub_key],
            ['e', src_evt.id, 'reply']
        ]

    def do_event(self, the_client: Client, sub_id, evt: Event):
        # replying to ourself would be bad! also call accept_event
        # to stop us replying mutiple times if we see the same event from different relays
        if evt.pub_key == self._as_user.public_key_hex() or \
                self.accept_event(the_client, sub_id, evt) is False:
            return

        logging.debug('BotEventHandler::do_event - received event %s' % evt)

        # is this a key we reply to?
        if not self.auth_any(evt):
            return

        # ok lets see if its a
        self.do_command(evt)

    def auth_any(self, evt: Event) -> bool:
        # auth check on basic event, do we even bother responding to this user?
        return True

    # TOOD: move the mapping of commands out in someway so that you just pass in a class
    # with the command mappings or something similar
    def do_command(self, evt: Event):
        cmd_text = evt.content

        if self._encrypt:
            cmd_text = Event.decrypt_nip4(evt=evt,
                                          keys=self._as_user,
                                          check_kind=False).content

        cmd_split = cmd_text.split()

        if not cmd_split:
            self.do_response('no command given?!', evt)

        cmd = cmd_split[0]
        args = cmd_split[1:]
        if not self._command_map.is_command(cmd):
            self.send_response(response={
                    'error': f'command not understood - {cmd}'
                },
                prompt_evt=evt)
        elif not self._command_map.is_cmd_auth(cmd, evt.pub_key):
            self.send_response(response={
                    'error': f'key: {evt.pub_key} not authorised cmd: {cmd}'
                },
                prompt_evt=evt)
        else:
            # call the command
            asyncio.create_task(self.do_response_cmd(prompt_evt=evt,
                                                     cmd=cmd,
                                                     args=args))

    async def do_response_cmd(self, prompt_evt: Event, cmd, args):
        self.send_response(response=await self._command_map.do_command(cmd, args),
                           prompt_evt=prompt_evt)

    def send_response(self, response: dict, prompt_evt: Event):

        response_evt = Event(kind=self._kind,
                             content=json.dumps(response),
                             tags=[
                                 ['p', self._as_user.public_key_hex()],
                                 ['p', prompt_evt.pub_key],
                                 ['e', prompt_evt.id]
                             ],
                             pub_key=self._as_user.public_key_hex())
        if self._encrypt:
            response_evt.content = response_evt.encrypt_content(priv_key=self._as_user.private_key_hex(),
                                                                pub_key=prompt_evt.pub_key)

        response_evt.sign(self._as_user.private_key_hex())
        self._clients.publish(response_evt)


from bots.echo import EchoBot
from bots.bitcoind import Bitcoind_Bot, Bitcoind_rpc

# def BasicBot(BotEventHandler):
#     pass

async def main(args):
    # just the keys, change to profile?
    as_user = args['bot_account']

    # relays we'll watch
    relays = args['relays']

    # bitcoin rpc stuff
    bitcoin_url = args['bitcoind_url']
    bitcoin_user = args['bitcoind_user']
    bitcoin_password = args['bitcoind_password']

    # kind we'll use for msgs
    use_kind = args['use_kind']


    # the actually clientpool obj
    my_clients = ClientPool(clients=relays.split(','),
                            ssl=False)

    # do_event of this class is called on recieving events that match teh filter we reg for
    # my_handler = BotEventHandler(as_user=as_user,
    #                              clients=my_clients,
    #                              command_map=Bitcoind_CommandMapper(bitcoind=Bitcoind_rpc(
    #                                  url=bitcoin_url,
    #                                  user=bitcoin_user,
    #                                  password=bitcoin_password
    #                              )),
    #                              kind=use_kind,
    #                              encrypt=True)

    my_handler = Bitcoind_Bot(as_user=as_user,
                              clients=my_clients,
                              bitcoin_rpc=Bitcoind_rpc(
                                  url=bitcoin_url,
                                  user=bitcoin_user,
                                  password=bitcoin_password
                              ))

    # my_handler = EchoBot(as_user=as_user,
    #                      clients=my_clients)

    # called on first connect and any reconnects, registers our event listener
    def on_connect(the_client: Client):
        the_client.subscribe(sub_id='bot_watch',
                             handlers=[my_handler],
                             filters={
                                 'kinds': [1],
                                 '#p': [as_user.public_key_hex()],
                                 'since': util_funcs.date_as_ticks(datetime.now())
                             })
    # add the on_connect
    my_clients.set_on_connect(on_connect)

    # start the clients
    print('monitoring for events from or to account %s on relays %s' % (as_user.public_key_hex(),
                                                                        relays))
    await my_clients.run()








async def test():

    to_url = 'http://localhost:8332/wallet/cormorant'
    user = 'monty'
    password = 'GET_FROM_CONGIG'

    try:
        async with ClientSession() as session:
            async with session.post(
                    url=to_url,
                    data=json.dumps({
                        'method': 'getwalletinfo',
                        'params': {
                            # 'filename': 'test'
                        }
                        # probably should send but doesn't cause issue that we don't....
                        # 'jsonrpc': '2.0',
                        # 'id': 1
                    }),
                    auth=aiohttp.BasicAuth(user, password)
            ) as resp:
                if resp.status == 200:
                    resp = json.loads(await resp.text())
                    for i in resp:
                        print(i, resp[i])
                else:
                    print('sendrawtransaction_bitcoind::post %s - bad status %s' % (to_url, resp.status))
                    print(await resp.text())

    except Exception as e:
        print(e)


# def run_test_server():
#     """
#     fucking webrowsers module, can't test just using file:// because js modules so will have to run a basic
#     web server for testing
#     :return:
#     """
#     from aiohttp import web
#     app = web.Application()
#
#     app.add_routes([web.static('/html', '/home/monty/bitcoinbot/web/html/')])
#     app.add_routes([web.static('/script/', '/home/monty/bitcoinbot/web/script/')])
#
#     web.run_app(app)

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    asyncio.run(main(get_args()))
    # run_test_server()

