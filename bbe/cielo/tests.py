# -*- coding: utf-8 -*-
from decimal import Decimal
import colander
import datetime
import unittest
import bbe.cielo as cielo


def nextmonth():
    return datetime.datetime.now() + datetime.timedelta(days=30)


class MoneyTestCase(unittest.TestCase):
    def setUp(self):
        self.node = colander.SchemaNode(cielo.Money())

    def assertSerialize(self, appstruct, cstruct):
        self.assertEqual(self.node.serialize(appstruct), cstruct)

    def assertDeserialize(self, cstruct, appstruct):
        self.assertEqual(self.node.deserialize(cstruct), appstruct)

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

    def test_not_number(self):
        "Obviously, non-numeric vaulues are invalid"
        self.assertRaises(colander.Invalid, self.node.serialize, None)
        self.assertRaises(colander.Invalid, self.node.serialize, 'notanumber')

    def test_invalid_values(self):
        "Values with more than two decimal places are invalid"
        self.assertRaises(colander.Invalid, self.node.serialize, 100.123)
        self.assertRaises(colander.Invalid, self.node.serialize, Decimal('200.543'))

    def test_deserialization(self):
        self.assertDeserialize('43200', Decimal('432.00'))
        self.assertDeserialize('87720', Decimal('877.2'))
        self.assertDeserialize('12311', Decimal('123.11'))


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
