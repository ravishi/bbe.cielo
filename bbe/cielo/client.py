# -*- coding: utf-8 -*-
import datetime as mod_datetime
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
)
from bbe.cielo.error import Error, UnknownResponse, CommunicationError

DEFAULT_CURRENCY = '096'


class Order(object):
    def __init__(self, value, number=None, datetime=None,
                 description=None, currency=DEFAULT_CURRENCY, language='PT'):
        self.value = value
        self.number = number
        self.datetime = datetime or mod_datetime.datetime.now()
        self.currency = currency
        self.description = description
        self.language = language

        if self.number is None:
            self.number = self.unique_number()

    def unique_number(self):
        return '1'
        #return str(uuid.uuid4())


class Payment(object):
    def __init__(self, value, datetime, installments, card_brand, card_number,
                 card_holder_name, card_expiration_date, card_security_code):
        self.value = value
        self.datetime = datetime
        self.installments = installments
        self.card_brand = card_brand
        self.card_number = card_number
        self.card_holder_name = card_holder_name
        self.card_expiration_date = card_expiration_date
        self.card_security_code = card_security_code


class DebitPayment(Payment):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('installments', 1)
        super(Payment, self).__init__(*args, **kwargs)


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

        if isinstance(response, Error):
            raise response
        else:
            return response
