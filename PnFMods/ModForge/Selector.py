# coding=utf-8

import re

_STEP_RE = re.compile(r'([A-Za-z_*][\w.\-]*)((?:\[[^\]]*\])*)')
_PRED_RE = re.compile(r'\[([^\]]*)\]')

_ATTR_PRED_RE = re.compile(
    r"""^@([\w.\-]+)\s*(!?=)\s*(?:'([^']*)'|"([^"]*)")$""")
_ATTR_EXISTS_RE = re.compile(r'^@([\w.\-]+)$')
_TEXT_PRED_RE = re.compile(
    r"""^text\(\)\s*(!?=)\s*(?:'([^']*)'|"([^"]*)")$""")
_TEXT_EXISTS_RE = re.compile(r'^text\(\)$')
_VALUE_PRED_RE = re.compile(r"""^\.\s*(!?=)\s*(?:'([^']*)'|"([^"]*)")$""")
_CONTAINS_RE = re.compile(
    r"""^contains\(\s*(@[\w.\-]+|\.|text\(\))\s*,\s*"""
    r"""(?:'([^']*)'|"([^"]*)")\s*\)$""")
_POS_PRED_RE = re.compile(r'^(\d+|last\(\))$')

class SelectorError(Exception):
    pass

class _Predicate(object):
    __slots__ = ('kind', 'name', 'value', 'op')

    def __init__(self, kind, name, value, op='='):
        self.kind = kind
        self.name = name
        self.value = value
        self.op = op

    def matches(self, node):
        if self.kind == 'attr':
            if not node.hasAttribute(self.name):
                return False
            equal = node.getAttribute(self.name) == self.value
            return equal if self.op == '=' else not equal
        if self.kind == 'attrExists':
            return node.hasAttribute(self.name)
        if self.kind == 'text':
            found = self.value in _textChildren(node)
            return found if self.op == '=' else not found
        if self.kind == 'textExists':
            return bool(_textChildren(node))
        if self.kind == 'contains':
            if self.name is None:
                return self.value in _stringValue(node)
            if self.name == 'text()':
                for data in _textChildren(node):
                    if self.value in data:
                        return True
                return False
            if not node.hasAttribute(self.name):
                return False
            return self.value in node.getAttribute(self.name)
        if self.kind == 'value':
            equal = _stringValue(node) == self.value
            return equal if self.op == '=' else not equal
        return False

class _Step(object):
    __slots__ = ('tag', 'predicates', 'axis')

    def __init__(self, tag, predicates, axis='child'):
        self.tag = tag
        self.predicates = predicates
        self.axis = axis

def _splitSteps(expr):
    steps = []
    buf = []
    quote = None
    depth = 0
    for ch in expr:
        if quote is not None:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
        elif ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth < 0:
                raise SelectorError('unbalanced ] in selector: %s' % expr)
        elif ch == '/' and depth == 0:
            steps.append(''.join(buf))
            buf = []
            continue
        buf.append(ch)
    if quote is not None:
        raise SelectorError('unterminated %s quote in selector: %s'
                            % (quote, expr))
    if depth:
        raise SelectorError('unbalanced [ in selector: %s' % expr)
    steps.append(''.join(buf))
    return steps

splitSteps = _splitSteps

def parseSelector(expr):
    if not expr or not expr.strip():
        raise SelectorError('empty selector')
    steps = []
    descendant = False
    raws = _splitSteps(expr)
    for position, raw in enumerate(raws):
        raw = raw.strip()
        if not raw:
            if position == 0:
                raise SelectorError(
                    'absolute path is not supported: %s (use .// for a '
                    'descendant of the current node)' % expr)
            if descendant or position == len(raws) - 1:
                raise SelectorError('empty step in selector: %s' % expr)
            descendant = True
            continue

        axis = 'descendant' if descendant else 'child'
        descendant = False

        axisTag = None
        predPart = ''
        if raw == '.' or raw == '..':
            axisTag = raw
        elif raw.startswith('..[') or raw.startswith('.['):
            split = raw.index('[')
            axisTag = raw[:split]
            predPart = raw[split:]
            if axisTag not in ('.', '..'):
                raise SelectorError('invalid axis step: %s' % raw)
        if axisTag is not None:
            if axis == 'descendant':
                raise SelectorError(
                    "'%s' cannot follow // in selector: %s" % (axisTag, expr))
            preds = []
            for pm in _PRED_RE.finditer(predPart):
                p = _parsePredicate(pm.group(1).strip())
                if p.kind == 'pos':
                    raise SelectorError(
                        "positional predicate not allowed on '%s' axis (%s)"
                        % (axisTag, raw))
                preds.append(p)
            steps.append(_Step(axisTag, preds, axisTag))
            continue
        m = _STEP_RE.match(raw)
        if not m or m.end() != len(raw):
            raise SelectorError('invalid step: %s' % raw)
        tag, predPart = m.group(1), m.group(2)
        preds = []
        for pm in _PRED_RE.finditer(predPart):
            preds.append(_parsePredicate(pm.group(1).strip()))
        steps.append(_Step(tag, preds, axis))
    return steps

