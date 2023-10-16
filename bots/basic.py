import logging
import asyncio
import json
from datetime import datetime
from abc import ABC, abstractmethod
from monstr.client.client import Client, ClientPool
from monstr.client.event_handlers import EventHandler, DeduplicateAcceptor, EventAccepter
from monstr.event.event import Event
from monstr.encrypt import Keys
from monstr.util import util_funcs


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
                 keys: Keys,
                 clients: ClientPool,
                 # default is to reply both to standard notes and nip 4 dms
                 kinds: [int] = [Event.KIND_TEXT_NOTE, Event.KIND_ENCRYPT],
                 # the encrypted kinds
                 encrypt_kinds: [int] = [Event.KIND_ENCRYPT],
                 inbox: Keys = None,
                 event_acceptors: [EventAccepter] = None,
                 command_map: CommandMapper = None):

        # keys the bot will use to recieve and send events
        self._keys = keys

        # the relays we're watching for events from and writing to
        # (can be a pool with different relays for reading to writing)
        self._clients = clients

        # the event kind/s we'll use to recieve message - and probably to write also default kind 1 text notes
        if isinstance(kinds, list):
            kinds = set(kinds)
        self._kinds = kinds

        # will we encrypt messages, default is only True for Event.KIND_ENCRYPT (NIP4) events
        if isinstance(encrypt_kinds, list):
            encrypt_kinds = set(encrypt_kinds)
        self._encrypt_kinds = encrypt_kinds

        # public inbox to use - not implemented yet
        self._inbox = inbox

        # acceptance code run before we'll accept and event, by default just de-duplication
        self._acceptors = [DeduplicateAcceptor()]
        if event_acceptors:
            self._acceptors = self._acceptors + event_acceptors

        # map commands to functions - if not given
        self._command_map = command_map

        super().__init__(event_acceptors=self._acceptors)

    @staticmethod
    def reply_tags(src_evt: Event) -> []:
        """
            returns the minimal reply tags that bot should make on an event its responding too
            TODO - make sure we deal with root reply correctly based on src_event
        """
        return [
            ['p', src_evt.pub_key],
            ['e', src_evt.id, 'reply']
        ]

    def do_event(self, client: Client, sub_id, evt: Event):
        # replying to ourself would be bad! also call accept_event
        # to stop us replying mutiple times if we see the same event from different relays
        if evt.pub_key == self._keys.public_key_hex() or \
                self.accept_event(client, sub_id, evt) is False \
                or evt.kind not in self._kinds:
            return

        logging.debug(f'BotEventHandler::do_event - received event {evt}')

        # authorisation can just be done via event_acceptor??
        # is this a key we reply to?
        # if not self.authorise(evt):
        #     return

        # decode/unwrap or whatever to get the actual event with the cmd in it
        req_event = self.get_request_event(evt)

        # fire of the task that actually create a response and send it
        asyncio.create_task(self.ado_response_event(client=client,
                                                    sub_id=sub_id,
                                                    evt=req_event))

    # def authorise(self, evt: Event) -> bool:
    #     # auth check on basic event, do we even bother responding to this user?
    #     return True

    def get_request_event(self, evt: Event) -> Event:
        ret = evt
        # TODO - add inbox unwrapping if required here

        # decrypt if required
        if evt.kind in self._encrypt_kinds:
            ret = Event.decrypt_nip4(evt=evt,
                                     keys=self._keys,
                                     check_kind=False)
        return ret

    def make_response_event(self, repsonse_evt: Event, prompt_evt: Event) -> Event:
        # should be the adding whatever we strip off during get cmd event
        ret = repsonse_evt
        # TODO - add inbox wrapping if required here

        # encrypt if required
        if repsonse_evt.kind in self._encrypt_kinds:
            ret.content = ret.encrypt_content(self._keys.private_key_hex(),
                                              pub_key=prompt_evt.pub_key)

        return ret

    async def ado_response_event(self, client: Client, sub_id, evt: Event) -> Event:
        # NOTE at this point is the decrypted and unwrapped event (if that was required)
        if self._command_map is None:
            response_evt = await self.make_response(client, sub_id, evt)
        else:
            response_evt = await self.make_response_cmd_map(client, sub_id, evt)

        # we have the response - this just encrypts/wraps for sending
        response_evt = self.make_response_event(response_evt, evt)

        # and actually send
        self.send_response(response_evt)

    def get_reply_event(self, prompt_evt: Event):
        # gets an empty reply event ready for us to set content - may also add tags
        return Event(
            # reply will be same kind that we recieved on
            kind=prompt_evt.kind,
            content='',
            tags=BotEventHandler.reply_tags(prompt_evt),
            pub_key=self._keys.public_key_hex(),
            created_at=util_funcs.date_as_ticks(datetime.now())
        )

    async def make_response(self, client: Client, sub_id, evt: Event) -> Event:
        ret = self.get_reply_event(evt)
        ret.content = 'BotEventHandler:: No CommandMapper? You should implement make_response in your bot'
        return ret

    def parse_command_event(self, evt):
        pass

    async def make_response_cmd_map(self, the_client: Client, sub_id, evt: Event) -> Event:
        cmd_text = evt.content
        cmd_split = cmd_text.split()
        response_text = 'no command given?!'

        if cmd_split:
            cmd = cmd_split[0]
            args = cmd_split[1:]
            if not self._command_map.is_command(cmd):
                response_text = json.dumps({
                    'error': f'command not understood - {cmd}'
                })
            elif not self._command_map.is_cmd_auth(cmd, evt.pub_key):
                response_text = json.dumps({
                    'error': f'command not understood - {cmd}'
                })
            else:
                response_text = json.dumps(await self._command_map.do_command(cmd, args))

        ret = self.get_reply_event(evt)
        ret.content = response_text
        return ret

    def send_response(self, response_evt: Event):
        response_evt.sign(self._keys.private_key_hex())
        self._clients.publish(response_evt)
