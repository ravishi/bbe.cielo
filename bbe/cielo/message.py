import re
import colander
from xml.etree.ElementTree import ParseError, ElementTree, Element, fromstring

# damn you, pyflakes! y u complain about this?
from StringIO import StringIO
#try:
#    from cStringIO import StringIO
#except:
#    from StringIO import StringIO


def serialize(schema, cstruct):
    """Serialize a cstruct into a message."""
    element = etreeify(schema, cstruct)
    etree = ElementTree(element)
    message = Message(etree_to_string(etree))
    message._etree = etree
    return message


def parse(message):
    """Parse a message and convert it to a :class:``Message``"""
    return Message.fromstring(message)


class Message(object):
    def serialize(self, schema):
        """Generate a message."""

    def deserialize(self, schema):
        """Generate a ``cstruct``."""

    @classmethod
    def fromstring(cls, message):
        """Parse ``message`` and build a new :class:`Message` instance.

        May raise :exc:`ParseError`.
        """
        try:
            etree = fromstring(message)
        except ParseError:
            pass

        return cls(etree)


def etree_to_string(etree):
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


def remove_namespaces(element):
    """Remove all namespaces in the passed element in place."""
    for ele in element.getiterator():
        ele.tag = re.sub(r'^\{[^\}]+\}', '', ele.tag)
