# -*- coding: utf-8 -*-
"""
Este módulo implementa um cliente de comunicação com o webservice
da Cielo, em sua versão 1.1.1, conforme descrito na versão 1.5.8
do manual do desenvolvedor da Cielo.

A API implementada tenta se aproximar de um design orientado a objetos,
ao mesmo tempo que tenta se mantar fiel à estrutura e nomenclatura descrita
no manual da Cielo. No fim das contas, a coisa ficou mais ou menos assim...

Primeiramente, é necessário instanciar o estabelecimento, utilizando
o número e código do seu estabelecimento junto à Cielo.

::

    import cielo
    ec = cielo.Estabelecimento('1006993069', '25fbb99741c739dd84d7b06ec78c9bac718838630f30b112d033ce2e621b34f3')

Depois, é necessário instanciar o cliente, passando a url do webservice.
A url utilizada nestes exemplos é a url de um webservice de testes disponibilizado
pela Cielo. Por favor, consulte o manual da Cielo para encontrar a url de produção.

::

    cliente = cielo.Cliente('https://qasecommerce.cielo.com.br/servicos/ecommwsec.do')


A criação de transações pode ser feita através do método ``Cliente.nova_transacao``,
para o qual devem ser passados os dados padrão da transação da Cielo e o Estabelecimento.

::

    import datetime
    from decimal import Decimal
    h1 = cielo.Portador(nome="Ananias da Silva",
                        numero="4012001037141112",
                        codigo_seguranca="123",
                        validade=datetime.datetime(2012, 11, 1))
    o1 = cielo.Pedido(numero="1",
                      valor=Decimal('200,5'),
                      data=datetime.datetime.now())
    p1 = cielo.FormaPagamento(bandeira=cielo.VISA,
                              parcelas=2,
                              produto=cielo.PARCELADO_ADMINISTRADORA)

    t1 = cliente.nova_transacao(ec=ec, portador=h1, pedido=o1, forma_pagamento=p1,
                                url_retorno="http://www.example.com", autorizar=3,
                                capturar=True)


Os dados da transação podem ser acessados no objeto retornado.

::

    print t1.status
    print t1.tid


Pode-se consultar transações realizadas usando o ``TID`` (transaction id)  ou
através do número do pedido. A resposta será a mesma de ``nova_transacao``.

::

    tt1 = cliente.consulta_tid(ec=ec, tid=t1.tid)
    assert tt1.tid == t1.tid

E mais!


.. note::

    Note que este módulo é totalmente independente do projeto Bambae. Ele foi
    construído de forma que poderia ser empacotado, distrubuído e testado sozinho.
    Ele só está aqui dentro de bambae.utils por preguiça do desenvolvedor.

.. data:: VERSAO_SERVICO

    A versão do serviço implementada pelo módulo. Atualmente é ``1.1.1``.
"""
import re
import uuid
import urllib2
import contextlib
import datetime
import colander
from decimal import Decimal
from itertools import chain
from collections import OrderedDict
from xml.etree.ElementTree import ParseError, ElementTree, Element, fromstring

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO

VERSAO_SERVICO = '1.1.1'

LANG_PT = 'PT'
LANG_EN = 'EN'
LANG_ES = 'ES'

IDIOMAS = (LANG_PT, LANG_EN, LANG_ES)

MASTERCARD = 'mastercard'
DINERS = 'diners'
DISCOVER = 'discover'
ELO = 'elo'
VISA = 'visa'

BANDEIRAS = (MASTERCARD, DINERS, DISCOVER, ELO, VISA)


CREDITO_A_VISTA = '1'
PARCELADO_LOJA = '2'
PARCELADO_ADMINISTRADORA = '2'
A_VISTA = 'A'

PRODUTOS = (
    CREDITO_A_VISTA,
    PARCELADO_LOJA,
    PARCELADO_ADMINISTRADORA,
    A_VISTA
)

NAO_INFORMADO = 'nao-informado'
ILEGIVEL = 'ilegivel'
INEXISTENTE = 'inexistente'
INFORMADO = 'informado'

ST_CRIADA = 0
ST_EM_ANDAMENTO = 1
ST_AUTENTICADA = 2
ST_NAO_AUTENTICADA = 3
ST_AUTORIZADA = 4
ST_NAO_AUTORIZADA = 5
ST_CAPTURADA = 6
ST_NAO_CAPTURADA = 8
ST_CANCELADA = 9
ST_EM_AUTENTICACAO = 10

