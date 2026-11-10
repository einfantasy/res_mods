# coding=utf-8

import re

class RequiresError(Exception):
    pass

MOD_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_KEYWORDS = ('and', 'or', 'not')

_TOKEN_RE = re.compile(
    r'\s*(?:(>=|<=|==|>|<)|([()!])|([A-Za-z_][A-Za-z0-9_]*)|(\d+(?:\.\d+)*))')

def nameProblem(name):

    if not MOD_NAME_RE.match(name or ''):
        return ('a mod name is letters, digits and _ only, and does not start '
                'with a digit')
    if name.lower() in _KEYWORDS:
        return "'and', 'or' and 'not' are reserved"
    return None

def parse(text):

    tokens = _tokenize(text)
    if not tokens:
        raise RequiresError('it is empty')
    node, pos = _parseOr(tokens, 0)
    if pos != len(tokens):
        raise RequiresError("unexpected '%s'; join two conditions with 'and' "
                            "or 'or'" % tokens[pos][1])
    return node

def _tokenize(text):
    out = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if m is None:
            rest = text[pos:].lstrip()
            if rest.startswith('='):
                raise RequiresError("'=' is not an operator; an exact version "
                                    "is ==")
            raise RequiresError("cannot read '%s'" % rest[:20])
        if m.group(1):
            out.append(('op', m.group(1)))
        elif m.group(2):
            out.append((m.group(2), m.group(2)))
        elif m.group(3):
            word = m.group(3)
            if word not in _KEYWORDS and word.lower() in _KEYWORDS:
                raise RequiresError("write '%s' in lower case" % word.lower())
            out.append((word if word in _KEYWORDS else 'name', word))
        else:
            out.append(('version', m.group(4)))
        pos = m.end()
    return out

def _kind(tokens, pos):
    return tokens[pos][0] if pos < len(tokens) else None

def _parseOr(tokens, pos):
    node, pos = _parseAnd(tokens, pos)
    nodes = [node]
    while _kind(tokens, pos) == 'or':
        node, pos = _parseAnd(tokens, pos + 1)
        nodes.append(node)
    return (nodes[0] if len(nodes) == 1 else ('or', nodes)), pos

def _parseAnd(tokens, pos):
    node, pos = _parseUnary(tokens, pos)
    nodes = [node]
    while _kind(tokens, pos) == 'and':
        node, pos = _parseUnary(tokens, pos + 1)
        nodes.append(node)
    return (nodes[0] if len(nodes) == 1 else ('and', nodes)), pos

def _parseUnary(tokens, pos):
    kind = _kind(tokens, pos)
    if kind in ('not', '!'):
        node, pos = _parseUnary(tokens, pos + 1)
        return ('not', node), pos
    if kind == '(':
        node, pos = _parseOr(tokens, pos + 1)
        if _kind(tokens, pos) != ')':
            raise RequiresError("a '(' is never closed")
        return node, pos + 1
    if kind != 'name':
        raise RequiresError('a mod name is missing %s'
                            % ('at the end' if kind is None
                               else "before '%s'" % tokens[pos][1]))
    name = tokens[pos][1]
    pos += 1
    constraint = None
    if _kind(tokens, pos) == 'op':
        if _kind(tokens, pos + 1) != 'version':
            raise RequiresError("'%s%s' needs a version, like %s>=1.0"
                                % (name, tokens[pos][1], name))
        constraint = tokens[pos][1] + tokens[pos + 1][1]
        pos += 2
    return ('mod', name, constraint), pos

def allOf(nodes):
    nodes = [n for n in nodes if n is not None]
    if not nodes:
        return None
    return nodes[0] if len(nodes) == 1 else ('and', nodes)

def holds(node, versions, satisfies):

    if node is None:
        return True
    kind = node[0]
    if kind == 'mod':
        _, name, constraint = node
        if name not in versions:
            return False
        return constraint is None or satisfies(versions[name], constraint)
    if kind == 'not':
        return not holds(node[1], versions, satisfies)
    results = [holds(n, versions, satisfies) for n in node[1]]
    return (False not in results) if kind == 'and' else (True in results)

def names(node, positiveOnly=False, _negated=False, _out=None):


    out = [] if _out is None else _out
    if node is None:
        return out
    kind = node[0]
    if kind == 'mod':
        if not (positiveOnly and _negated) and node[1] not in out:
            out.append(node[1])
    elif kind == 'not':
        names(node[1], positiveOnly, not _negated, out)
    else:
        for child in node[1]:
            names(child, positiveOnly, _negated, out)
    return out

def describe(node):
    kind = node[0]
    if kind == 'mod':
        return node[1] + (node[2] or '')
    if kind == 'not':
        inner = describe(node[1])
        return 'not ' + (inner if node[1][0] in ('mod', 'not')
                         else '(%s)' % inner)
    parts = []
    for child in node[1]:
        text = describe(child)
        if child[0] in ('and', 'or') and child[0] != kind:
            text = '(%s)' % text
        parts.append(text)
    return (' %s ' % kind).join(parts)
