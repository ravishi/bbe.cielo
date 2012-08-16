# -*- coding: utf-8 -*-
import uuid
import urllib2
import contextlib
from bbe.cielo import message
from bbe.cielo.schema import (
    SERVICE_VERSION,
    Error,
    Transaction,
    TransactionRequestSchema,
)


class CommunicationError(urllib2.URLError):
    """This exception is raised when the communication between
    our client and the remote service fail.

    .. attribute:: reason

        The error reason. It can be a message or an instance of
        another exception.
    """


class UnknownResponse(Exception):
    """This is raised when our client don't know how to handle
    the response.
    """


class Client(object):
    def __init__(self, store_id, store_key, service_url=None):
        self.store_id = store_id
        self.store_key = store_key
        self.service_url = service_url

    def generate_transaction_id(self):
        return str(uuid.uuid4())

    def create_transaction(self, order, payment, authorize, capture, card=None, return_url=None):
        appstruct = {
            'id': self.generate_transaction_id(),
            'version': SERVICE_VERSION,
            'establishment': {
                'number': self.store_id,
                'key': self.store_key,
            },
            'order': order.serialize(),
            'payment': payment.serialize(),
            'return_url': return_url,
            'authorize': authorize,
            'capture': capture,
        }

        if card is not None:
            appstruct['holder'] = card.serialize()
            appstruct['bin'] =  card.number[:6]

        schema = TransactionRequestSchema(tag='requisicao-transacao')

        cstruct = schema.serialize(appstruct)
        request = message.serialize(schema, cstruct)
        request = message.dumps(request)
        return self.post_request(request)

    def post_request(self, request):
        msg = u"mensagem=" + request

        try:
            request = urllib2.urlopen(self.service_url, msg)
            with contextlib.closing(request) as response:
                response = response.read()
        except urllib2.URLError, e:
            raise CommunicationError(e.reason)

        return self.process_response(response)

    def process_response(self, response):
        response = message.loads(response)
        root_tag = message.get_root_tag(response)

        if root_tag == 'erro':
            response_cls = Error
        elif root_tag == 'transacao':
            response_cls = Transaction
        else:
            # TODO shouldn't this be named UnexpectedResponse
            raise UnknownResponse("Unknown response type '%s'" % root_tag)

        schema = response_cls.__schema__
        cstruct = message.deserialize(schema, response)
        appstruct = schema.deserialize(cstruct)

        return response_cls.from_appstruct(appstruct)
