from monstr.client.client import Client
from monstr.client.event_handlers import EventAccepter
from monstr.event.event import Event
from monstr.encrypt import Keys


class AuthListAccept(EventAccepter):
    """
        basic auth acceptor that will only return True if evt pub_k is in accept_pub_k
        this could come from file or better a nostr list event (we could then watch for updates of the list)
    """
    def __init__(self, accept_pub_k: [str | Keys] = None):
        self._accept = accept_pub_k
        if self._accept is not None:
            self._accept = self._get_keys(self._accept)

    def _get_keys(self, key_list: []) -> set:
        ret = set()
        for c_i in key_list:
            k = c_i
            if not isinstance(k, Keys):
                k = Keys.get_key(k)
            if k is not None:
                ret.add(k.public_key_hex())

        print(ret)
        return ret



    def accept_event(self, the_client: Client, sub_id: str, evt: Event) -> bool:
        print(self._accept, evt.pub_key)
        ret = False
        if self._accept is None or evt.pub_key in self._accept:
            ret = True
        return ret