STATUS = (
    ST_CRIADA,
    ST_EM_ANDAMENTO,
    ST_AUTENTICADA,
    ST_NAO_AUTENTICADA,
    ST_AUTORIZADA,
    ST_NAO_AUTORIZADA,
    ST_CAPTURADA,
    ST_NAO_CAPTURADA,
    ST_CANCELADA,
    ST_EM_AUTENTICACAO,
)


# ==========================================================================
# tipos personalizados

class Indicador(colander.Integer):
    MAP = (
        (NAO_INFORMADO, 0),
        (INFORMADO, 1),
        (ILEGIVEL, 2),
        (INEXISTENTE, 9),
    )
    _map = dict(MAP)
    _rmap = dict((b, a) for (a, b) in _map.iteritems())

    def serialize(self, node, appstruct):
        i = self._map.get(appstruct, None)
        if i is not None:
            return str(i)
        elif not appstruct:
            return colander.null
        else:
            raise colander.Invalid(node, "%s is not a valid Indicador" % appstruct)

    def deserialize(self, node, cstruct):
        i = super(Indicador, self).deserialize(node, cstruct)
        if i in self._rmap:
            return self._rmap[i]
        elif not i:
            raise colander.Invalid(node, "%s is not a valid Indicator" % i)


class Dinheiro(colander.Decimal):
    """
    Serializa números para um valor monetário no formato utilizado
    pela Cielo, isto é, um número inteiro cujos dois últimos dígitos
    representam os centavos.

    ::

        >>> node = colander.SchemaNode(Dinheiro())
        >>> node.serialize(200)
        '20000'
        >>> node.serialize(200.0)
        '20000'
        >>> node.serialize(199.5)
        '19950'
        >>> node.serialize(200.21)
        '20021'
        >>> from decimal import Decimal
        >>> node.serialize(Decimal('200'))
        '20000'
        >>> node.serialize(Decimal('200.21'))
        '20021'
        >>> node.serialize(Decimal('200.3'))
        '20030'
        >>> node.serialize(200.213)
        Traceback (most recent call last):
          ...
        Invalid: {'': u'"200.213" is not a valid Dinheiro value because it has more than two decimal places'}
        >>> node.deserialize('20000')
        Decimal('200.00')
        >>> node.deserialize('193')
        Decimal('1.93')
        >>> node.deserialize('190')
        Decimal('1.90')
    """
    def serialize(self, node, appstruct):
        cstruct = super(Dinheiro, self).serialize(node, appstruct)

        if cstruct is not colander.null:
            if '.' in cstruct:
                i, d = str(cstruct).rsplit('.', 1)
            else:
                i = str(cstruct)
                d = '00'

            if len(d) > 2:
                raise colander.Invalid(node,
                    ('"%s" is not a valid Dinheiro value because it has'
                     ' more than two decimal places' % appstruct))
            elif len(d) < 2:
                d += '0' * (2 - len(d))

            return "%s%s" % (i, d)
        else:
            return cstruct

    def deserialize(self, node, cstruct):
        if cstruct:
            cstruct = "%s.%s" % (cstruct[:-2], cstruct[-2:])
        return super(Dinheiro, self).deserialize(node, cstruct)


class BaseDateTime(colander.SchemaType):
    err_template =  "invalid date"
    format = None

    def serialize(self, node, appstruct):
        if not appstruct:
            return colander.null

        if type(appstruct) is datetime.date: # cant use isinstance; dt subs date
            appstruct = datetime.datetime.combine(appstruct, datetime.time())

        if not isinstance(appstruct, datetime.datetime):
            raise colander.Invalid(node, '"%s" is not a datetime object' % appstruct)

        return appstruct.strftime(self.format)

    def deserialize(self, node, cstruct):
        if not cstruct:
            return colander.null
        try:
            result = self._strptime(cstruct)
        except ValueError:
            raise colander.Invalid(node, self.err_template)

        return result

    def _strptime(self, cstruct):
        """
        Deve levantar ValueError caso a estrutura seja inválida.
        """
        return datetime.datetime.strptime(cstruct, self.format)


class DateTime(BaseDateTime):
    format = "%Y-%m-%dT%H:%M:%S"

    def _strptime(self, cstruct):
        # XXX nas respostas da Cielo, os timestamps contém milisegundos
        # e timezone. precisamos tratar isso.
        try:
            return super(DateTime, self)._strptime(cstruct)
        except ValueError:
            dt, extra = cstruct.split('.', 1)
            ts = super(DateTime, self)._strptime(dt)

            # FIXME vamos fazer nosso melhor para carregar o timestamp de
            # forma correta, mas vamos ignorar o timezone
            ms, tz = extra.split('-')
            ts += datetime.timedelta(milliseconds=int(ms))
            return ts


