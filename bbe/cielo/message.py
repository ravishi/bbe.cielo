import colander
import contextlib
from xml.etree.ElementTree import ElementTree, Element, fromstring

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO


def isattrib(node):
    return getattr(node, 'attrib', False)


def gettag(node):
    return getattr(node, 'tag', node.name)


def _build_element(node):
    return Element(gettag(node))


def serialize(schema, cstruct):
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

        if subvalue is colander.null:
            continue

        if isattrib(child):
            element.attrib[subtag] = subvalue
        else:
            subelement = serialize(child, subvalue)
            if subelement is not None:
                element.append(subelement)

    return element


def deserialize(schema, etree):
    if isinstance(schema.typ, colander.Mapping):
        return _deserialize_mapping(schema, etree)

    if etree.text is None:
        return colander.null

    return etree.text


def _deserialize_mapping(schema, etree):
    cstruct = {}
    for child in schema.children:
        tag = gettag(child)
        if isattrib(child):
            value = etree.attrib.get(tag, colander.null)
        else:
            subelement = etree.find(tag)
            if subelement is None:
                value = colander.null
            else:
                value = deserialize(child, subelement)
        cstruct[child.name] = value
    return cstruct


def dumps(etree):
    if not isinstance(etree, ElementTree):
        etree = ElementTree(etree)
    with contextlib.closing(StringIO()) as s:
        etree.write(s)
        return s.getvalue()


def loads(string):
    return fromstring(string)
