# -*- coding: utf-8 -*-
"""
As informações abaixo podem ser usadas pelo desenvolvedor durante o desenvolvimento da
integração.

    - Cartão com autenticação: 4012001037141112 (visa)
    - Cartão sem autenticação: 4551870000000183 (visa),  5453010000066167 (mastercard),
      6362970000457013 (elo), 36490102462661 (diners) e 6011020000245045 (discover).
    - Data de validade: qualquer posterior ao corrente
    - Código de segurança: qualquer
    - Valor do pedido: para simular transação autorizada, use qualquer valor em que os
      dois últimos dígitos sejam zeros. Do contrário, toda autorização será negada.
    - Credenciais

        Leitura do cartão   Número      Chave
        Loja                1006993069  25fbb99741c739dd84d7b06ec78c9bac718838630f30b112d033ce2e621b34f3
        Cielo               1001734898  e84827130b9837473681c2787007da5914d6359947015a5cdb2b8843db0fa832


Ambientes
=========

Teste:      https://qasecommerce.cielo.com.br/servicos/ecommwsec.do
Produção:   https://ecommerce.cbmp.com.br/servicos/ecommwsec.do
"""
import uuid
import datetime
import colander
import unittest
from decimal import Decimal

import bbe.cielo as cielo


def nextmonth():
    return datetime.datetime.today() + datetime.timedelta(days=31)


class DinheiroTestCase(unittest.TestCase):
    def setUp(self):
        self.node = colander.SchemaNode(cielo.Dinheiro())

    def test_serialize_integer(self):
        i = 200
        self.assertEqual(self.node.serialize(i), '20000')

    def test_serialize_float(self):
        f = 200.0
        self.assertEqual(self.node.serialize(f), '20000')

        f2 = 199.5
        self.assertEqual(self.node.serialize(f2), '19950')

        f3 = 200.21
        self.assertEqual(self.node.serialize(f3), '20021')

    def test_serialize_decimal(self):
        d = Decimal('200.00')
        self.assertEqual(self.node.serialize(d), '20000')

        d2 = Decimal('91823.2')
        self.assertEqual(self.node.serialize(d2), '9182320')

        d3 = Decimal('200.21')
        self.assertEqual(self.node.serialize(d3), '20021')

    def test_serialization_fails_for_invalid_values(self):
        """
        Valores inválidos são, basicamente, valores com mais
        de duas casas decimais.
        """
        f = 200.213
        self.assertRaises(colander.Invalid, self.node.serialize, f)

        d = Decimal('400.5412')
        self.assertRaises(colander.Invalid, self.node.serialize, d)

        self.assertRaises(colander.Invalid, self.node.serialize, 'notanumber')

    def test_deserialization(self):
        self.assertEqual(
            self.node.deserialize('20000'),
            200
        )

        self.assertEqual(
            self.node.deserialize('20030'),
            Decimal('200.30')
        )

        self.assertEqual(
            self.node.deserialize('20054'),
            Decimal('200.54')
        )


class ClienteTestCase(unittest.TestCase):
    def setUp(self):
        self.ec = cielo.Estabelecimento(
            numero='1006993069',
            chave='25fbb99741c739dd84d7b06ec78c9bac718838630f30b112d033ce2e621b34f3',
        )
        self.cliente = cielo.Cliente(
            url='https://qasecommerce.cielo.com.br/servicos/ecommwsec.do',
        )