class Month(BaseDateTime):
    err_template =  u"Mês invalido"
    format = "%Y%m"
    extended_format = None


class ErroSchema(colander.Schema):
    codigo = colander.SchemaNode(colander.Integer())
    mensagem = colander.SchemaNode(colander.String())


class PortadorSchema(colander.Schema):
    """
    dados-portador

    dados-portador.numero           N   R   16      Número do cartão.
    dados-portador.validade         N   R   6       Validade do cartão no formato aaaamm.
                                                    Exemplos: 201212 (dez 2012).
    dados-portador.indicador        N   R   1       Indicador do código de segurança: 0 (não informado),
                                                    1 (informado), 2 (ilegível), 9 (inexistente).
    dados-portador.codigo-seguranca N   C   3..4    Obrigatório se indicador = 1.
    dados-portador.nome-portador    AN  O   0..50   Opcional. Nome impresso no cartão.
    """
    numero = colander.SchemaNode(colander.String(),
                                 validator=colander.Length(16, 16))
    validade = colander.SchemaNode(Month())
    indicador = colander.SchemaNode(Indicador())
    codigo_seguranca = colander.SchemaNode(colander.String(),
                                           tag='codigo-seguranca',
                                           validator=colander.Length(3, 4))
    nome = colander.SchemaNode(colander.String(),
                               tag='nome-portador',
                               missing=colander.null,
                               validator=colander.Length(max=50))


class PedidoSchema(colander.Schema):
    """
    dados-pedido

    dados-pedido.numero     AN  R   1..20   Número do pedido da loja. Recomenda-se que seja um valor único por pedido.
    dados-pedido.valor      N   R   1..12   Valor do pedido.
    dados-pedido.moeda      N   R   3       Código numérico da moeda na ISO 4217.
                                            Para o Real, o código é 986.
    dados-pedido.data-hora  AN  R   19      Data hora do pedido.
    dados-pedido.descricao  AN  O   0..1024 Descrição do pedido.
    dados-pedido.idioma     AN  O   2       Idioma do pedido: PT (português), EN (inglês) ou ES (espanhol).
                                            Com base nessa informação é definida a língua a ser utilizada
                                            nas telas da Cielo. Caso não preenchido, assume-se PT.
    """
    numero = colander.SchemaNode(colander.String(),
                                 validator=colander.Length(max=20))
    valor = colander.SchemaNode(Dinheiro(),
                                validator=colander.Range(
                                    min=Decimal('0.01'),
                                    max=Decimal('9999999999.99')
                                ))
    moeda = colander.SchemaNode(colander.String()) # TODO OneOf
    data = colander.SchemaNode(DateTime(), tag='data-hora')
    descricao = colander.SchemaNode(colander.String(),
                                    validator=colander.Length(max=1024),
                                    missing=colander.null)
    idioma = colander.SchemaNode(colander.String(),
                                 missing='PT',
                                 defaults='PT',
                                 validator=colander.OneOf(IDIOMAS))


class FormaPagamentoSchema(colander.Schema):
    """
    forma-pagamento

    forma-pagamento.bandeira    AN  R   n/a     Bandeira: visa, mastercard, diners,
                                                discover ou elo (em minúsculo).
    forma-pagamento.produto     AN  R   1       Código do produto: 1 (Crédito à Vista),
                                                2 (Parcelado loja), 3 (Parcelado administradora),
                                                A (Débito).
    forma-pagamento.parcelas    N   R   1..3    Número de parcelas. Para crédito à vista ou
                                                débito, utilizar 1.
    """
    bandeira = colander.SchemaNode(colander.String(),
                                   validator=colander.OneOf(BANDEIRAS))
    produto = colander.SchemaNode(colander.String(),
                                  validator=colander.OneOf(PRODUTOS))
    parcelas = colander.SchemaNode(colander.Integer(),
                                   validator=colander.Range(1, 999))


class EstabelecimentoSchema(colander.Schema):
    """
    dados-ec

    dados-ec.numero N   R   1..20   Número de afiliação da loja com a Cielo.
    dados-ec.chave  AN  R   1..100  Chave de acesso da loja atribuída pela Cielo.
    """
    numero = colander.SchemaNode(colander.String(),
                                 validator=colander.Length(max=20))
    chave = colander.SchemaNode(colander.String(),
                                validator=colander.Length(max=100))


