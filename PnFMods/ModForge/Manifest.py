# coding=utf-8

import re

import Requires
from Logger import logInfo, logError
from Codec import _u2

VANILLA_MARKUP = 'gui/unbound/markup.xml'
VANILLA_STYLES = 'gui/unbound/styles.xml'
USS_SETTINGS = 'gui/uss_settings.xml'
BATTLE_ELEMENTS = 'gui/battle_elements.xml'
PAYLOAD_DIR = 'gui/unbound/mods/'
USS_PAYLOAD_DIR = '../unbound/mods/'
UNBOUND_ELEMENT_CLASS = 'lesta.libs.unbound.UnboundElement'
UNBOUND2_ELEMENT_CLASS = 'lesta.unbound2.UbElement'
UNBOUND_CONTROLLER_CLASS = ('lesta.dialogs.battle_window_controllers'
                            '.UnboundElementController')

class Manifest(object):
    __slots__ = (
        'modName', 'version', 'priority',
        'installerRequirement',
        'modRequirement',
        'builds',
        'definitions',
        'sourcePath',
        'sourceHash',
    )

    def __init__(self):
        self.modName = None
        self.version = None
        self.priority = 0
        self.installerRequirement = None
        self.modRequirement = None
        self.builds = []
        self.definitions = []
        self.sourcePath = None
        self.sourceHash = None

class DefinitionSpec(object):
    __slots__ = ('namespace', 'name', 'actions', 'requirement')

    def __init__(self):
        self.namespace = None
        self.name = None
        self.actions = []
        self.requirement = None

class BuildSpec(object):
    __slots__ = ('file', 'root', 'guards', 'actions', 'requirement',
                 'restartOnChange')

    def __init__(self):
        self.file = None
        self.root = None
        self.guards = []
        self.actions = []
        self.requirement = None


        self.restartOnChange = False

class Guard(object):
    __slots__ = ('kind', 'expr')

    def __init__(self, kind, expr):
        self.kind = kind
        self.expr = expr

class ActionSpec(object):
    __slots__ = (
        'kind',
        'select',
        'source',
        'into',
        'before',
        'after',
        'payload',
        'attribute',
        'fromValue',
        'toValue',
        'actions',
    )

    def __init__(self, kind):
        self.kind = kind
        self.select = None
        self.source = None
        self.into = None
        self.before = None
        self.after = None
        self.payload = []
        self.attribute = None
        self.fromValue = None
        self.toValue = None
        self.actions = []

class ManifestError(Exception):
    pass

_KNOWN_MOD_ATTRS = set(['name', 'version', 'priority'])
_KNOWN_BUILD_ATTRS = set(['file', 'root', 'restartOnChange'])
_KNOWN_INSERT_ATTRS = set(['into', 'before', 'after'])
_KNOWN_REMOVE_ATTRS = set(['select'])
_KNOWN_REPLACE_ATTRS = set(['select'])
_KNOWN_SET_ATTRIBUTE_ATTRS = set(['select', 'attribute', 'from', 'to'])
_KNOWN_COPY_ATTRS = set(['select', 'from', 'into', 'before', 'after'])
_KNOWN_GUARD_ATTRS = set(['ifExists', 'ifNotExists'])
_KNOWN_REQUIRES_ATTRS = set(['installer', 'mods'])
_KNOWN_DEFINITION_ATTRS = set(['name'])
_KNOWN_UB_MOUNT_ATTRS = set(['unbound', 'rootElementId', 'name', 'hitTest',
                             'url', 'before', 'after'])




_REMOVED_VERBS = {
    'ubBuild': "<ubBuild> is gone. Name the definition you edit -- "
               "<ubBuildBlock name='...'> or <ubBuildStyle name='...'> -- and "
               "Forge picks the file, the compile and the registration, so "
               "two mods editing one definition merge instead of racing.",
    'ubCompile': '<ubCompile> is gone; Forge compiles what it emitted.',
    'ubRegister': "<ubRegister> is gone. A file Forge did not write can "
                  "define any name, which is the cross-file collision "
                  "per-class emission exists to remove. Use <ubBuildBlock> "
                  "or <ubBuildStyle>.",
}

