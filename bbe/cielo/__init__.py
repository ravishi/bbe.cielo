# -*- coding: utf-8 -*-
import re
import uuid
import urllib2
import colander
from itertools import chain
from collections import OrderedDict
from xml.etree.ElementTree import ParseError, ElementTree, Element, fromstring
from .schema import *

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO


SERVICE_VERSION = '1.1.1'


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

    versao = SERVICE_VERSION

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