class AutenticacaoSchema(colander.Schema):
    codigo = colander.SchemaNode(colander.Integer())
    mensagem = colander.SchemaNode(colander.String())
    data = colander.SchemaNode(DateTime(), tag='data-hora')
    valor = colander.SchemaNode(Dinheiro())
    eci = colander.SchemaNode(colander.Integer())


class AutorizacaoSchema(colander.Schema):
    codigo = colander.SchemaNode(colander.Integer())
    mensagem = colander.SchemaNode(colander.String())
    data = colander.SchemaNode(DateTime(), tag='data-hora')
    valor = colander.SchemaNode(Dinheiro())
    lr = colander.SchemaNode(colander.Integer()) # TODO OneOf?
    nsu = colander.SchemaNode(colander.String()) # TODO wtf?
    arp = colander.SchemaNode(colander.String(), missing=colander.null) # só está disponível em transações que foram auatorizadas


class CapturaSchema(colander.Schema):
    codigo = colander.SchemaNode(colander.Integer())
    mensagem = colander.SchemaNode(colander.String())
    data = colander.SchemaNode(DateTime(), tag='data-hora')
    valor = colander.SchemaNode(Dinheiro())


class CancelamentoSchema(colander.Schema):
    codigo = colander.SchemaNode(colander.Integer())
    mensagem = colander.SchemaNode(colander.String())
    data = colander.SchemaNode(DateTime(), tag='data-hora')
    valor = colander.SchemaNode(Dinheiro())


class Raiz(colander.Schema):
    """
    Schema base para schemas de nós-raiz.
    """
    id = colander.SchemaNode(colander.String(), attrib=True)
    versao = colander.SchemaNode(colander.String(), attrib=True)


class RequisicaoTransacaoSchema(Raiz):
    ec = EstabelecimentoSchema(tag='dados-ec')
    portador = PortadorSchema(tag='dados-portador', missing=colander.null)
    pedido = PedidoSchema(tag='dados-pedido')
    pagamento = FormaPagamentoSchema(tag='forma-pagamento')
    url_retorno = colander.SchemaNode(colander.String(), tag='url-retorno')
    autorizar = colander.SchemaNode(colander.Integer())
    capturar = colander.SchemaNode(colander.Boolean(), tag='capturar', missing=colander.null)
    bin = colander.SchemaNode(colander.String(), tag='bin', missing=colander.null)


class RequisicaoConsultaSchema(Raiz):
    """
    Schema da Consulta via TID

    requisicao-consulta

    dados-ec.numero N   R   1..20   Número de afiliação da loja com a Cielo
    dados-ec.chave  AN  R   1..100  Chave de acesso da loja atribuída pela Cielo
    tid             AN  R   1..40   Identificador da transação.
    """
    tid = colander.SchemaNode(colander.String(), validator=colander.Length(max=40))
    ec = EstabelecimentoSchema(tag='dados-ec')


class RequisicaoConsultaPedidoSchema(Raiz):
    """
    Schema da Consulta via Número do Pedido

    requisicao-consulta-chsec

    numero-pedido   NA  R   1...20  Número do Pedido associado à Transação
    dados-ec.numero N   R   1..20   Número de afiliação da loja com a Cielo
    dados-ec.chave  AN  R   1..100  Chave de acesso da loja atribuída pela Cielo
    """
    numero_pedido = colander.SchemaNode(colander.String(),
                                        tag='numero-pedido',
                                        validator=colander.Length(max=20))
    ec = EstabelecimentoSchema(tag='dados-ec')


class RequisicaoCapturaSchema(Raiz):
    """
    Schema da requisição de captura.

    requisicao-captura

    dados-ec.numero N   R   1..20   Número de afiliação da loja com a Cielo
    dados-ec.chave  AN  R   1..100  Chave de acesso da loja atribuída pela Cielo
    tid             AN  R   1..40   Identificador da transação.
    valor           N   O   1..12   Valor da captura. Caso não fornecido, o valor atribuído é o valor da autorização.
    anexo           AN  O   1..1024 Informação adicional para detalhamento da captura.
    """
    tid = colander.SchemaNode(colander.String(),
                              validator=colander.Length(max=40))
    valor = colander.SchemaNode(Dinheiro(),
                                missing=colander.null,
                                validator=colander.Range(max=Decimal('9999999999.99')))
    anexo = colander.SchemaNode(colander.String(),
                                missing=colander.null,
                                validator=colander.Length(max=1024))
    ec = EstabelecimentoSchema(tag='dados-ec')


