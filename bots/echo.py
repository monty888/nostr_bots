from monstr.client.client import Client
from monstr.event.event import Event
from bots.basic import BotEventHandler


class EchoBot(BotEventHandler):

    async def make_response(self, client: Client, sub_id, evt: Event) -> Event:
        ret = self.get_reply_event(evt)
        ret.content = evt.content
        return ret

