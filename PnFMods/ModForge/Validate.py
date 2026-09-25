# coding=utf-8

from xml.dom import minidom as _minidom

import Paths
import Resources
from Logger import logInfo
from Codec import _u1

BUILTIN_ELEMENT_CLASSES = (
    'lesta.unbound2.UbElement',
    'lesta.libs.unbound.UnboundElement',
)

_SWF_MAGIC = ('FWS', 'CWS', 'ZWS')

def validateContent(relPath, data):
    lower = relPath.lower()
    if lower.endswith('.xml'):
        return _validateXml(data)
    if lower.endswith('.unbound'):
        return _validateUnbound(data)
    if lower.endswith('.swf'):
        return _validateSwf(data)
    return []

def _validateXml(data):
    if not data.strip():
        return ['file is empty']
    try:
        doc = _minidom.parseString(data)
    except Exception as exc:
        return ['not well-formed XML: %s' % exc]
    doc.unlink()
    return []

def _validateUnbound(data):
    # ref:uss-splice -- an entry that yields no content kills the Unbound
    # parser in native code, before mods load and before markup is parsed:
    # nothing in python.log, nothing in ub_player_errors.log. The .xml path
    # has always checked this; this one did not.
    if not data.strip():
        return ['file is empty']
    # `#` is the only comment; both quote styles are strings.
    depth = 0
    line = 1
    inString = None
    inComment = False
    i = 0
    n = len(data)
    while i < n:
        ch = data[i]
        if ch == '\n':
            line += 1
            inComment = False
            i += 1
            continue
        if inComment:
            i += 1
            continue
        if inString:
            if ch == '\\':
                i += 2
                continue
            if ch == inString:
                inString = None
            i += 1
            continue
        if ch in ('"', "'"):
            inString = ch
        elif ch == '#':
            inComment = True
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0:
                return ['unbalanced ) at line %d' % line]
        i += 1
    if inString:
        return ['unterminated string literal']
    if depth:
        return ['%d unclosed ( at end of file' % depth]
    return []

def _validateSwf(data):
    if len(data) < 8:
        return ['too short to be a SWF (%d bytes)' % len(data)]
    magic = data[:3]
    if magic not in _SWF_MAGIC:
        return ['not a SWF: header is %r, expected one of %s'
                % (magic, '/'.join(_SWF_MAGIC))]
    declared = (ord(data[4]) | (ord(data[5]) << 8)
                | (ord(data[6]) << 16) | (ord(data[7]) << 24))
    if magic == 'FWS' and declared != len(data):
        return ['truncated SWF: header declares %d bytes, file has %d'
                % (declared, len(data))]
    return []

def validateAssembled(relPath, doc, resolveRef=None):
    name = relPath.rsplit('/', 1)[-1]
    if name == 'uss_settings.xml':
        return _validateUssSettings(doc, resolveRef)
    if name == 'battle_elements.xml':
        return _validateBattleElements(doc, resolveRef)
    return []

def _text(node):
    parts = [c.data for c in node.childNodes if c.nodeType == 3]
    return ''.join(parts).strip()

def _children(parent, tag):
    return [c for c in parent.childNodes
            if c.nodeType == 1 and c.tagName == tag]

def _validateUssSettings(doc, resolveRef):
    problems = []
    root = doc.documentElement
    for container in _children(root, 'mods'):
        for tag in ('xmlfile', 'swffile'):
            for node in _children(container, tag):
                path = _text(node)
                if not path:
                    problems.append('<%s> with no path' % tag)
                    continue
                if resolveRef is None:
                    continue
                rel = resolveRef(path)
                if rel is None:
                    problems.append('<%s>%s</%s> does not resolve to a file'
                                    % (tag, path, tag))
                    continue
                problems.extend('%s: %s' % (path, p)
                                for p in _contentOf(rel))
    return problems

def _contentOf(relPath):
    absPath = Paths.resModsDir() + relPath
    if not Paths.fileExists(absPath):
        return []
    try:
        data = Paths.readBytes(absPath)
    except Exception as exc:
        return ['unreadable: %s' % exc]
    return validateContent(relPath, data)

def _validateBattleElements(doc, resolveRef):
    problems = []
    root = doc.documentElement
    elementNames = set()
    duplicates = []

    for container in _children(root, 'elementList'):
        for el in _children(container, 'element'):
            name = el.getAttribute('name')
            if name:
                if name in elementNames:
                    duplicates.append(name)
                elementNames.add(name)
            problems.extend(_validateElementRow(el, name, resolveRef))

    for name in duplicates:
        problems.append("two elements claim name='%s'; the later one wins "
                        "and the earlier mod is silently inert" % name)

    for container in _children(root, 'controllers'):
        for ctrl in _children(container, 'controller'):
            clips = ctrl.getAttribute('clips')
            if not clips:
                continue
            for clip in [c.strip() for c in clips.split(',') if c.strip()]:
                if clip not in elementNames:
                    problems.append(
                        "controller clips='%s' names no <element name=>; "
                        "the controller will be dropped" % clip)
    return problems