class TransacaoSchema(Raiz):
    tid = colander.SchemaNode(colander.String())
    pedido = PedidoSchema(tag='dados-pedido')
    pagamento = FormaPagamentoSchema(tag='forma-pagamento')
    status = colander.SchemaNode(colander.Integer(), validator=colander.OneOf(STATUS))
    autenticacao = AutenticacaoSchema(missing=colander.null)
    autorizacao = AutorizacaoSchema(missing=colander.null)
    captura = CapturaSchema(missing=colander.null)
    cancelamento = CancelamentoSchema(missing=colander.null)
    pan = colander.SchemaNode(colander.String())
    url_autenticacao = colander.SchemaNode(colander.String(),
                                           tag='url-autenticacao',
                                           missing=colander.null)


# ==========================================================================

def tostring(etree):
    s = StringIO()
    etree.write(s)
    return s.getvalue()


def etreeify(schema, cstruct):
    tag = getattr(schema, 'tag', schema.name)
    ele = Element(tag)
    if isinstance(schema.typ, colander.Mapping):
        for child in schema.children:
            value = cstruct.get(child.name, colander.null)
            if value is not colander.null:
                if getattr(child, 'attrib', False):
                    attr = getattr(child, 'tag', child.name)
                    ele.attrib[attr] = value
                else:
                    subele = etreeify(child, cstruct.get(child.name, colander.null))
                    if subele is not None:
                        ele.append(subele)
        return ele
    else:
        if cstruct is colander.null:
            return None
        ele.text = cstruct
        return ele


def deetreeify(schema, etree):
    if isinstance(schema.typ, colander.Mapping):
        cstruct = {}
        for child in schema.children:

            if getattr(child, 'attrib', False):
                attr = getattr(child, 'tag', child.name)
                value = etree.attrib.get(attr, colander.null)
            else:
                tag = getattr(child, 'tag', child.name)
                element = etree.find(tag)
                if element is not None:
                    value = deetreeify(child, element)
                else:
                    value = colander.null

            if value is not colander.null:
                cstruct[child.name] = value

        return cstruct
    else:
        return etree.text


def xmlify(schema, appstruct):
    cstruct = schema.serialize(appstruct)
    element = etreeify(schema, cstruct)
    return tostring(ElementTree(element))


def dexmlify(schema, xml):
    etree = fromstring(xml)
    cstruct = deetreeify(schema, etree)
    return schema.deserialize(cstruct)


def recursive_subclasses(cls):
    subs = cls.__subclasses__()
    return set(subs) | set(chain(*(c.__subclasses__() for c in subs)))


def remove_namespaces(element):
    """Remove all namespaces in the passed element in place."""
    for ele in element.getiterator():
        ele.tag = re.sub(r'^\{[^\}]+\}', '', ele.tag)


class ContentType(object):
    __schema__ = None

    def serialize(self):
        return xmlify(self.__schema__, self.appstruct())

    @classmethod
    def fromappstruct(cls, appstruct):
        return cls(**appstruct)

    @classmethod
    def find_by_tag_name(cls, tag):
        for subcls in recursive_subclasses(ContentType):
            schema = subcls.__schema__
            if schema is not None and schema.name == tag:
                return subcls

    def appstruct(self):
        appstruct = OrderedDict()
        for child in self.__schema__:
            value = getattr(self, child.name, colander.null)
            # XXX seria esse o lugar certo para converter None -> null?
            # e se o cara queria passar o None?
            if value is None:
                value = colander.null
            if isinstance(value, ContentType):
                value = value.appstruct()
            appstruct[child.name] = value
        return appstruct


class Estabelecimento(ContentType):
    __schema__ = EstabelecimentoSchema()

    def __init__(self, numero, chave):
        self.numero = numero
        self.chave = chave


class Portador(ContentType):
    __schema__ = PortadorSchema()

    def __init__(self, numero, validade, codigo_seguranca, nome=None):
        self.numero = numero
        self.validade = validade
        self.nome = nome

        if codigo_seguranca == NAO_INFORMADO:
            self._indicador = NAO_INFORMADO
        elif codigo_seguranca == ILEGIVEL:
            self._indicador = ILEGIVEL
        elif codigo_seguranca == INEXISTENTE:
            self._indicador = INEXISTENTE
        else:
            self.codigo_seguranca = codigo_seguranca
            self._indicador = INFORMADO

    @property
    def indicador(self):
        return self._indicador


class Pedido(ContentType):
    __schema__ = PedidoSchema()

    def __init__(self, numero, valor, data, descricao=None,
                 idioma='PT', moeda=986):
        self.numero = numero
        self.valor = valor
        self.data = data
        self.descricao = descricao
        self.idioma = idioma
        self.moeda = moeda