def parseManifest(filePath, fileBytes):
    try:
        root = _u2.fromstring(fileBytes)
    except Exception as exc:
        raise ManifestError('not valid XML: %s' % exc)
    if root.tag != 'mod':
        raise ManifestError("root element must be <mod>, got <%s>" % root.tag)

    m = Manifest()
    m.sourcePath = filePath

    _warnUnknown(root, _KNOWN_MOD_ATTRS, 'mod attribute', filePath)

    m.modName = root.get('name')
    m.version = root.get('version')
    if not m.modName:
        raise ManifestError('<mod> requires a `name` attribute')
    problem = Requires.nameProblem(m.modName)
    if problem:

        raise ManifestError("<mod name='%s'>: %s" % (m.modName, problem))
    if not m.version:
        raise ManifestError("<mod name='%s'> requires a `version` attribute"
                            % m.modName)
    parts = parseVersion(m.version)
    if parts and len(parts) > 3:
        logInfo("%s: version='%s' has %d numbers; use major.minor.patch, "
                "like 1.2.0" % (m.modName, m.version, len(parts)))
    try:
        m.priority = int(root.get('priority', '0'))
    except Exception:
        logInfo('%s: priority must be an integer, got %r; using 0'
                % (m.modName, root.get('priority')))
        m.priority = 0

    for child in root:
        if child.tag == 'requires':
            m.modRequirement = Requires.allOf(
                [m.modRequirement, _parseRequires(m, child, '<mod>')])
        elif child.tag == 'build':
            m.builds.append(_parseBuild(m, child))
        elif child.tag in _REMOVED_VERBS:
            raise ManifestError('%s: %s' % (m.modName,
                                            _REMOVED_VERBS[child.tag]))
        elif child.tag == 'ubBuildBlock':
            m.definitions.append(_parseDefinition(m, child, 'block'))
        elif child.tag == 'ubBuildStyle':
            m.definitions.append(_parseDefinition(m, child, 'css'))
        elif child.tag == 'ubMountInBattle':
            m.builds.append(_parseUbMountInBattle(m, child))
        else:
            logInfo('%s: ignoring unknown element <%s>' % (m.modName, child.tag))

    if not m.builds and not m.definitions:
        logInfo('%s: manifest has nothing to build' % m.modName)

    return m

def _parseRequires(m, node, scope):




    if node.get('mod') is not None or node.get('version') is not None:
        name = (node.get('mod') or 'Other').strip()
        version = (node.get('version') or '').strip()
        if version and version[0] not in '<>=':
            version = '>=' + version
        if Requires.nameProblem(name):
            raise ManifestError(
                "%s: <requires mod=> and version= are gone; write <requires "
                "mods='Name%s'/>, with that mod renamed: %s"
                % (m.modName, version, Requires.nameProblem(name)))
        raise ManifestError(
            "%s: <requires mod=> and version= are gone; write <requires "
            "mods='%s%s'/>" % (m.modName, name, version))
    _warnUnknown(node, _KNOWN_REQUIRES_ATTRS, 'requires attribute', m.modName)
    inst = node.get('installer')
    mods = node.get('mods')
    if inst is not None and mods is not None:
        raise ManifestError('%s: <requires> takes installer= or mods=, not '
                            'both; write two <requires>' % m.modName)
    if inst is not None:
        if scope != '<mod>':
            raise ManifestError('%s: <requires installer=> belongs directly '
                                'under <mod>, not in %s' % (m.modName, scope))
        m.installerRequirement = inst.strip()
        return None
    if mods is None:
        logInfo('%s: <requires> needs `installer` or `mods` attribute'
                % m.modName)
        return None
    try:
        return Requires.parse(mods)
    except Requires.RequiresError as exc:
        raise ManifestError("%s: <requires mods='%s'> in %s: %s"
                            % (m.modName, mods, scope, exc))

def _parseBuild(m, node):
    _warnUnknown(node, _KNOWN_BUILD_ATTRS, 'build attribute', m.modName)
    b = BuildSpec()
    if not node.get('file'):
        raise ManifestError("%s: <build> requires `file`" % m.modName)
    b.file = _relPath(m, node.get('file'), 'file')
    root = node.get('root')
    b.root = root.strip() if root else None
    if b.root is not None and not _TAG_RE.match(b.root):
        raise ManifestError("%s: <build root='%s'> is not a usable element name"
                            % (m.modName, b.root))
    b.restartOnChange = _bool(m, node.get('restartOnChange'),
                              "<build file='%s' restartOnChange" % b.file)
    for child in node:
        if child.tag == 'guard':
            if b.root:
                raise ManifestError(
                    "%s: <build file='%s' root='%s'> cannot carry a <guard>; "
                    "it starts from an empty document" % (m.modName, b.file,
                                                          b.root))
            b.guards.append(_parseGuard(m, child))
        elif child.tag == 'requires':
            if b.root:


                raise ManifestError(
                    "%s: <build file='%s' root='%s'> cannot carry a "
                    "<requires>; put it under <mod>, in a blueprint of its "
                    "own" % (m.modName, b.file, b.root))
            b.requirement = Requires.allOf([b.requirement, _parseRequires(
                m, child, "<build file='%s'>" % b.file)])
        else:
            action = _parseAction(m, child, "<build file='%s'>" % b.file)
            if action is not None:
                b.actions.append(action)
    return b

