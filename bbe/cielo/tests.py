# -*- coding: utf-8 -*-
from decimal import Decimal
import colander
import datetime
import unittest
import bbe.cielo as cielo


def nextmonth():
    return datetime.datetime.now() + datetime.timedelta(days=30)


class MessageSerializationTestCase(unittest.TestCase):
    def assertDumps(self, node, appstruct, test):
        cstruct = node.serialize(appstruct)
        etree = cielo.message.serialize(node, cstruct)
        s = cielo.message.dumps(etree)
        return self.assertEqual(s, test)

    def test_serialization(self):
        node = colander.SchemaNode(colander.String(), name='node')
        self.assertDumps(node, 'abcdef', '<node>abcdef</node>')

    def test_serialization_with_tag(self):
        node = colander.SchemaNode(colander.String(), name='node', tag='node-tag')
        self.assertDumps(node, 'abcdef', '<node-tag>abcdef</node-tag>')

    def test_subnode_serialization(self):
        node = colander.SchemaNode(colander.Mapping(), name='node')
        node.add(colander.SchemaNode(colander.String(), name='sub'))

        self.assertDumps(node, {'sub': 'abcdef'}, '<node><sub>abcdef</sub></node>')

    def test_subnode_serialization_order(self):
        "Subnode serialization must follow schema's order"
        node = colander.SchemaNode(colander.Mapping(), name='node')
        node.add(colander.SchemaNode(colander.String(), name='a'))
        node.add(colander.SchemaNode(colander.String(), name='b'))
        node.add(colander.SchemaNode(colander.String(), name='c'))

        appstruct = {'a': 'value-1', 'b': 'value-2', 'c': 'value-3'}

        #self.assertNotEqual(appstruct.keys(), ['a', 'b', 'c'])
        self.assertDumps(node, appstruct, '<node><a>value-1</a><b>value-2</b><c>value-3</c></node>')

    def test_empty_mapping_serialization(self):
        node = colander.SchemaNode(colander.Mapping(), name='node')
        node.add(colander.SchemaNode(colander.String(), name='a'))
        node.add(colander.SchemaNode(colander.String(), name='b'))
        node.add(colander.SchemaNode(colander.String(), name='c'))
        self.assertDumps(node, {}, '<node/>')

    def test_null_mapping_serialization(self):
        node = colander.SchemaNode(colander.Mapping(), name='node')
        node.add(colander.SchemaNode(colander.String(), name='a'))
        node.add(colander.SchemaNode(colander.String(), name='b'))
        node.add(colander.SchemaNode(colander.String(), name='c'))
        self.assertDumps(node, colander.null, '<node/>')


class MessageDeserializationTestCase(unittest.TestCase):
    def assertLoads(self, node, message, test):
        etree = cielo.message.loads(message)
        cstruct = cielo.message.deserialize(node, etree)
        appstruct = node.deserialize(cstruct)
        return self.assertEqual(appstruct, test)

    def test_serialization(self):
        node = colander.SchemaNode(colander.String(), name='node')
        self.assertLoads(node, '<node>abcdef</node>', 'abcdef')

    def test_deserialization_with_tags(self):
        node = colander.SchemaNode(colander.String(), name='node', tag='node-tag')
        self.assertLoads(node, '<node-tag>abcdef</node-tag>', 'abcdef')

    def test_subnode_deserialization(self):
        node = colander.SchemaNode(colander.Mapping(), name='node')
        node.add(colander.SchemaNode(colander.String(), name='sub'))
        self.assertLoads(node, '<node><sub>abcdef</sub></node>', {'sub': 'abcdef'})

    def test_empty_mapping_deserialization(self):
        node = colander.SchemaNode(colander.Mapping(), name='node')
        node.add(colander.SchemaNode(colander.String(), name='a', missing=colander.null))
        node.add(colander.SchemaNode(colander.String(), name='b', missing=colander.null))
        node.add(colander.SchemaNode(colander.String(), name='c', missing=colander.null))
        self.assertLoads(node, '<node/>', {'a': colander.null, 'b': colander.null, 'c': colander.null})