class FormaPagamento(ContentType):
    __schema__ = FormaPagamentoSchema()

    def __init__(self, bandeira, produto, parcelas=1):
        self.bandeira = bandeira
        self.produto = produto
        self.parcelas = parcelas


class Autenticacao(ContentType):
    __schema__ = AutenticacaoSchema()

    def __init__(self, codigo, mensagem, data, valor, eci):
        self.codigo = codigo
        self.mensagem = mensagem
        self.data = data
        self.valor = valor
        self.eci = eci


class Autorizacao(ContentType):
    __schema__ = AutorizacaoSchema()

    def __init__(self, codigo, mensagem, data, valor, lr, nsu, arp):
        self.codigo = codigo
        self.mensagem = mensagem
        self.data = data
        self.valor = valor
        self.lr = lr
        self.nsu = nsu
        self.arp = arp


class Captura(ContentType):
    __schema__ = CapturaSchema()

    def __init__(self, codigo, mensagem, data, valor):
        self.codigo = codigo
        self.mensagem = mensagem
        self.data = data
        self.valor = valor


class Cancelamento(ContentType):
    __schema__ = CancelamentoSchema()

    def __init__(self, codigo, mensagem, data, valor):
        self.codigo = codigo
        self.mensagem = mensagem
        self.data = data
        self.valor = valor


class ConteudoRaiz(ContentType):
    """
    Classe base para todos os conteúdos que podem ser utilizados
    como raiz do XML pelo webservice.

    Atributos:

        .. attribute:: id

            O id deste nó. Ainda não sei pra que isso serve.

        .. attribute:: versao

            A versão do webservice que gerou o nó. O padrão é :data:`VERSAO_SERVICO`.
    """

    versao = VERSAO_SERVICO

    def __init__(self, versao=None, id=None):
        self.id = id
        self.versao = versao or self.versao

        if self.id is None:
            self.id = self.gerar_id()

    def gerar_id(self):
        return str(uuid.uuid4())


class Transacao(ConteudoRaiz):
    """
    Transação retornada pela maioria dos métodos do :class:`Cliente`.
    É um :class:`ConteudoRaiz`.

    Atributos:

    .. attribute:: tid

        O id único da transação (TID).

    .. attributes:: pedido

        O pedido.
    """
    __schema__ = TransacaoSchema(name='transacao')

    def __init__(self, tid, pedido, pagamento, status, url_autenticacao,
                 pan, autenticacao=None, autorizacao=None, captura=None,
                 cancelamento=None, *args, **kwargs):
        self.tid = tid
        self.pedido = pedido
        self.pagamento = pagamento
        self.status = status
        self.autenticacao = autenticacao
        self.autorizacao = autorizacao
        self.captura = captura
        self.cancelamento = cancelamento
        self.pan = pan
        self.url_autenticacao = url_autenticacao

        super(Transacao, self).__init__(*args, **kwargs)

    @classmethod
    def fromappstruct(cls, appstruct):
        kwargs = {
            'pedido': Pedido.fromappstruct(appstruct.pop('pedido')),
            'pagamento': FormaPagamento.fromappstruct(appstruct.pop('pagamento')),
        }

        # XXX FIXME TODO LOL
        for cls_ in [Autenticacao, Autorizacao, Captura, Cancelamento]:
            key = cls_.__name__.lower()
            value = appstruct.pop(key, colander.null)
            if value:
                kwargs[key] = cls_.fromappstruct(value)

        kwargs.update(appstruct)
        return cls(**kwargs)


class Requisicao(ConteudoRaiz):
    def __init__(self, ec, *args, **kwargs):
        self.ec = ec
        super(Requisicao, self).__init__(*args, **kwargs)


class RequisicaoTransacao(Requisicao):
    __schema__ = RequisicaoTransacaoSchema(name='requisicao-transacao')

    def __init__(self, ec, pedido, pagamento, url_retorno, autorizar,
                 capturar, portador=None, *args, **kwargs):
        self.pedido = pedido
        self.pagamento = pagamento
        self.url_retorno = url_retorno
        self.autorizar = autorizar
        self.capturar = capturar
        self.portador = portador or colander.null

        super(RequisicaoTransacao, self).__init__(ec, *args, **kwargs)

    @property
    def bin(self):
        if self.portador:
            return self.portador.numero[:6]


