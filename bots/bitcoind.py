import logging
import json
from abc import ABC
import asyncio
import aiohttp
from aiohttp import ClientSession
from monstr.client.client import Client, ClientPool
from monstr.client.event_handlers import EventAccepter
from monstr.event.event import Event
from monstr.encrypt import Keys
from bots.basic import BotEventHandler, CommandMapper


class Bitcoind_rpc:

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
                    if resp.status != 200:
                        logging.debug(f'Bitcoind_rpc:: execute_cmd failed method- {method} params - {params} status {resp.status}')

                    ret = json.loads(await resp.text())

        except Exception as e:
            ret = {
                'error': str(e)
            }

        return ret

    async def getnewaddress(self):
        return await self._execute_cmd('getnewaddress',{})

    async def listtransactions(self):
        return await self._execute_cmd('listtransactions',{})


class Bitcoind_CommandMapper(CommandMapper, ABC):

    def __init__(self, bitcoind: Bitcoind_rpc):
        self._rpc = bitcoind
        super().__init__({
            'getnewaddress': self.getnewaddress,
            'listtransactions': self.listtransactions,
            'claim': self.claim
        })

    def is_cmd_auth(self, name, pub_k: str) -> bool:
        return True

    async def getnewaddress(self, args):
        return await self._rpc.getnewaddress()

    async def listtransactions(self, args):
        return await self._rpc.listtransactions()

    async def claim(self):
        pass


class Bitcoind_Bot(BotEventHandler):

    def __init__(self,
                 as_user: Keys,
                 clients: ClientPool,
                 bitcoin_rpc: Bitcoind_rpc,
                 kind: int = Event.KIND_TEXT_NOTE,
                 encrypt: bool = None,
                 inbox: Keys = None,
                 event_acceptors: [EventAccepter] = None):

        self._rpc = bitcoin_rpc

        super().__init__(as_user=as_user,
                         clients=clients,
                         kind=kind,
                         encrypt=encrypt,
                         inbox=inbox,
                         event_acceptors=event_acceptors,
                         command_map=Bitcoind_CommandMapper(bitcoin_rpc))

