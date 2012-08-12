# -*- coding: utf-8 -*-
import colander
import uuid
from collections import OrderedDict
from itertools import chain
from .schema import *
from .client import Client, Order, Payment, DebitPayment


SERVICE_VERSION = '1.1.1'