class RequisicaoConsulta(Requisicao):
    """
    Consulta via TID
    ================

    Funcionalidade de extrema importância na integração.
    É através dela que a loja virtual obtém uma “foto” da
    transação. É sempre utilizada após a loja ter recebido
    o retorno do fluxo da Cielo.

    Observações
    -----------

    Somente transações dos últimos 180 dias estão disponíveis para consulta.
    """
    __schema__ = RequisicaoConsultaSchema(name='requisicao-consulta')

    def __init__(self, ec, tid, *args, **kwargs):
        self.tid = tid

        super(RequisicaoConsulta, self).__init__(ec, *args, **kwargs)


class RequisicaoConsultaPedido(Requisicao):
    """
    Consulta via Número do Pedido
    =============================

    Consulta de transação via número do pedido. Seu uso é restrito
    para casos onde há ausência do identificador da transação (TID),
    por conta de um timeout, por exemplo. São retornadas as mesmas
    informações da consulta via TID.

    Observações
    -----------

    Somente transações dos últimos 180 dias estão disponíveis para consulta.

    Caso a loja virtual possua mais de uma transação para um mesmo número do
    pedido, retorna-se a transação mais recente apenas.
    """
    __schema__ = RequisicaoConsultaPedidoSchema(name='requisicao-consulta-chsec')

    def __init__(self, ec, numero_pedido, *args, **kwargs):
        super(RequisicaoConsultaPedido, self).__init__(ec, *args, **kwargs)
        self.numero_pedido = numero_pedido



class RequisicaoCaptura(Requisicao):
    """
    Uma transação autorizada somente gera crédito para o estabelecimento
    comercial caso ela seja capturada. Por isso, todo pedido de compra
    que o lojista queira efetivar, deve ter a transação capturada.

    Para venda na modalidade de Crédito, essa confirmação pode ocorrer
    logo após a autorização (valor total) ou num momento posterior
    (valor total ou parcial).

    Essa definição é feita através do parâmetro  capturar (consulte
    o tópico “Criação”). Já na modalidade de Débito não existe essa
    abertura: toda transação de débito autorizada é automaticamente
    capturada.

    Regras
    ------

    Por padrão, o prazo máximo para captura é de 5 dias após a data
    de autorização. Exemplo: se a data de autorização é 21/09, o prazo
    máximo é as 0 hs do dia 27/09.

    O valor da captura deve ser menor (captura parcial) ou igual
    (captura total) ao valor autorizado. Somente transações
    autorizadas podem ser capturadas.

    Em caso de falha na captura, outras tentativas poderão ser realizadas.
    """
    __schema__ = RequisicaoCapturaSchema(name='requisicao-captura')

    def __init__(self, ec, tid, valor=None, anexo=None, *args, **kwargs):
        super(RequisicaoCaptura, self).__init__(ec, *args, **kwargs)
        self.tid = tid
        self.valor = valor
        self.anexo = anexo


# ==========================================================================
# Erros

class ErroComunicacao(urllib2.URLError):
    """
    O cliente levanta esta exceção quando ocorre algum problema de comunicação.
    Esta é uma subclasse de :class:`urllib2.URLError`.

    .. attribute:: reason

        O motivo deste erro. Pode ser uma string de uma mensagem ou uma
        instância de outra exceção.
    """
    def __init__(self, reason):
        super(ErroComunicacao, self).__init__(reason)


class ErroAnalise(Exception):
    """
    O cliente levanta esta exceção quando não consegue interpretar a resposta
    obtida como um XML válido.

    .. attribute:: reason

        O motivo deste erro. Pode ser uma string de mensagem ou uma instância
        de outra exceção.
    """
    def __init__(self, reason):
        self.reason = reason
        super(ErroAnalise, self).__init__(reason)


class RespostaDesconhecida(ErroAnalise):
    """
    O cliente levanta esta exceção quando recebe como resposta um XML
    válido, mas não consegue encontrar uma classe correspodente.
    Neste caso, provavelmente se trata de alguma funcionalidade do
    webservice que não foi considerada durante o desenvolvimento,
    mas pode ser introduzida em uma versão posterior.
    """


class Erro(Exception, ContentType):
    """
    Classe base de todos os erros retornados pelo webservice remoto.
    """
    __schema__ = ErroSchema(name='erro')

    def __init__(self, codigo, mensagem):
        self.codigo = codigo
        self.mensagem = mensagem

        exc_msg = (u"erro %d: %s" % (self.codigo, self.mensagem))
        exc_msg = exc_msg.encode('ascii', 'replace')
        super(Erro, self).__init__(exc_msg)

    @classmethod
    def classe_por_codigo(cls, codigo):
        for subcls in cls.__subclasses__():
            if getattr(subcls, '__codig__', None) == codigo:
                return subcls