class MoneyTestCase(unittest.TestCase):
    def setUp(self):
        self.node = colander.SchemaNode(cielo.Money())

    def assertSerialize(self, appstruct, cstruct):
        self.assertEqual(self.node.serialize(appstruct), cstruct)

    def assertDeserialize(self, cstruct, appstruct):
        self.assertEqual(self.node.deserialize(cstruct), appstruct)

    def test_null_serialization(self):
        self.assertSerialize(colander.null, colander.null)

    def test_null_deserialization(self):
        node = self.node.clone()
        node.missing = colander.null
        self.assertEqual(node.deserialize(colander.null), colander.null)

    def test_integer_serialization(self):
        self.assertSerialize(188, '18800')

    def test_float_serialization(self):
        self.assertSerialize(333.0, '33300')
        self.assertSerialize(333.1, '33310')
        self.assertSerialize(333.11, '33311')

    def test_decimal_serialization(self):
        self.assertSerialize(Decimal('123.00'), '12300')
        self.assertSerialize(Decimal('123.5'), '12350')
        self.assertSerialize(Decimal('123.56'), '12356')

    def test_decimal_with_lots_of_zeroes_serialization(self):
        "We should ignore useless zeroes of decimal values"
        self.assertSerialize(Decimal('1.00000000'), '100')
        self.assertSerialize(Decimal('1.23000'), '123')

    def test_deserialization(self):
        self.assertDeserialize('43200', Decimal('432.00'))
        self.assertDeserialize('87720', Decimal('877.2'))
        self.assertDeserialize('12311', Decimal('123.11'))

    def test_non_numeric_values_serialization(self):
        "Obviously, non-numeric vaulues are invalid"
        self.assertRaises(colander.Invalid, self.node.serialize, None)
        self.assertRaises(colander.Invalid, self.node.serialize, 'notanumber')

    @unittest.skip("i'm not sure about this one")
    def test_string_numeric_values_deserialization(self):
        self.assertRaises(colander.Invalid, self.node.serialize, '42')

    def test_non_numeric_values_deserialization(self):
        "Obviously, non-numeric values will be invalid during deserialization"
        self.assertRaises(colander.Invalid, self.node.deserialize, None)
        self.assertRaises(colander.Invalid, self.node.deserialize, 'notanumber')

    def test_invalid_monetary_values(self):
        "Values with more than two decimal places are invalid"
        self.assertRaises(colander.Invalid, self.node.serialize, 100.123)
        self.assertRaises(colander.Invalid, self.node.serialize, Decimal('200.543'))


# do not trust these

class TestCase(unittest.TestCase):
    def setUp(self):
        self.client = cielo.Client(
            store_id='1006993069',
            store_key='25fbb99741c739dd84d7b06ec78c9bac718838630f30b112d033ce2e621b34f3',
            service_url='https://qasecommerce.cielo.com.br/servicos/ecommwsec.do',
            default_installment_type=cielo.PARCELADO_ADMINISTRADORA,
        )