def _relPath(m, value, attr):



    path = value.strip().replace('\\', '/')
    parts = [p for p in path.split('/') if p not in ('', '.')]
    if path.startswith('/') or (parts and ':' in parts[0]):
        raise ManifestError("%s: %s='%s' must be relative"
                            % (m.modName, attr, value))
    if '..' in parts:
        raise ManifestError("%s: %s='%s' may not contain '..'"
                            % (m.modName, attr, value))
    if not parts:
        raise ManifestError("%s: %s='%s' names no file"
                            % (m.modName, attr, value))
    return '/'.join(parts)

def _parseAction(m, node, context):
    parser = _ACTION_PARSERS.get(node.tag)
    if parser is None:
        logInfo('%s: ignoring unknown child <%s> inside %s'
                % (m.modName, node.tag, context))
        return None
    return parser(m, node)

def _parseNested(m, node, context):
    out = []
    for child in node:
        action = _parseAction(m, child, context)
        if action is not None:
            out.append(action)
    return out

def _parseGuard(m, node):
    _warnUnknown(node, _KNOWN_GUARD_ATTRS, 'guard attribute', m.modName)
    if node.get('ifExists') is not None and node.get('ifNotExists') is not None:
        raise ManifestError('%s: <guard> takes ifExists= or ifNotExists=, not '
                            'both; write two <guard>' % m.modName)
    expr = node.get('ifExists')
    if expr is not None:
        return Guard('ifExists', expr)
    expr = node.get('ifNotExists')
    if expr is not None:
        return Guard('ifNotExists', expr)
    raise ManifestError(
        '%s: <guard> requires either ifExists or ifNotExists' % m.modName)

def _parseInsert(m, node):
    _warnUnknown(node, _KNOWN_INSERT_ATTRS, 'insert attribute', m.modName)
    a = ActionSpec('insert')
    a.into = node.get('into')
    a.before = node.get('before')
    a.after = node.get('after')
    if not a.into and not a.before and not a.after:
        raise ManifestError('%s: <insert> needs into=, before=, or after='
                            % m.modName)
    a.payload = list(node)
    if not a.payload:
        logInfo('%s: <insert> has no payload elements; will be a no-op'
                % m.modName)
    return a

def _parseRemove(m, node):
    _warnUnknown(node, _KNOWN_REMOVE_ATTRS, 'remove attribute', m.modName)
    a = ActionSpec('remove')
    a.select = node.get('select')
    if not a.select:
        raise ManifestError('%s: <remove> needs `select`' % m.modName)
    return a

def _parseReplace(m, node):
    _warnUnknown(node, _KNOWN_REPLACE_ATTRS, 'replace attribute', m.modName)
    a = ActionSpec('replace')
    a.select = node.get('select')
    if not a.select:
        raise ManifestError('%s: <replace> needs `select`' % m.modName)
    a.payload = list(node)
    return a

def _parseSetAttribute(m, node):
    _warnUnknown(node, _KNOWN_SET_ATTRIBUTE_ATTRS, 'setAttribute attribute',
                 m.modName)
    a = ActionSpec('setAttribute')
    a.select = node.get('select')
    a.attribute = node.get('attribute')
    a.fromValue = node.get('from')
    a.toValue = node.get('to')
    if not a.attribute or a.toValue is None:
        raise ManifestError(
            '%s: <setAttribute> needs `attribute` and `to`' % m.modName)
    return a