def _validateElementRow(el, name, resolveRef):
    problems = []
    label = name or '(unnamed)'
    cls = el.getAttribute('class')
    urls = [u.strip() for u in (el.getAttribute('url') or '').split(',')
            if u.strip()]

    resolvedUrls = []
    for url in urls:
        rel = resolveRef(url) if resolveRef is not None else None
        if resolveRef is not None and rel is None:
            problems.append("element '%s' url='%s' does not resolve to a file"
                            % (label, url))
            continue
        if rel is not None:
            resolvedUrls.append(rel)
            problems.extend("element '%s' url='%s': %s" % (label, url, p)
                            for p in _contentOf(rel))

    if cls and cls not in BUILTIN_ELEMENT_CLASSES:
        if not urls:
            problems.append(
                "element '%s' class='%s' is not built in and the row names "
                "no url= to supply it" % (label, cls))
        elif resolveRef is not None and not resolvedUrls:
            problems.append(
                "element '%s' class='%s' needs a SWF but none of its url= "
                "entries resolve" % (label, cls))
    return problems

_UNBOUND2_REL = 'gui/unbound2'
_NAME_CACHE_FILE = 'unbound2Names.txt'

_DEFINITION_KEYS = (('block', 'className'), ('css', 'name'))

def duplicateDefinitions(emitted):
    """Top-level definitions more than one emitted file declares.

    Read from `UbBlockFactory.loadPlansFromXml`, build 13187581: both loops
    are E4X CHILD accessors (`xml.css`, `xml.block`, not `xml..block`), so
    ONLY a top-level definition becomes a plan -- a nested <block className=>
    is an inline child and nothing else. Registration is then a bare
    `xmlElementPlans[name] = plan` over every registered file in load order,
    so a second declaration of the same name silently replaces the first and
    nothing is logged. Which one wins is load order, which the author does
    not control.

    `emitted` is (relPath, bytes) for each XML this run wrote."""
    import BlockSlice
    seen = {}
    problems = []
    for relPath, data in emitted:
        if not relPath.lower().endswith('.xml'):
            continue
        for tag, attr in _DEFINITION_KEYS:
            index = BlockSlice.top_level_index(data, tag, attr)
            for name, span in index.items():
                if span is None:
                    problems.append(
                        "%s declares <%s %s='%s'> twice; the later one wins "
                        "and the earlier is dead" % (relPath, tag, attr, name))
                seen.setdefault((tag, attr, name), []).append(relPath)
    for key in sorted(seen):
        tag, attr, name = key
        files = sorted(set(seen[key]))
        if len(files) > 1:
            problems.append(
                "<%s %s='%s'> is declared by %s; whichever loads last wins "
                "and the rest are dead, with nothing logged in game"
                % (tag, attr, name, ', '.join(files)))
    return problems

def styleClassUses(data):
    """name -> how many `<styleClass value=>` name it, at any depth.

    It is a child ELEMENT, not an attribute: 5,469 of them in vanilla
    markup.xml across build 13187581, zero in the attribute form. The scan
    goes through `BlockSlice.iter_tags`, so a commented-out example does not
    count as a use."""
    import BlockSlice
    out = {}
    for _kind, tag, start, end in BlockSlice.iter_tags(data):
        if tag != 'styleClass':
            continue
        value = BlockSlice.tag_attrs(data, start, end).get('value')
        if value is not None:
            out[value] = out.get(value, 0) + 1
    return out

def unresolvedStyleClasses(emitted, definedElsewhere):
    """`<styleClass value=>` naming no preset anything in this run defines.

    The asymmetry is the point: a missing registered XML THROWS, but an
    unresolved styleClass is completely silent -- `getStyleClassById` returns
    undefined with no guard, the merge loop runs zero times, and nothing is
    logged anywhere. The element renders with inherited values and the author
    gets no signal at all. Forge holds both sides, so it can say so.

    Calibrated against vanilla: 156 names used, 286 defined, 0 unresolved on
    both 13015811 and 13187581 -- so a hit here is a real fault, not noise."""
    import BlockSlice
    defined = set(definedElsewhere)
    for _relPath, data in emitted:
        defined |= set(BlockSlice.top_level_index(data, 'css', 'name'))

    problems = []
    for relPath, data in emitted:
        for name in sorted(styleClassUses(data)):
            if name not in defined:
                problems.append(
                    "%s: <styleClass value='%s'> names no preset vanilla or "
                    "any mod in this run defines; it is ignored in game with "
                    "nothing logged, and the element keeps inherited values"
                    % (relPath, name))
    return problems

