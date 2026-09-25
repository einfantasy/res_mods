# coding=utf-8

import AbcFmt
import Paths
import Resources
from Codec import _u3
from Logger import logInfo, logError

SCENE = 'gui/flash/consumer_main_scene.swf'
CONTROLLER_ROOT = 'UbController'

def load():
    """(class names, simple names of UbController and its subclasses) in
    the running build's scene, or None when they cannot be read."""
    cached = _loadCache()
    if cached is not None:
        return cached
    if _u3 is None:
        logError('cannot inflate %s; class names are not checked' % SCENE)
        return None
    data = Resources.loadPristine(SCENE)
    if data is None:
        return None
    try:
        classes = classesOf(data)
    except Exception as exc:
        logError('cannot read the classes of %s: %s' % (SCENE, exc))
        return None
    controllers = controllersOf(classes)
    # An empty or rootless table would refuse every controller a mod names.
    if CONTROLLER_ROOT not in controllers:
        logError('%s yielded %d classes and no %s; class names are not '
                 'checked' % (SCENE, len(classes), CONTROLLER_ROOT))
        return None
    result = (frozenset(classes), controllers)
    _saveCache(result)
    logInfo('read %d classes from %s' % (len(classes), SCENE))
    return result

def classesOf(swf):
    """{qualified class name: qualified superclass name or None}."""
    sig, _version, _length, body = AbcFmt.split_swf(swf)
    sig = str(sig)
    if sig == 'CWS':
        body = _u3.decompress(str(body))
    elif sig != 'FWS':
        raise Exception('unsupported SWF signature %r' % sig)
    out = {}
    for _index, _head, abc in AbcFmt.abc_tags(
            AbcFmt.parse_body(bytearray(body))):
        _readInstances(abc, out)
    return out

def _readInstances(abc, out):
    # Stops after the instance table: method bodies are most of the ABC.
    r = AbcFmt.Reader(abc)
    r.u16()
    r.u16()
    pool = _readPool(r)
    for _ in range(r.u30()):
        AbcFmt._read_method(r)
    for _ in range(r.u30()):
        r.u30()
        for _ in range(r.u30()):
            r.u30()
            r.u30()
    for _ in range(r.u30()):
        inst = AbcFmt._read_instance(r)
        name = _qname(pool, inst['name'])
        if name:
            out[name] = _qname(pool, inst['super_name'])

def _readPool(r):
    # AbcFmt._read_cpool less the values: doubles are skipped undecoded,
    # because the client raises FloatingPointError on creating a NaN and the
    # scene's pool holds one.
    for _ in range(max(r.u30() - 1, 0)):
        r.s32()
    for _ in range(max(r.u30() - 1, 0)):
        r.u32()
    doubles = max(r.u30() - 1, 0)
    r.p += 8 * doubles
    strings = [r.string() for _ in range(max(r.u30() - 1, 0))]
    namespaces = [{'kind': r.u8(), 'name': r.u30()}
                  for _ in range(max(r.u30() - 1, 0))]
    for _ in range(max(r.u30() - 1, 0)):
        for _ in range(r.u30()):
            r.u30()
    multinames = [AbcFmt._read_multiname(r)
                  for _ in range(max(r.u30() - 1, 0))]
    return {'strings': strings, 'namespaces': namespaces,
            'multinames': multinames}

def _qname(pool, index):
    if not index:
        return None
    m = pool['multinames'][index - 1]
    if m['kind'] not in (0x07, 0x0D):
        return None
    ns = pool['namespaces'][m['ns'] - 1]['name'] if m['ns'] else 0
    package = str(pool['strings'][ns - 1]) if ns else ''
    name = str(pool['strings'][m['name'] - 1]) if m['name'] else ''
    return '%s.%s' % (package, name) if package else name

def controllersOf(classes):
    parent = {}
    for name, superName in classes.items():
        parent[name.split('.')[-1]] = (superName.split('.')[-1]
                                       if superName else None)
    out = set()
    for name in parent:
        seen = set()
        node = name
        while node and node not in seen:
            if node == CONTROLLER_ROOT:
                out.add(name)
                break
            seen.add(node)
            node = parent.get(node)
    return frozenset(out)

def _cachePath():
    return Paths.originalsDir() + SCENE + '.classes'

def _buildId():
    buildId = Paths.gameBuildId()
    if isinstance(buildId, unicode):
        buildId = buildId.encode('utf-8')
    return buildId

def _loadCache():
    path = _cachePath()
    if not Paths.fileExists(path):
        return None
    try:
        lines = Paths.readBytes(path).split('\n')
    except Exception:
        return None
    if not lines or lines[0] != _buildId():
        return None
    classes = set()
    controllers = set()
    for line in lines[1:]:
        kind, _sep, name = line.partition('\t')
        if kind == 'C':
            classes.add(name)
        elif kind == 'U':
            controllers.add(name)
    if CONTROLLER_ROOT not in controllers:
        return None
    return frozenset(classes), frozenset(controllers)

def _saveCache(result):
    classes, controllers = result
    out = [_buildId()]
    out.extend('C\t%s' % n for n in sorted(classes))
    out.extend('U\t%s' % n for n in sorted(controllers))
    try:
        Paths.writeBytes(_cachePath(), '\n'.join(out))
    except Exception:
        pass
