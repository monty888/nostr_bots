import logging
import json
from abc import ABC
import aiohttp
from aiohttp import ClientSession
from monstr.client.client import ClientPool
from monstr.signing import SignerInterface
from monstr.inbox import Inbox
from monstr.client.event_handlers import EventAccepter
from bots.basic import BotEventHandler, CommandMapper


class BitcoindRPC:

    def __init__(self,
                 url: str,
                 user: str,
                 password: str):

        self._url = url
        self._user = user
        self._password = password

    async def _execute_cmd(self, method, params):
        try:
            async with ClientSession() as session:
                print(self._url)
                async with session.post(
                        url=self._url,
                        data=json.dumps({
                            'method': method,
                            'params': params
                            # 'jsonrpc': '2.0',
                            # 'id': self._id
                        }),
                        auth=aiohttp.BasicAuth(self._user, self._password)
                ) as resp:
                    if resp.status == 200:
                        ret = json.loads(await resp.text())
                    else:
                        raise Exception(f'Bitcoind_rpc:: execute_cmd failed method- {method} params - {params} status {resp.status}')
                        # logging.debug(f'Bitcoind_rpc:: execute_cmd failed method- {method} params - {params} status {resp.status}')

        except Exception as e:
            ret = {
                'error': str(e)
            }

        return ret

    async def getbalances(self):
        return await self._execute_cmd('getbalances', {})

    async def getnewaddress(self):
        return await self._execute_cmd('getnewaddress',{})

    async def listtransactions(self):
        return await self._execute_cmd('listtransactions',{})

    async def listunspent(self):
        return await self._execute_cmd('listunspent',{})

    async def sendrawtransaction(self, hexstring: str):
        return await self._execute_cmd('sendrawtransaction', [hexstring])


class BitcoindCommandMapper(CommandMapper, ABC):

    def __init__(self, bitcoind: BitcoindRPC):
        self._rpc = bitcoind
        super().__init__({
            'getbalances': self.getbalances,
            'getnewaddress': self.getnewaddress,
            'listtransactions': self.listtransactions,
            'listunspent': self.listunspent,
            'sendrawtransaction' : self.sendrawtransaction
        })

    def is_cmd_auth(self, name, pub_k: str) -> bool:
        return True

    async def getbalances(self, args):
        return await self._rpc.getbalances()

    async def getnewaddress(self, args):
        return await self._rpc.getnewaddress()

    async def listtransactions(self, args):
        return await self._rpc.listtransactions()

    async def listunspent(self, args):
        return await self._rpc.listunspent()

    async def sendrawtransaction(self, args):
        return await self._rpc.sendrawtransaction(args[0])


class BitcoindBot(BotEventHandler):

    def __init__(self,
                 signer: SignerInterface,
                 clients: ClientPool,
                 bitcoin_rpc: BitcoindRPC,
                 kind: int = 20888,
                 inbox: Inbox = None,
                 event_acceptors: [EventAccepter] = None):

        self._rpc = bitcoin_rpc

        self._kind = kind

        super().__init__(signer=signer,
                         clients=clients,
                         kinds=[kind],
                         encrypt_kinds=[kind],
                         inbox=inbox,
                         event_acceptors=event_acceptors,
                         command_map=BitcoindCommandMapper(bitcoin_rpc))

    @property
    def kind(self):
        return self._kind

