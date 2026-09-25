# coding=utf-8

import re

_TAG = re.compile(r'<(/?)([A-Za-z_][\w.\-]*)|<!--|<!\[CDATA\[|<\?')

def _skip_to(data, pos, close):
    i = data.find(close, pos)
    return len(data) if i < 0 else i + len(close)

def iter_tags(data, pos=0):
    n = len(data)
    while pos < n:
        m = _TAG.search(data, pos)
        if m is None:
            return
        head = m.group(0)
        if head == '<!--':
            pos = _skip_to(data, m.end(), '-->')
            continue
        if head == '<![CDATA[':
            pos = _skip_to(data, m.end(), ']]>')
            continue
        if head == '<?':
            pos = _skip_to(data, m.end(), '?>')
            continue

        i = m.end()
        quote = None
        while i < n:
            c = data[i]
            if quote:
                if c == quote:
                    quote = None
            elif c in '"\'':
                quote = c
            elif c == '>':
                break
            i += 1
        if i >= n:
            return

        closing = m.group(1) == '/'
        empty = data[i - 1] == '/'
        kind = 'close' if closing else ('empty' if empty else 'open')
        yield kind, m.group(2), m.start(), i + 1
        pos = i + 1

_ATTR = re.compile(r'([A-Za-z_][\w.\-]*)\s*=\s*"([^"]*)"')

def tag_attrs(data, start, end):
    return dict(_ATTR.findall(data[start:end]))

_COMMENT = re.compile(r'<!--.*?-->', re.S)

def comment_spans(data):
    return [m.span() for m in _COMMENT.finditer(data)]

def _in_span(spans, pos):
    lo, hi = 0, len(spans)
    while lo < hi:
        mid = (lo + hi) // 2
        s, e = spans[mid]
        if pos < s:
            hi = mid
        elif pos >= e:
            lo = mid + 1
        else:
            return True
    return False

def find_block(data, className, tag='block', attr='className', spans=None):
    if spans is None:
        spans = comment_spans(data)
    pat = re.compile(r'<%s\b[^>]*\b%s="%s"' % (tag, attr, re.escape(className)))

    for m in pat.finditer(data):
        if _in_span(spans, m.start()):
            continue
        depth = 0
        for kind, name, s, e in iter_tags(data, m.start()):
            if name != tag:
                continue
            if depth == 0:
                if s != m.start():
                    break
                if kind == 'empty':
                    return (s, e)
                depth = 1
                continue
            if kind == 'open':
                depth += 1
            elif kind == 'close':
                depth -= 1
                if depth == 0:
                    return (m.start(), e)

    return None

def top_level_index(data, tag='block', attr='className'):
    index = {}
    depth = 0
    pending = None
    for kind, name, s, e in iter_tags(data):
        if name != tag:
            continue
        if kind == 'empty':
            if depth == 0:
                v = tag_attrs(data, s, e).get(attr)
                if v is not None:
                    index[v] = None if v in index else (s, e)
            continue
        if kind == 'open':
            if depth == 0:
                pending = (tag_attrs(data, s, e).get(attr), s)
            depth += 1
        elif kind == 'close':
            if depth > 0:
                depth -= 1
            if depth == 0 and pending is not None:
                v, start = pending
                pending = None
                if v is not None:
                    index[v] = None if v in index else (start, e)
    return index

def class_names(data, tag='block', attr='className'):
    out = []
    for kind, name, s, e in iter_tags(data):
        if name == tag and kind in ('open', 'empty'):
            v = tag_attrs(data, s, e).get(attr)
            if v is not None:
                out.append(v)
    return out