def unbound2ElementNames():
    modNames = _modElementNames()
    vanillaNames = _vanillaElementNames()
    if modNames is None and vanillaNames is None:
        return None
    return (modNames or set()) | (vanillaNames or set())

_installedScan = None

def _scanInstalledUnbound2():
    """{name: [paths]} plus the files that are empty, for everything under
    res_mods/gui/unbound2. Cached for the run: two callers want it and it
    reads every installed view."""
    # Keyed on the directory, not a bare flag: one process can serve more
    # than one res_mods (the offline harness does), and a stale hit there
    # would answer about a tree that is no longer the one being installed.
    global _installedScan
    root = Paths.resModsDir() + _UNBOUND2_REL + '/'
    if _installedScan is not None and _installedScan[0] == root:
        return _installedScan[1]
    if not Paths.dirExists(root):
        _installedScan = (root, (None, []))
        return _installedScan[1]
    owners = {}
    empty = []
    for path in _walkFiles(root, '.unbound'):
        try:
            data = Paths.readBytes(path)
        except Exception:
            continue
        rel = path[len(Paths.resModsDir()):] if path.startswith(
            Paths.resModsDir()) else path
        if not data.strip():
            empty.append(rel)
            continue
        for name in _defElementNames(data):
            owners.setdefault(name, []).append(rel)
    _installedScan = (root, (owners, empty))
    return _installedScan[1]

def _modElementNames():
    owners, _empty = _scanInstalledUnbound2()
    return None if owners is None else set(owners)

def installedUnbound2Problems():
    """What only the installed SET can reveal, which is why it is here and
    not in the authoring linter: a view that is empty, and a name two
    installed mods both define.

    A mod shadowing a VANILLA name is how an Unbound 2 mod overrides a view
    and is deliberate, so vanilla is not consulted -- only collisions between
    two mods the player happens to have together.

    Unbound 2 resolves a duplicate the OPPOSITE way to Unbound 1: the FIRST
    registration wins. `duplicateDefinitions` above is the last-wins rule and
    is right about Unbound 1; do not carry it across."""
    owners, empty = _scanInstalledUnbound2()
    problems = []
    for rel in sorted(empty):
        problems.append(
            '%s is empty; an entry that yields no content kills the Unbound '
            'parser in native code, before anything is logged' % rel)
    if owners:
        for name in sorted(owners):
            paths = sorted(set(owners[name]))
            if len(paths) > 1:
                problems.append(
                    "two installed mods both define '%s': %s -- whichever "
                    "registers FIRST wins and the rest never build; the "
                    "client logs 'Duplicate element definition' for each "
                    "loser" % (name, ', '.join(paths)))
    return problems

def _vanillaElementNames():
    buildId = Paths.gameBuildId()
    cached = _readNameCache(buildId)
    if cached is not None:
        return cached
    try:
        from PkgMgr import PkgMgr
        mgr = PkgMgr(_UNBOUND2_REL.split('/', 1)[0])
        paths = mgr.listFiles(_UNBOUND2_REL, '.unbound')
        names = set()
        for path in paths:
            data = mgr.getFileContents(path)
            if data:
                names.update(_defElementNames(data))
        mgr.clear()
    except Exception as exc:
        logInfo('could not read vanilla unbound2 names: %s' % exc)
        return None
    if not paths:
        return None
    _writeNameCache(buildId, names)
    return names

def _readNameCache(buildId):
    path = Paths.cacheDir() + _NAME_CACHE_FILE
    if not Paths.fileExists(path):
        return None
    try:
        lines = Paths.readBytes(path).split('\n')
    except Exception:
        return None
    if not lines or lines[0].strip() != buildId:
        return None
    return set(n for n in (line.strip() for line in lines[1:]) if n)

def _writeNameCache(buildId, names):
    try:
        Paths.writeBytes(Paths.cacheDir() + _NAME_CACHE_FILE,
                         '\n'.join([buildId] + sorted(names)))
    except Exception as exc:
        logInfo('could not cache vanilla unbound2 names: %s' % exc)

def _walkFiles(root, suffix):
    out = []
    for dirPath, _dirs, files in _u1.walk(root):
        base = dirPath.replace('\\', '/').rstrip('/') + '/'
        for name in files:
            if name.endswith(suffix):
                out.append(base + name)
    return out

