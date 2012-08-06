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
        self.assertDumps(node, {}, '<node />')


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
        node.add(colander.SchemaNode(colander.String(), name='a'))
        node.add(colander.SchemaNode(colander.String(), name='b'))
        node.add(colander.SchemaNode(colander.String(), name='c'))
        self.assertLoads(node, '<node />', {})

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

    def test_deserialization(self):
        self.assertDeserialize('43200', Decimal('432.00'))
        self.assertDeserialize('87720', Decimal('877.2'))
        self.assertDeserialize('12311', Decimal('123.11'))

    def test_non_numeric_values_serialization(self):
        "Obviously, non-numeric vaulues are invalid"
        self.assertRaises(colander.Invalid, self.node.serialize, None)
        self.assertRaises(colander.Invalid, self.node.serialize, 'notanumber')
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
        self.establishment = cielo.Establishment(
            '1006993069',
            '25fbb99741c739dd84d7b06ec78c9bac718838630f30b112d033ce2e621b34f3',
        )
        self.client = cielo.Client(
            url='https://qasecommerce.cielo.com.br/servicos/ecommwsec.do',
        )


class MonolithicTestCase(TestCase):
    def test_transaction(self):
        order = cielo.Order(date=datetime.datetime.now(),
                            value=Decimal('200.0'))
        payment = cielo.CreditCardPayment(
            card_number='4012001037141112',
            card_expiration_date=nextmonth(),
            card_security_code='123',
            card_holder_name='Joao da Silva',
            card_brand=cielo.VISA,
            value=order.value,
            date=order.date,
            plots=2,
        )
        self.client.new_transaction(
            order=order,
            payment=payment,
        )