def _parseCopy(m, node):
    _warnUnknown(node, _KNOWN_COPY_ATTRS, 'copy attribute', m.modName)
    a = ActionSpec('copy')
    a.select = node.get('select')
    source = node.get('from')
    a.source = _relPath(m, source, 'from') if source else None
    a.into = node.get('into')
    a.before = node.get('before')
    a.after = node.get('after')
    if not a.select:
        raise ManifestError('%s: <copy> needs `select`' % m.modName)
    if not a.into and not a.before and not a.after:
        raise ManifestError(
            '%s: <copy> needs into=, before=, or after=' % m.modName)
    a.actions = _parseNested(m, node, "<copy select='%s'>" % a.select)
    return a

_ACTION_PARSERS = {
    'insert': _parseInsert,
    'remove': _parseRemove,
    'replace': _parseReplace,
    'setAttribute': _parseSetAttribute,
    'copy': _parseCopy,
}

DEFINITION_VERBS = {'block': 'ubBuildBlock', 'css': 'ubBuildStyle'}
DEFINITION_DIRS = {'block': PAYLOAD_DIR, 'css': PAYLOAD_DIR + 'css/'}
USS_DEFINITION_DIRS = {'block': USS_PAYLOAD_DIR,
                       'css': USS_PAYLOAD_DIR + 'css/'}