# A battle_elements `elementName=` may name either form. Measured on build
# 13187581: of vanilla's own 18, `MarkersContainer` and `SpeedControl` are
# `(def layout ...)` and the other 16 are `(def element ...)`. Scanning only
# for the latter reports two stock entries as broken, every run.
_DEF_FORMS = ('(def element', '(def layout')

def _defElementNames(data):
    out = []
    for needle in _DEF_FORMS:
        _scanDefs(data, needle, out)
    return out

def _scanDefs(data, needle, out):
    idx = 0
    while True:
        idx = data.find(needle, idx)
        if idx < 0:
            return out
        idx += len(needle)
        end = idx
        while end < len(data) and data[end] in ' \t\r\n':
            end += 1
        start = end
        while end < len(data) and data[end] not in ' \t\r\n()':
            end += 1
        if end > start:
            out.append(data[start:end])

def validateElementNames(doc, knownNames):
    if knownNames is None:
        return []
    problems = []
    root = doc.documentElement
    for container in _children(root, 'elementList'):
        for el in _children(container, 'element'):
            if el.getAttribute('class') != 'lesta.unbound2.UbElement':
                continue
            elementName = el.getAttribute('elementName')
            if elementName and elementName not in knownNames:
                problems.append(
                    "element '%s' elementName='%s' matches no "
                    "(def element ...) under gui/unbound2/"
                    % (el.getAttribute('name') or '(unnamed)', elementName))
    return problems

STUB_XML = '<ui/>'

def substituteBrokenRefs(doc, relPath, resolveRef, stubPathFor):
    if relPath.rsplit('/', 1)[-1] != 'uss_settings.xml':
        return []
    swapped = []
    used = {'xmlfile': 0, 'swffile': 0}
    root = doc.documentElement
    for container in _children(root, 'mods'):
        for tag in ('xmlfile', 'swffile'):
            for node in _children(container, tag):
                path = _text(node)
                if not path:
                    continue
                why = _brokenReason(path, resolveRef)
                if why is None:
                    continue
                used[tag] += 1
                stub = stubPathFor(tag, used[tag])
                if stub is None:
                    container.removeChild(node)
                    swapped.append((path, 'removed'))
                    logInfo('removed unusable <%s>%s (%s)' % (tag, path, why))
                    continue
                for child in list(node.childNodes):
                    node.removeChild(child)
                node.appendChild(doc.createTextNode(stub))
                swapped.append((path, stub))
                logInfo('substituted stub for <%s>%s (%s)' % (tag, path, why))
    return swapped

def _brokenReason(path, resolveRef):
    rel = resolveRef(path)
    if rel is None:
        return 'does not resolve to a file'
    problems = _contentOf(rel)
    if problems:
        return problems[0]
    return None

_STUB_DIR_REL = 'gui/unbound/mods/'
_XML_STUB_STEM = '__forge_stub'
_SWF_STUB_REL = _STUB_DIR_REL + '__forge_stub.swf'

def _xmlStubName(n):
    if n == 1:
        return _XML_STUB_STEM + '.xml'
    return '%s_%d.xml' % (_XML_STUB_STEM, n)

# One file per entry: an xmlfile URL listed twice never finishes loading.
# ref:uss-duplicate-url
def ensureXmlStub(n=1):
    name = _xmlStubName(n)
    absPath = Paths.resModsDir() + _STUB_DIR_REL + name
    try:
        if not Paths.fileExists(absPath):
            Paths.writeBytes(absPath, STUB_XML)
    except Exception as exc:
        logInfo('could not create xml stub: %s' % exc)
        return None
    return '../unbound/mods/' + name

def _isXmlStubName(name):
    if name == _xmlStubName(1):
        return True
    prefix = _XML_STUB_STEM + '_'
    return (name.startswith(prefix) and name.endswith('.xml')
            and name[len(prefix):-4].isdigit())

def ensureSwfStub():
    absPath = Paths.resModsDir() + _SWF_STUB_REL
    try:
        import StubAssets
        if not Paths.fileExists(absPath):
            Paths.writeBytes(absPath, StubAssets.STUB_SWF)
    except Exception as exc:
        logInfo('could not create swf stub: %s' % exc)
        return None
    return '../unbound/mods/__forge_stub.swf'

def removeStubs():
    stubs = [_STUB_DIR_REL + name
             for name in Paths.listFiles(Paths.resModsDir() + _STUB_DIR_REL,
                                         '.xml')
             if _isXmlStubName(name)]
    for rel in stubs + [_SWF_STUB_REL]:
        absPath = Paths.resModsDir() + rel
        try:
            if Paths.fileExists(absPath):
                Paths.removeFile(absPath)
        except Exception as exc:
            logInfo('could not remove stub %s: %s' % (rel, exc))
