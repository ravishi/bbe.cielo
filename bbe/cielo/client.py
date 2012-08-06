# -*- coding: utf-8 -*-
import urllib2
import contextlib
from bbe.cielo import (
    RequisicaoConsulta,
    RequisicaoConsultaPedido,
    RequisicaoCaptura,
)

class Client(object):
    """
    The client.
    """

    def __init__(self, url):
        self.url = url

    def new_transaction(self, *args, **kwargs):
        raise NotImplementedError()

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
        data = u"mensagem=" + mensagem

        try:
            # enviar a requisição e ler a resposta do webservice.
            with contextlib.closing(urllib2.urlopen(self.url, data)) as r:
                body = r.read()
        except urllib2.URLError, e:
            raise ErroComunicacao(e.reason)

        response = Message.fromstring(body)

        if response.root_tag == 'erro':
            # o webservice retornou um erro. vamos tentar identificar a
            # classe do erro.
            schema = Erro.__schema__
            cstruct = response.deserialize(schema)
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
