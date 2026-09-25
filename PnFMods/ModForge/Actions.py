# coding=utf-8

from xml.dom import minidom as _minidom

import Selector
from Logger import logInfo
from Codec import _u2

class ActionError(Exception):
    pass

# Claim markers live ON the node, written by applySetAttribute when a tracker
# is passed. Stripped before the document is serialized.
CLAIM_PREFIX = '_forgeClaim-'

def _etToMinidomNodes(etElements, ownerDoc):
    out = []
    for el in etElements:
        xml = _u2.tostring(el)
        if xml.startswith('<?xml'):
            xml = xml.split('?>', 1)[1]
        parsed = _minidom.parseString(xml)
        imported = ownerDoc.importNode(parsed.documentElement, True)
        parsed.unlink()
        out.append(imported)
    return out

def _resolveInsertionPoint(root, into, before, after):
    if into:
        parent = Selector.findFirst(root, into)
        if parent is None:
            raise ActionError('into= selector matched nothing: %s' % into)
        if before:
            anchor = Selector.findFirst(parent, before)
            if anchor is None:
                raise ActionError(
                    "before= selector matched nothing inside into= scope: %s"
                    % before)
            return parent, anchor
        if after:
            anchor = Selector.findFirst(parent, after)
            if anchor is None:
                raise ActionError(
                    "after= selector matched nothing inside into= scope: %s"
                    % after)
            return parent, _nextElementSibling(anchor)
        return parent, None
    if before:
        anchor = Selector.findFirst(root, before)
        if anchor is None:
            raise ActionError('before= selector matched nothing: %s' % before)
        return anchor.parentNode, anchor
    if after:
        anchor = Selector.findFirst(root, after)
        if anchor is None:
            raise ActionError('after= selector matched nothing: %s' % after)
        return anchor.parentNode, _nextElementSibling(anchor)
    raise ActionError('no insertion target specified')

def _nextElementSibling(node):
    return node.nextSibling

def _canonical(node):
    pairs = []
    if node.attributes:
        pairs = sorted((k, node.getAttribute(k))
                       for k in node.attributes.keys()
                       if not k.startswith(CLAIM_PREFIX))
    text = ''.join(c.data for c in node.childNodes
                   if c.nodeType == c.TEXT_NODE).strip()
    kids = [_canonical(c) for c in node.childNodes
            if c.nodeType == c.ELEMENT_NODE]
    # repr, not a joined string: a value holding the separator must not
    # collide with a different attribute set.
    return repr((node.tagName, pairs, text, kids))

def stripClaims(node):
    if node.nodeType == node.ELEMENT_NODE and node.attributes:
        for key in [k for k in node.attributes.keys()
                    if k.startswith(CLAIM_PREFIX)]:
            node.removeAttribute(key)
    for child in node.childNodes:
        stripClaims(child)

def _childKeys(parent):
    return set(_canonical(c) for c in parent.childNodes
               if c.nodeType == c.ELEMENT_NODE)

def _insertDeduped(parent, nodes, anchor, label):
    present = _childKeys(parent)
    inserted = 0
    for node in nodes:
        if _canonical(node) in present:
            logInfo('%s: <%s> is already present in <%s>; skipped'
                    % (label, node.tagName, parent.tagName))
            continue
        parent.insertBefore(node, anchor)
        inserted += 1
    return inserted

def evaluateGuards(root, guards):
    for g in guards:
        if g.kind == 'ifExists':
            if not Selector.exists(root, g.expr):
                return False
        elif g.kind == 'ifNotExists':
            if Selector.exists(root, g.expr):
                return False
    return True

def applyInsert(doc, action, label, root, sources, claims=None):
    parent, anchor = _resolveInsertionPoint(root, action.into,
                                            action.before, action.after)
    nodes = _etToMinidomNodes(action.payload, doc)
    return _insertDeduped(parent, nodes, anchor, label)

def applyRemove(doc, action, label, root, sources, claims=None):
    matches = Selector.findAll(root, action.select)
    if not matches:
        raise ActionError('remove select matched nothing: %s' % action.select)
    for node in matches:
        node.parentNode.removeChild(node)
    return len(matches)

def applyReplace(doc, action, label, root, sources, claims=None):
    matches = Selector.findAll(root, action.select)
    if not matches:
        raise ActionError('replace select matched nothing: %s' % action.select)
    replacementNodes = _etToMinidomNodes(action.payload, doc)
    for target in matches:
        parent = target.parentNode
        anchor = target.nextSibling
        parent.removeChild(target)
        for rep in replacementNodes:
            clone = rep.cloneNode(True)
            parent.insertBefore(clone, anchor)
    return len(matches)

def applySetAttribute(doc, action, label, root, sources, claims=None):
    if action.select is None:
        matches = [root]
    else:
        matches = Selector.findAll(root, action.select)
        if not matches:
            raise ActionError('setAttribute select matched nothing: %s'
                              % action.select)
    changed = 0
    for node in matches:
        if action.fromValue is None:
            value = action.toValue
        else:
            if not node.hasAttribute(action.attribute):
                continue
            current = node.getAttribute(action.attribute)
            if action.fromValue not in current:
                continue
            value = current.replace(action.fromValue, action.toValue)
        # Only a write claims: a from= that finds nothing must not refuse a peer.
        if claims is not None and not claims.claim(node, action.attribute,
                                                   label):
            continue
        node.setAttribute(action.attribute, value)
        changed += 1
    return changed

def applyCopy(doc, action, label, root, sources, claims=None):
    if action.source:
        if sources is None:
            raise ActionError('copy from= is not available here: %s'
                              % action.source)
        found = sources.find(action.source, action.select)
        if not found:
            raise ActionError('copy select matched nothing in %s: %s'
                              % (action.source, action.select))
    else:
        found = Selector.findAll(root, action.select)
        if not found:
            raise ActionError('copy select matched nothing: %s'
                              % action.select)
    parent, anchor = _resolveInsertionPoint(root, action.into,
                                            action.before, action.after)

    count = 0
    for src in found:
        clone = (doc.importNode(src, True) if action.source
                 else src.cloneNode(True))
        # A clone is a new node; its original's claims are not its own.
        stripClaims(clone)
        for nested in action.actions:
            applyAction(doc, nested, label, clone, sources, claims)
        parent.insertBefore(clone, anchor)
        count += 1
    return count

_DISPATCH = {
    'insert': applyInsert,
    'remove': applyRemove,
    'replace': applyReplace,
    'setAttribute': applySetAttribute,
    'copy': applyCopy,
}

def applyAction(doc, action, label='', root=None, sources=None, claims=None):
    fn = _DISPATCH.get(action.kind)
    if fn is None:
        raise ActionError('unknown action kind: %s' % action.kind)
    if root is None:
        root = doc.documentElement
    return fn(doc, action, label, root, sources, claims)