class ClientResponseTest(TestCase):
    def test_process_response(self):
        response = self.client.process_response(
            u"""<?xml version="1.0" encoding="ISO-8859-1"?>
                <transacao versao="1.1.1" id="f71e286f-21f6-4abe-8999-cc200e585454" xmlns="http://ecommerce.cbmp.com.br">
                  <tid>100699306905227C1001</tid>
                  <pan>uv9yI5tkhX9jpuCt+dfrtoSVM4U3gIjvrcwMBfZcadE=</pan>
                  <dados-pedido>
                    <numero>1</numero>
                    <valor>20000</valor>
                    <moeda>96</moeda>
                    <data-hora>2012-08-11T08:48:23.659-03:00</data-hora>
                    <idioma>PT</idioma>
                  </dados-pedido>
                  <forma-pagamento>
                    <bandeira>visa</bandeira>
                    <produto>1</produto>
                    <parcelas>1</parcelas>
                  </forma-pagamento>
                  <status>5</status>
                  <autenticacao>
                    <codigo>5</codigo>
                    <mensagem>Transacao sem autenticacao</mensagem>
                    <data-hora>2012-08-11T08:48:23.695-03:00</data-hora>
                    <valor>20000</valor>
                    <eci>7</eci>
                  </autenticacao>
                  <autorizacao>
                    <codigo>5</codigo>
                    <mensagem>Autorização negada</mensagem>
                    <data-hora>2012-08-11T08:48:43.708-03:00</data-hora>
                    <valor>20000</valor>
                    <lr>999</lr>
                    <nsu>336508</nsu>
                  </autorizacao>
                </transacao>""".encode('iso-8859-1'))
        self.assertIsInstance(response, cielo.Transaction)
        self.assertEqual(response.status, 5)
        self.assertEqual(response.authorization.code, 5)

    def test_process_error_response(self):
        response = u"""<?xml version="1.0" encoding="ISO-8859-1"?>
                         <erro>
                         <codigo>032</codigo>
                         <mensagem>Valor de captura inválido</mensagem>
                       </erro>""".encode('iso-8859-1')

        self.assertRaises(cielo.Error, self.client.process_response, response)

    def test_credit_payment(self):
        card = cielo.Card(
            brand=cielo.VISA,
            number='4551870000000183',
            expiration_date=nextmonth(),
            security_code='123',
            holder_name='Joao da Silva',
        )
        payment = self.client.create_transaction(
            value=Decimal('200.0'),
            card=card,
            installments=1,
            authorize=3,
            capture=False,
        )

        self.assertIsInstance(payment, cielo.Transaction)
        self.assertTrue(payment.tid)
        self.assertTrue(payment.order)
        self.assertTrue(payment.datetime)


class QueryTestCase(TestCase):
    def setUp(self):
        super(QueryTestCase, self).setUp()

        card = cielo.Card(
            brand=cielo.VISA,
            number='4551870000000183',
            expiration_date=nextmonth(),
            security_code='123',
            holder_name='Joao da Silva',
        )
        self.payment = self.client.create_transaction(
            value=Decimal('200.0'),
            card=card,
            installments=1,
            authorize=3,
            capture=False,
        )

        assert isinstance(self.payment, cielo.Transaction)
        assert self.payment.tid
        assert self.payment.order

    def test_query_by_tid(self):
        payment = self.client.query_by_tid(self.payment.tid)
        self.assertEqual(payment.tid, self.payment.tid)

    def test_query_by_order_number(self):
        payment = self.client.query_by_order_number(self.payment.order)
        self.assertEqual(payment.tid, self.payment.tid)
        self.assertEqual(payment.order, self.payment.order)

    def test_cancel(self):
        payment = self.client.cancel_transaction(self.payment.tid)
        self.assertEqual(payment.tid, self.payment.tid)
        self.assertEqual(payment.status, cielo.ST_CANCELLED)

"""
As informações abaixo podem ser usadas pelo desenvolvedor durante
o desenvolvimento da integração. Cartão com autenticação:
    4012001037141112 (visa)
Cartão sem autenticação: 4551870000000183 (visa), 5453010000066167 (mastercard),
6362970000457013 (elo), 36490102462661 (diners) e 6011020000245045 (discover).
Data de validade: qualquer posterior ao corrente
Código de segurança: qualquer
Valor do pedido: para simular transação autorizada, use qualquer valor em que os dois
últimos dígitos sejam zeros. Do contrário, toda autorização será negada.
Credenciais
Leitura
Número
 Chave
do
cartão
Loja
 1006993069 25fbb99741c739dd84d7b06ec78c9bac718838630f30b112d033ce2e621b34f3
Cielo
 1001734898 e84827130b9837473681c2787007da5914d6359947015a5cdb2b8843db0fa832
"""
