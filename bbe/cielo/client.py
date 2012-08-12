# -*- coding: utf-8 -*-
import uuid
import urllib2
import contextlib
from bbe.cielo import message
from bbe.cielo.schema import (
    TransactionRequestSchema,
    INFORMADO,
    INEXISTENTE,
    DEBITO,
    CREDITO_A_VISTA,
    PARCELADO_ADMINISTRADORA,
    guess_response_schema,
    DebitPayment,
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

    def create_transaction(self, order, payment,  authorize, capture, return_url=None):
        if payment.card_security_code is None:
            code_indic = INEXISTENTE
        else:
            code_indic = INFORMADO
            # TODO: support other security_code indices

        if isinstance(payment, DebitPayment):
            product = DEBITO
        elif payment.installments == 1:
            product = CREDITO_A_VISTA
        else:
            product = PARCELADO_ADMINISTRADORA
            # TODO suportar parcelado_administradora

        appstruct = {
            'id': self.generate_transaction_id(),
            'version': '1.1.1',
            'establishment': {
                'number': self.store_id,
                'key': self.store_key,
            },
            'order': {
                'number': order.number,
                'value': order.value,
                'currency': order.currency,
                'datetime': order.datetime,
                'description': order.description,
                'language': order.language,
            },
            'holder': {
                'number': payment.card_number,
                'security_code': payment.card_security_code,
                'security_code_indicator': code_indic,
                'expiration_date': payment.card_expiration_date,
                'holder_name': payment.card_holder_name,
            },
            'payment': {
                'card_brand': payment.card_brand,
                'product': product,
                'installments': payment.installments,
            },
            'return_url': return_url,
            'authorize': authorize,
            'capture': capture,
            'bin': payment.card_number[:6],
        }

        schema = TransactionRequestSchema(tag='requisicao-transacao')
        request = schema.serialize(appstruct)
        request = message.dumps(request)
        return self.post_request(request)

    def post_request(self, request):
        msg = u"mensagem=" + request
        #TODO msg = msg.encode('iso-')

        try:
            request = urllib2.urlopen(self.service_url, msg)
            with contextlib.closing(request) as response:
                response = response.read()
        except urllib2.URLError, e:
            raise CommunicationError(e.reason)

        return self.process_response(response.decode('iso-8859-1'))

    def process_response(self, response):
        response = message.loads(response.encode('utf-8'))

        # get the root type
        root_tag = message.get_root_tag(response)

        # let's try to guess the response content-type
        schema = guess_response_schema(root_tag)

        if schema is None:
            raise UnknownResponse("Unknown response type '%s'" % root_tag)

        # TODO specialized exception class?
        cstruct = message.deserialize(schema, response)
        response = schema.deserialize(cstruct)
        response = schema.content_type.deserialize(response)

        return response