class ErroSistemaIndisponivel(Erro):
    """
    Sistema indisponível. Falha no sistema. Persistindo, entrar
    em contato com o Suporte e-commerce.
    """
    __codigo__ = 97


class ErroTimeout(Erro):
    """
    A aplicação não respondeu dentro de 25 segundos. Persistindo,
    entrar em contato com o Suporte e-commerce.
    """
    __codigo__ = 98


class Cliente(object):
    """
    O cliente
    """
    def __init__(self, url):
        self.url = url

    def nova_transacao(self, *args, **kwargs):
        requisicao = RequisicaoTransacao(*args, **kwargs)
        return self.enviar_requisicao(requisicao)

    def consultar_tid(self, ec, tid):
        """
        Efetua uma consulta via TID.

        .. note::

            Segundo o manual da Cielo, apenas as transações dos últimos
            180 dias estão disponíveis para consulta.

        :param ec: o :class:`Estabelecimento`
        :param tid: o tid a ser consultado

        :returns: :class:`Transacao`
        """
        requisicao = RequisicaoConsulta(ec=ec, tid=tid)
        return self.enviar_requisicao(requisicao)

    def consultar_pedido(self, ec, numero_pedido):
        """
        Efetua uma consulta via número do pedido.

        .. note::

            Segundo o manual da Cielo, apenas as transações dos últimos
            180 dias estão disponíveis para consulta.

        .. note::

            Segundo a especificação da Cielo, é responsabilidade do
            usuário do serviço garantir a unicidade dos números dos
            pedidos gerados. Caso o estabelecimento faça mais de um
            pedido com o mesmo número, a transação mais recente será
            retornada pelo serviço.

        :param ec: o :class:`Estabelecimento`
        :param numero_pedido: o número do pedido a ser consultado

        :returns: :class:`Transacao`
        """
        requisicao = RequisicaoConsultaPedido(ec=ec, numero_pedido=numero_pedido)
        return self.enviar_requisicao(requisicao)

    def capturar(self, ec, tid, valor=None, anexo=None):
        requisicao = RequisicaoCaptura(ec, tid, valor, anexo)
        return self.enviar_requisicao(requisicao)

    def enviar_requisicao(self, requisicao):
        message = requisicao.serialize()
        return self.enviar_mensagem(message)

    def enviar_mensagem(self, mensagem):
        """
        Envia uma mensagem para o webservice, analisa a resposta e tenta
        convertê-la em uma subclasse de :class:`ContentType`. Pode levantar
        :exc:`ErroComunicacao` caso ocorra algum problema de comunicação
        com o serviço, :exc:`ErroAnalise` caso não consiga interpretar a
        resposta obtida como um XML válido, :exc:`RespostaDesconhecida`,
        caso não consiga converter a resposta em um :class:`ContentType`
        ou alguma subclasse de :exc:`Erro` caso receba um erro como resposta.
        """
        data = u'mensagem=' + mensagem

        try:
            # enviar a requisição e ler a resposta do webservice.
            with contextlib.closing(urllib2.urlopen(self.url, data)) as response:
                xml = response.read()
                etree = fromstring(xml)
        except urllib2.URLError, e:
            raise ErroComunicacao(e.reason)
        except ParseError, e:
            raise ErroAnalise(e)

        remove_namespaces(etree)
        root_tag = etree.tag

        if root_tag == 'erro':
            # o webservice retornou um erro. vamos tentar identificar a
            # classe do erro.
            schema = Erro.__schema__
            cstruct = deetreeify(schema, etree)
            appstruct = schema.deserialize(cstruct)
            error_class = Erro.classe_por_codigo(appstruct['codigo'])

            # se nenhuma classe puder ser identificada, vamos tratar o
            # erro como um erro comum
            if not error_class:
                error_class = Erro

            erro = error_class.fromappstruct(appstruct)
            raise erro
        else:
            # encontrar o ContentType correspondente à resposta
            content_type = ContentType.find_by_tag_name(root_tag)
            if content_type is None:
                raise RespostaDesconhecida('Nao foi possivel econtrar '
                                           'uma clase correspondente '
                                           'a tag "%s"' % root_tag)
            else:
                schema = content_type.__schema__
                cstruct = deetreeify(schema, etree)
                appstruct = schema.deserialize(cstruct)
                return content_type.fromappstruct(appstruct)
