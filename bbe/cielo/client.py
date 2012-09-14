# -*- coding: utf-8 -*-
import datetime
import uuid
import hashlib
import urllib2
import contextlib
from colander import null
from bbe.cielo import message
from bbe.cielo import schema as schemas


class CommunicationError(urllib2.URLError):
    """This exception is raised when the communication between
    our client and the remote service fail.

    .. attribute:: reason

        The error reason. It can be a message or an instance of
        another exception.
    """


class Error(Exception):
    code = None

    def __init__(self, message, code):
        self.message = message
        self.code = code
        super(Error, self).__init__(self.message)

    @staticmethod
    def get_error_class(code):
        for cls in Error.__subclasses__():
            if getattr(cls, 'code', None) == code:
                return cls
        return Error


class TimeoutError(Error):
    code = 98


def get_object_like(appstruct, key, default=None):
    value = appstruct.get(key, default)
    if value is null:
        value = default
    else:
        value = ObjectLikeDict(value)
    return value


class ObjectLikeDict(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class Transaction(object):
    def __init__(self, tid, order, store, value, currency, datetime,
                 language, brand, installments, product, status, pan,
                 description=None, authentication=None, authorization=None,
                 capture=None, cancel=None, authentication_url=None):

        self.tid = tid
        self.order = order
        self.store = store
        self.value = value
        self.currency = currency
        self.datetime = datetime
        self.language = language
        self.brand = brand
        self.installments = installments
        self.product = product
        self.status = status
        self.pan = pan
        self.authorization = authorization
        self.authentication = authentication
        self.cancel = cancel
        self.capture = capture
        self.authentication_url = authentication_url


class Card(object):
    def __init__(self, brand, number, holder_name, expiration_date, security_code=None):
        self.brand = brand
        self.number = number
        self.holder_name = holder_name
        self.expiration_date = expiration_date
        self.security_code = security_code


class Client(object):
    def __init__(self, store_id, store_key, default_installment_type,
                 service_url=schemas.SERVICE_URL,
                 default_currency=schemas.DEFAULT_CURRENCY,
                 default_language=schemas.DEFAULT_LANGUAGE):
        self.store_id = store_id
        self.store_key = store_key
        self.service_url = service_url
        self.default_installment_type = default_installment_type
        self.default_currency = default_currency
        self.default_language = default_language

    def generate_request_id(self):
        return str(uuid.uuid4())

    def generate_order_number(self):
        return hashlib.sha1(str(uuid.uuid4())).hexdigest()[:20]

    def query_by_tid(self, tid):
        schema = schemas.QuerySchema(tag='requisicao-consulta')
        cstruct = schema.serialize({
            'id': self.generate_request_id(),
            'version': schemas.SERVICE_VERSION,
            'establishment': {
                'number': self.store_id,
                'key': self.store_key,
            },
            'tid': tid,
        })
        etree = message.serialize(schema, cstruct)
        request = message.dumps(etree, encoding='ISO-8859-1')
        return  self.post_request(request)

    def query_by_order_number(self, order_number):
        schema = schemas.OrderQuerySchema(tag='requisicao-consulta-chsec')
        cstruct = schema.serialize({
            'id': self.generate_request_id(),
            'version': schemas.SERVICE_VERSION,
            'establishment': {
                'number': self.store_id,
                'key': self.store_key,
            },
            'order_number': order_number,
        })
        etree = message.serialize(schema, cstruct)
        request = message.dumps(etree, encoding='ISO-8859-1')
        return  self.post_request(request)

    def create_transaction(self, value, card, installments, authorize,
                           capture, created_at=None, description=None,
                           currency=None, language=None, installment_type=None,
                           return_url=None, product=None):
        currency = currency or self.default_currency
        language = language or self.default_language

        created_at = created_at or datetime.datetime.now()

        # TODO is this really necessary?
        return_url = return_url or 'http://example.com'

        if not isinstance(card, Card):
            brand = card
        else:
            brand = card.brand

            if card.security_code is None:
                card_indicator = schemas.SC_NAO_INFORMADO
            else:
                card_indicator = schemas.SC_INFORMADO
                # TODO: support more indicator types

        if product is not None:
            # validate the specified product
            if product in (schemas.CREDITO_A_VISTA, schemas.DEBITO):
                if installments != 1:
                    raise ValueError("Inconsistent `installment`, `product` pair")
            elif installments == 1:
                raise ValueError("Inconsistent `installment`, `product` pair")
        else:
            if installments == 1:
                product = schemas.CREDITO_A_VISTA
            else:
                product = installment_type or self.default_installment_type

        # the order id
        oid = self.generate_order_number()

        appstruct = {
            'id': self.generate_request_id(),
            'version': schemas.SERVICE_VERSION,
            'establishment': {
                'number': self.store_id,
                'key': self.store_key,
            },
            'order': {
                'number': oid,
                'value': value,
                'currency': currency,
                'description': description,
                'datetime': created_at,
                'language': language,
            },
            'payment': {
                'brand': brand,
                'product': product,
                'installments': installments,
            },
            'return_url': return_url,
            'authorize': authorize,
            'capture': capture,
        }

        if isinstance(card, Card):
            appstruct['holder'] = {
                'number': card.number,
                'holder_name': card.holder_name,
                'expiration_date': card.expiration_date,
                'security_code': card.security_code,
                'security_code_indicator': card_indicator,
            }
            appstruct['bin'] =  card.number[:6]

        # TODO move this 'tag' thing to the schema, where it belongs
        schema = schemas.TransactionRequestSchema(tag='requisicao-transacao')
        cstruct = schema.serialize(appstruct)
        etree = message.serialize(schema, cstruct)
        request = message.dumps(etree, encoding='ISO-8859-1')
        return  self.post_request(request)

    def post_request(self, request):
        data = 'mensagem=' + request

        try:
            request = urllib2.urlopen(self.service_url, data)
            with contextlib.closing(request) as response:
                response = response.read()
        except urllib2.URLError, e:
            raise CommunicationError(e.reason)

        return self.process_response(response)

    def process_response(self, response):
        etree = message.loads(response)
        root_tag = message.get_root_tag(etree)

        if root_tag == 'erro':
            schema = schemas.ErrorSchema()
        elif root_tag == 'transacao':
            schema = schemas.TransactionSchema()
        else:
            # the service only returns errors or transactions.
            raise ValueError("Invalid response: %s" % root_tag)

        cstruct = message.deserialize(schema, etree)
        appstruct = schema.deserialize(cstruct)

        if root_tag == 'erro':
            error_class = Error.get_error_class(appstruct['code'])
            raise error_class(**appstruct)

        order = appstruct['order']
        payment = appstruct['payment']
        status = appstruct['status']
        return Transaction(
            tid=appstruct['tid'],
            store=self.store_id,
            datetime=order['datetime'],
            order=order['number'],
            value=order['value'],
            currency=order['currency'],
            language=order['language'],
            description=order['description'],
            brand=payment['brand'],
            installments=payment['installments'],
            product=payment['product'],
            status=status,
            pan=appstruct['pan'],
            authentication=get_object_like(appstruct, 'authentication'),
            authentication_url=appstruct['authentication_url'],
            authorization=get_object_like(appstruct, 'authorization'),
            capture=get_object_like(appstruct, 'capture'),
            cancel=get_object_like(appstruct, 'cancel'),
        )