_FILE_SAFE = set('abcdefghijklmnopqrstuvwxyz'
                 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-$')


_RESERVED_STEMS = ('markup', 'styles', 'con', 'prn', 'aux', 'nul')
_RESERVED_PREFIXES = ('com', 'lpt')

def definitionFile(namespace, name):
    if isinstance(name, unicode):
        name = name.encode('utf-8')
    out = []
    for ch in name:
        out.append(ch if ch in _FILE_SAFE else '%%%02X' % ord(ch))
    stem = ''.join(out)
    if _isReservedStem(stem):
        stem = '%%%02X%s' % (ord(stem[0]), stem[1:])
    return DEFINITION_DIRS[namespace] + stem + '.xml'

def _isReservedStem(stem):
    low = stem.lower()
    if low in _RESERVED_STEMS:
        return True
    return (len(low) == 4 and low[:3] in _RESERVED_PREFIXES
            and low[3] in '123456789')

def ussDefinitionPath(namespace, name):
    return (USS_DEFINITION_DIRS[namespace]
            + definitionFile(namespace, name).rsplit('/', 1)[1])

def _parseDefinition(m, node, namespace):
    label = DEFINITION_VERBS[namespace]
    _warnUnknown(node, _KNOWN_DEFINITION_ATTRS, '%s attribute' % label,
                 m.modName)
    name = node.get('name')
    name = name.strip() if name else ''
    if not name:
        raise ManifestError('%s: <%s> requires `name`' % (m.modName, label))

    d = DefinitionSpec()
    d.namespace = namespace
    d.name = name
    context = "<%s name='%s'>" % (label, name)
    for child in node:
        if child.tag == 'guard':
            raise ManifestError(
                '%s: %s cannot carry a <guard>; a definition is assembled from '
                'the vanilla one when it exists and from nothing when it does '
                'not' % (m.modName, context))
        if child.tag == 'requires':
            d.requirement = Requires.allOf(
                [d.requirement, _parseRequires(m, child, context)])
            continue
        action = _parseAction(m, child, context)
        if action is not None:
            d.actions.append(action)
    if not d.actions:
        raise ManifestError('%s: %s has nothing to change'
                            % (m.modName, context))
    return d





DEFINITIONS_SWF = PAYLOAD_DIR + 'ForgeDefinitions.swf'
USS_DEFINITIONS_SWF = USS_PAYLOAD_DIR + 'ForgeDefinitions.swf'

def registrationBuild(xmlPaths, swfPath=None):
    payload = [_textElement('xmlfile', p) for p in xmlPaths]
    if swfPath:
        payload.append(_textElement('swffile', swfPath))
    a = ActionSpec('insert')
    a.into = 'mods'
    a.payload = payload
    b = BuildSpec()
    b.file = USS_SETTINGS
    b.actions.append(a)
    return b

def _parseUbMountInBattle(m, node):
    _warnUnknown(node, _KNOWN_UB_MOUNT_ATTRS, 'ubMountInBattle attribute',
                 m.modName)
    unbound = node.get('unbound')
    if unbound is None:
        raise ManifestError("%s: <ubMountInBattle> requires unbound='1' or "
                            "unbound='2'" % m.modName)
    unbound = unbound.strip()
    if unbound not in ('1', '2'):
        raise ManifestError("%s: <ubMountInBattle unbound='%s'> must be '1' or "
                            "'2'" % (m.modName, unbound))
    rootElementId = (node.get('rootElementId') or '').strip()
    if not rootElementId:
        raise ManifestError('%s: <ubMountInBattle> requires `rootElementId`'
                            % m.modName)
    name = (node.get('name') or rootElementId).strip()
    if not name:
        raise ManifestError('%s: <ubMountInBattle> has an empty `name`'
                            % m.modName)

    element = _u2.Element('element')
    element.set('name', name)
    url = node.get('url')
    if url:
        element.set('url', url.strip())
    props = _u2.SubElement(element, 'properties')
    props.set('hitTest', 'true' if _hitTest(m, node.get('hitTest'))
              else 'false')

    before, after = _mountAnchors(m, node)

    b = BuildSpec()
    b.file = BATTLE_ELEMENTS
    for child in node:
        if child.tag == 'requires':
            b.requirement = Requires.allOf([b.requirement, _parseRequires(
                m, child, '<ubMountInBattle>')])
        else:
            logInfo('%s: ignoring unknown child <%s> inside <ubMountInBattle>'
                    % (m.modName, child.tag))
    if unbound == '1':
        element.set('class', UNBOUND_ELEMENT_CLASS)
        props.set('rootElementId', rootElementId)
    else:
        element.set('class', UNBOUND2_ELEMENT_CLASS)
        element.set('elementName', rootElementId)
    b.actions.append(_insertInto('elementList', element, before, after))
    if unbound == '1':
        controller = _u2.Element('controller')
        controller.set('class', UNBOUND_CONTROLLER_CLASS)
        controller.set('clips', name)
        b.actions.append(_insertInto('controllers', controller))
    return b

def _mountAnchors(m, node):











    before = (node.get('before') or '').strip()
    after = (node.get('after') or '').strip()
    if before and after:
        raise ManifestError('%s: <ubMountInBattle> takes before= or after=, '
                            'not both' % m.modName)
    asSelector = lambda v: "element[@elementName='%s']" % v if v else None
    if (before or after).find("'") >= 0:
        raise ManifestError("%s: <ubMountInBattle> anchor cannot contain a "
                            "quote: %s" % (m.modName, before or after))
    return asSelector(before), asSelector(after)

def _insertInto(container, payloadElement, before=None, after=None):
    a = ActionSpec('insert')
    a.into = container
    a.before = before
    a.after = after
    a.payload = [payloadElement]
    return a

def _textElement(tag, text):
    el = _u2.Element(tag)
    el.text = text
    return el

_TAG_RE = re.compile(r'^[A-Za-z_][\w.-]*$')
_NAME_RE = re.compile(r'^[A-Za-z0-9_.-]+$')

def _hitTest(m, value):


    return _bool(m, value, '<ubMountInBattle hitTest')

def _bool(m, value, label):
    if value is None:
        return False
    word = value.strip().lower()
    if word not in ('true', 'false'):
        logError("%s: %s='%s'> is not true or false; using false"
                 % (m.modName, label, value))
    return word == 'true'

def _warnUnknown(node, knownAttrs, label, context):
    for key in node.keys():
        if key not in knownAttrs:
            logInfo('%s: unknown %s `%s`' % (context, label, key))

_VERSION_RE = re.compile(r'^(\d+(?:\.\d+)*)')
_CONSTRAINT_RE = re.compile(r'^(>=|<=|==|>|<)?\s*(\d+(?:\.\d+)*)\s*$')

def parseVersion(text):
    if not text:
        return None
    m = _VERSION_RE.match(text.strip())
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split('.'))

def _alignedPair(a, b):
    width = max(len(a), len(b))
    return (a + (0,) * (width - len(a)), b + (0,) * (width - len(b)))

def satisfiesConstraint(versionText, constraint):
    if constraint is None or not constraint.strip():
        return True
    m = _CONSTRAINT_RE.match(constraint.strip())
    if not m:
        return False
    op = m.group(1) or '>='
    required = parseVersion(m.group(2))
    actual = parseVersion(versionText)
    if required is None or actual is None:
        return False
    actual, required = _alignedPair(actual, required)
    if op == '>=':
        return actual >= required
    if op == '<=':
        return actual <= required
    if op == '==':
        return actual == required
    if op == '>':
        return actual > required
    if op == '<':
        return actual < required
    return False
