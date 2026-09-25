# coding=utf-8

from xml.dom import minidom as _minidom

from Actions import applyAction

class BuildError(Exception):
    pass

def buildDocument(spec, modName, sources):
    try:
        doc = _minidom.parseString('<%s/>' % spec.root)
    except Exception as exc:
        raise BuildError("cannot start a <%s> document: %s"
                         % (spec.root, exc))
    try:
        for action in spec.actions:
            applyAction(doc, action, modName, None, sources)
        return serialize(doc)
    finally:
        doc.unlink()

def serialize(doc):
    root = doc.documentElement
    parts = []
    for child in root.childNodes:
        if child.nodeType == child.ELEMENT_NODE:
            parts.append(child.toxml())
    out = '<%s>\n%s\n</%s>\n' % (root.tagName, '\n'.join(parts), root.tagName)
    if isinstance(out, unicode):
        out = out.encode('utf-8')
    return out

def sourceFiles(actions, out=None):
    if out is None:
        out = []
    for action in actions:
        if action.kind == 'copy' and action.source:
            out.append(action.source)
        if action.actions:
            sourceFiles(action.actions, out)
    return out