def _parsePredicate(body):
    m = _ATTR_PRED_RE.match(body)
    if m:
        value = m.group(3) if m.group(3) is not None else m.group(4)
        return _Predicate('attr', m.group(1), value, m.group(2))
    m = _ATTR_EXISTS_RE.match(body)
    if m:
        return _Predicate('attrExists', m.group(1), None)
    m = _TEXT_PRED_RE.match(body)
    if m:
        value = m.group(2) if m.group(2) is not None else m.group(3)
        return _Predicate('text', None, value, m.group(1))
    if _TEXT_EXISTS_RE.match(body):
        return _Predicate('textExists', None, None)
    m = _VALUE_PRED_RE.match(body)
    if m:
        value = m.group(2) if m.group(2) is not None else m.group(3)
        return _Predicate('value', None, value, m.group(1))
    m = _CONTAINS_RE.match(body)
    if m:
        target = m.group(1)
        value = m.group(2) if m.group(2) is not None else m.group(3)
        if target == '.':
            return _Predicate('contains', None, value)
        if target == 'text()':
            return _Predicate('contains', 'text()', value)
        return _Predicate('contains', target[1:], value)
    m = _POS_PRED_RE.match(body)
    if m:
        token = m.group(1)
        if token == 'last()':
            return _Predicate('pos', None, 'last')
        return _Predicate('pos', None, int(token))
    raise SelectorError('unsupported predicate: [%s]' % body)

def _applyPredicates(nodes, predicates):
    for pred in predicates:
        if not nodes:
            return []
        if pred.kind == 'pos':
            if pred.value == 'last':
                nodes = nodes[-1:]
            else:
                index = pred.value - 1
                nodes = [nodes[index]] if 0 <= index < len(nodes) else []
        else:
            nodes = [n for n in nodes if pred.matches(n)]
    return nodes

def findAll(rootNode, expr):
    steps = parseSelector(expr)
    current = [rootNode]
    for step in steps:
        if step.axis == '.':
            current = _applyPredicates(current, step.predicates)
        elif step.axis == '..':
            parents = []
            seen = set()
            for n in current:
                p = getattr(n, 'parentNode', None)
                if p is None or getattr(p, 'nodeType', 0) != 1:
                    continue
                pid = id(p)
                if pid in seen:
                    continue
                seen.add(pid)
                parents.append(p)
            current = _applyPredicates(parents, step.predicates)
        else:
            nextLevel = []
            for parent in current:
                if step.axis == 'descendant':
                    candidates = _descendantElements(parent, step.tag)
                else:
                    candidates = _directElementChildren(parent, step.tag)
                nextLevel.extend(_applyPredicates(candidates, step.predicates))
            current = nextLevel
        if not current:
            return []
    return current

def findFirst(rootNode, expr):
    matches = findAll(rootNode, expr)
    return matches[0] if matches else None

def exists(rootNode, expr):
    return bool(findAll(rootNode, expr))

def _directElementChildren(parent, tag):
    out = []
    for child in parent.childNodes:
        if child.nodeType != 1:
            continue
        if tag == '*' or child.tagName == tag:
            out.append(child)
    return out

def _descendantElements(parent, tag):
    out = []
    for child in parent.childNodes:
        if child.nodeType != 1:
            continue
        if tag == '*' or child.tagName == tag:
            out.append(child)
        out.extend(_descendantElements(child, tag))
    return out

def _textChildren(node):
    return [c.data for c in node.childNodes if c.nodeType in (3, 4)]

def _stringValue(node):
    parts = []
    for child in node.childNodes:
        if child.nodeType in (3, 4):
            parts.append(child.data)
        elif child.nodeType == 1:
            parts.append(_stringValue(child))
    return ''.join(parts)