class ClientTestCase(ClienteTestCase):
    def test_criacao_transacao(self):
        valor = 200

        portador = cielo.Portador(
            numero="4012001037141112", validade=nextmonth(),
            codigo_seguranca="123", nome="Augusto")
        pedido = cielo.Pedido(numero="1", valor=valor, data=datetime.datetime.now())
        pagamento = cielo.FormaPagamento(bandeira=cielo.VISA, parcelas=2, produto=cielo.PARCELADO_ADMINISTRADORA)

        t = self.cliente.nova_transacao(
            ec=self.ec, portador=portador, pedido=pedido, pagamento=pagamento,
            url_retorno="http://www.example.com/", autorizar=3, capturar=True)

        self.assertTrue(t.tid)
        self.assertEqual(t.status, cielo.ST_CAPTURADA)
        self.assertEqual(t.autorizacao.lr, 0)

        self.assertIsNotNone(t.autenticacao)
        self.assertIsNotNone(t.autorizacao)
        self.assertIsNotNone(t.captura)
        self.assertIsNone(t.cancelamento)

        self.assertEqual(t.autenticacao.valor, valor)
        self.assertEqual(t.autorizacao.valor, valor)

        # A loja optou por autorizar sem passar pela autenticacação
        self.assertEqual(t.autenticacao.eci, 7)
        self.assertEqual(t.autenticacao.mensagem, u"Transacao sem autenticacao")

    def test_transacao_nao_autorizada(self):
        valor = Decimal('200.21')

        portador = cielo.Portador(
            numero="4012001037141112", validade=nextmonth(),
            codigo_seguranca="123", nome="Augusto")
        pedido = cielo.Pedido(numero="1", valor=valor, data=datetime.datetime.now())
        pagamento = cielo.FormaPagamento(bandeira=cielo.VISA, parcelas=2, produto=cielo.PARCELADO_ADMINISTRADORA)

        t = self.cliente.nova_transacao(
            ec=self.ec, portador=portador, pedido=pedido, pagamento=pagamento,
            url_retorno="http://www.example.com/", autorizar=3, capturar=True)

        self.assertTrue(t.tid)
        self.assertEqual(t.status, cielo.ST_NAO_AUTORIZADA)
        self.assertEqual(t.autorizacao.lr, 21)

        self.assertIsNotNone(t.autenticacao)
        self.assertIsNotNone(t.autorizacao)
        self.assertIsNone(t.captura)
        self.assertIsNone(t.cancelamento)

        self.assertEqual(t.autenticacao.valor, valor)
        self.assertEqual(t.autorizacao.valor, valor)

        # A loja optou por autorizar sem passar pela autenticacação
        self.assertEqual(t.autenticacao.eci, 7)
        self.assertEqual(t.autenticacao.mensagem, u"Transacao sem autenticacao")

    def test_transacao_capturada(self):
        valor = Decimal('200.00')

        portador = cielo.Portador(
            numero="5453010000066167", validade=nextmonth(),
            codigo_seguranca="123", nome="Augusto")
        pedido = cielo.Pedido(numero="1", valor=valor, data=datetime.datetime.now())
        pagamento = cielo.FormaPagamento(bandeira=cielo.VISA, parcelas=2, produto=cielo.PARCELADO_ADMINISTRADORA)

        t = self.cliente.nova_transacao(
            ec=self.ec, portador=portador, pedido=pedido, pagamento=pagamento,
            url_retorno="http://www.example.com/", autorizar=3, capturar=True)

        self.assertTrue(t.tid)
        self.assertEqual(t.status, cielo.ST_CAPTURADA)
        self.assertEqual(t.autorizacao.lr, 0)

        self.assertIsNotNone(t.autenticacao)
        self.assertIsNotNone(t.autorizacao)
        self.assertIsNotNone(t.captura)
        self.assertIsNone(t.cancelamento)

        self.assertEqual(t.autenticacao.valor, valor)
        self.assertEqual(t.autorizacao.valor, valor)

        # A loja optou por autorizar sem passar pela autenticacação
        self.assertEqual(t.autenticacao.eci, 7)
        self.assertEqual(t.autenticacao.mensagem, u"Transacao sem autenticacao")

    def test_consulta_tid(self):
        valor = Decimal('200.00')

        portador = cielo.Portador(
            numero="5453010000066167", validade=nextmonth(),
            codigo_seguranca="123", nome="Augusto")
        pedido = cielo.Pedido(numero="1", valor=valor, data=datetime.datetime.now())
        pagamento = cielo.FormaPagamento(bandeira=cielo.VISA, parcelas=2, produto=cielo.PARCELADO_ADMINISTRADORA)

        t = self.cliente.nova_transacao(
            ec=self.ec, portador=portador, pedido=pedido, pagamento=pagamento,
            url_retorno="http://www.example.com/", autorizar=3, capturar=True)

        self.assertTrue(t.tid)

        t2 = self.cliente.consultar_tid(self.ec, t.tid)
        self.assertEqual(t.tid, t2.tid)

    def test_consulta_pedido(self):
        valor = Decimal('200.00')
        numero_pedido = str(uuid.uuid4()).replace('-', '')[:20]

        portador = cielo.Portador(
            numero="5453010000066167", validade=nextmonth(),
            codigo_seguranca="123", nome="Augusto")
        pedido = cielo.Pedido(numero=numero_pedido, valor=valor, data=datetime.datetime.now())
        pagamento = cielo.FormaPagamento(bandeira=cielo.VISA, parcelas=2, produto=cielo.PARCELADO_ADMINISTRADORA)

        t = self.cliente.nova_transacao(
            ec=self.ec, portador=portador, pedido=pedido, pagamento=pagamento,
            url_retorno="http://www.example.com/", autorizar=3, capturar=True)

        self.assertTrue(t.tid)

        t2 = self.cliente.consultar_pedido(self.ec, numero_pedido)
        self.assertEqual(t.tid, t2.tid)

    def test_captura_manual(self):
        valor = Decimal('200.00')
        numero_pedido = str(uuid.uuid4()).replace('-', '')[:20]

        portador = cielo.Portador(
            numero="5453010000066167", validade=nextmonth(),
            codigo_seguranca="123", nome="Frederico")
        pedido = cielo.Pedido(numero=numero_pedido, valor=valor, data=datetime.datetime.now())
        pagamento = cielo.FormaPagamento(bandeira=cielo.VISA, parcelas=2, produto=cielo.PARCELADO_ADMINISTRADORA)

        t = self.cliente.nova_transacao(
            ec=self.ec, portador=portador, pedido=pedido, pagamento=pagamento,
            url_retorno="http://www.example.com/", autorizar=3, capturar=False)

        self.assertTrue(t.tid)
        self.assertEqual(t.status, cielo.ST_AUTORIZADA)

        t2 = self.cliente.capturar(self.ec, tid=t.tid)
        self.assertEqual(t2.tid, t.tid)
        self.assertEqual(t2.status, cielo.ST_CAPTURADA)


class ErrorTestCase(ClienteTestCase):
    def test_erro_1(self):
        """
        001 Mensagem inválida. A mensagem XML está fora do formato
        especificado pelo arquivo ecommerce.xsd.
        """
        pass

    def test_erro_10(self):
        """
        Erro 10: Inconsistência no enviodo cartão. A transação,
        com ou sem cartão, está divergente com a permissão de envio
        dessa informação.
        """
        valor = 200

        pedido = cielo.Pedido(numero="1", valor=valor, data=datetime.datetime.now())
        pagamento = cielo.FormaPagamento(bandeira=cielo.VISA, parcelas=2, produto=cielo.PARCELADO_ADMINISTRADORA)

        try:
            self.cliente.nova_transacao(
                ec=self.ec, pedido=pedido, pagamento=pagamento,
                url_retorno="http://www.example.com/", autorizar=3,
                capturar=True)
        except cielo.Erro, e:
            self.assertEqual(e.codigo, 10)
        else:
            self.fail("Uma transacao invalida nao falhou como esperado")
