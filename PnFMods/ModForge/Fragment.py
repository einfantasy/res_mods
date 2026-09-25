# coding=utf-8

from xml.dom import minidom as _minidom

import BlockSlice
import Paths
import Resources
import Selector
from Logger import logInfo

class FragmentError(Exception):
    pass

_MISSING = object()

def _indexPath(relPath, tag, attr):
    return '%s%s.%s-%s.index' % (Paths.originalsDir(), relPath, tag, attr)

def _loadIndex(relPath, tag, attr, data):
    path = _indexPath(relPath, tag, attr)
    if not Paths.fileExists(path):
        return None
    try:
        lines = Paths.readBytes(path).split('\n')
    except Exception:
        return None
    if not lines or lines[0].strip() != str(len(data)):
        return None
    index = {}
    for line in lines[1:]:
        if not line:
            continue
        parts = line.split('\t', 2)
        if len(parts) != 3:
            return None
        try:
            start, end = int(parts[0]), int(parts[1])
        except Exception:
            return None
        index[parts[2]] = None if start < 0 else (start, end)
    return index

def _saveIndex(relPath, tag, attr, data, index):
    out = [str(len(data))]
    for name in sorted(index):
        span = index[name]
        start, end = (-1, -1) if span is None else span
        out.append('%d\t%d\t%s' % (start, end, name))
    try:
        Paths.writeBytes(_indexPath(relPath, tag, attr), '\n'.join(out))
    except Exception:
        pass

def _headLength(raws):
    """How many raw steps make the first location step: any leading `.`,
    and the `//` that makes it a descendant step."""
    for cut in range(1, len(raws) + 1):
        raw = raws[cut - 1].strip()
        if raw and raw != '.':
            return cut
    return len(raws)

def _rest(nodes, raws):
    if not raws:
        return nodes
    # `X//y`: the remainder starts at the empty step `//` leaves behind.
    expr = '/'.join(raws)
    if not raws[0].strip():
        expr = './' + expr
    out = []
    for node in nodes:
        out.extend(Selector.findAll(node, expr))
    return out

class Sources(object):
    def __init__(self):
        self._data = {}
        self._docs = {}
        self._indexes = {}
        self._fragments = {}

    def find(self, relPath, expr):
        """The first step must name exactly one node, in any file; the steps
        after it may match many. The index is only a faster way to evaluate
        a `tag[@attr='v']` first step, and gives the same answer."""
        steps = Selector.parseSelector(expr)
        raws = Selector.splitSteps(expr)
        head = steps[0]
        if (head.axis == 'child' and head.tag not in ('.', '..', '*')
                and len(head.predicates) == 1
                and head.predicates[0].kind == 'attr'
                and head.predicates[0].op == '='):
            return _rest(self._sliced(relPath, head), raws[1:])
        root = self.document(relPath).documentElement
        cut = _headLength(raws)
        heads = Selector.findAll(root, '/'.join(raws[:cut]))
        if len(heads) > 1:
            raise FragmentError(
                "the first step of '%s' matches %d nodes in %s; it has to name "
                "one -- add a predicate or [1]" % (expr, len(heads), relPath))
        return _rest(heads, raws[cut:])

    def raw(self, relPath):
        data = self._data.get(relPath)
        if data is None:
            data = Resources.loadPristine(relPath)
            if data is None:
                raise FragmentError('cannot fetch pristine copy of %s'
                                    % relPath)
            self._data[relPath] = data
        return data

    def document(self, relPath):
        doc = self._docs.get(relPath)
        if doc is None:
            try:
                doc = _minidom.parseString(self.raw(relPath))
            except Exception as exc:
                raise FragmentError('%s does not parse: %s' % (relPath, exc))
            self._docs[relPath] = doc
        return doc

    def index(self, relPath, tag, attr):
        key = (relPath, tag, attr)
        index = self._indexes.get(key)
        if index is not None:
            return index
        data = self.raw(relPath)
        index = _loadIndex(relPath, tag, attr, data)
        if index is None:
            index = BlockSlice.top_level_index(data, tag, attr)
            _saveIndex(relPath, tag, attr, data, index)
            logInfo('indexed %d top-level <%s %s=> in %s'
                    % (len(index), tag, attr, relPath))
        self._indexes[key] = index
        return index

    def _sliced(self, relPath, head):
        attr = head.predicates[0].name
        value = head.predicates[0].value
        key = (relPath, head.tag, attr, value)
        cached = self._fragments.get(key)
        if cached is not None:
            return [cached]

        span = self.index(relPath, head.tag, attr).get(value, _MISSING)
        if span is _MISSING:
            raise FragmentError("no top-level <%s %s='%s'> in %s"
                                % (head.tag, attr, value, relPath))
        if span is None:
            raise FragmentError("<%s %s='%s'> is defined more than once at the "
                                "top level of %s"
                                % (head.tag, attr, value, relPath))
        fragment = self.raw(relPath)[span[0]:span[1]]
        try:
            doc = _minidom.parseString(fragment)
        except Exception as exc:
            raise FragmentError("<%s %s='%s'> in %s does not parse: %s"
                                % (head.tag, attr, value, relPath, exc))
        self._fragments[key] = doc.documentElement
        return [doc.documentElement]
