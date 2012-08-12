import re
import colander
import contextlib
from lxml import etree

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO


def isattrib(node):
    return getattr(node, 'attrib', False)


def gettag(node):
    return getattr(node, 'tag', node.name)


def _build_element(node):
    return etree.Element(gettag(node))


def serialize(schema, cstruct):
    element = _serialize(schema, cstruct)
    return etree.ElementTree(element)


def _serialize(schema, cstruct):
    if cstruct is colander.null:
        return None

    if isinstance(schema.typ, colander.Mapping):
        return _serialize_mapping(schema, cstruct)
    else:
        element = _build_element(schema)
        element.text = cstruct
        return element


def _serialize_mapping(schema, cstruct):
    element = _build_element(schema)

    for child in schema:
        subtag = gettag(child)
        subvalue = cstruct.get(child.name, colander.null)

        # TODO: default, required, etc
        if subvalue is colander.null:
            continue

        if isattrib(child):
            element.attrib[subtag] = subvalue
        else:
            subelement = _serialize(child, subvalue)
            if subelement is not None:
                element.append(subelement)

    return element


def deserialize(schema, tree):
    element = tree.getroot()
    return _deserialize(schema, element)


def _deserialize(schema, element):
    if isinstance(schema.typ, colander.Mapping):
        return _deserialize_mapping(schema, element)

    if element.text is None:
        return colander.null

    return element.text


def _deserialize_mapping(schema, element):
    cstruct = {}
    for child in schema.children:
        tag = gettag(child)
        if isattrib(child):
            value = element.attrib.get(tag, colander.null)
        else:
            subelement = element.find(tag)
            if subelement is None:
                value = colander.null
            else:
                value = _deserialize(child, subelement)
        cstruct[child.name] = value
    return cstruct


def dumps(tree):
    #if isinstance(tree, etree.Element):
    #    tree = etree.ElementTree(tree)
    with contextlib.closing(StringIO()) as sio:
        tree.write(sio)
        s =  sio.getvalue()
        # XXX xml.etree.ElementTree does like ' />', while lxml.etree
        # does like '/>'. we don't know which one we'll use, so...
        s.replace(' />', '/>')
        return s


def loads(data):
    element = etree.fromstring(data)
    tree = etree.ElementTree(element)
    remove_namespaces(tree)
    return tree


def remove_namespaces(element):
    """Remove all namespaces in the passed element in place."""
    for ele in element.getiterator():
        ele.tag = re.sub(r'^\{[^\}]+\}', '', ele.tag)


def get_root_tag(tree):
    return tree.getroot().tag
