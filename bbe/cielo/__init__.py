# -*- coding: utf-8 -*-
import colander
import uuid
import urllib2
from collections import OrderedDict
from itertools import chain
from .schema import *
from .client import Client, Order, Payment, DebitPayment


SERVICE_VERSION = '1.1.1'


def recursive_subclasses(cls):
    subs = cls.__subclasses__()
    return set(subs) | set(chain(*(c.__subclasses__() for c in subs)))


class ContentType(object):
    __schema__ = None

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


