# coding=utf-8

import re

import Ub1Vocab as V
import Ub1Verbs as VB
import UssTrans

STALL = 'stall'
THROW = 'throw'
COMPILE = 'compile'
DEAD = 'dead'
WARN = 'warn'
SEVERITIES = (STALL, THROW, COMPILE, DEAD, WARN)

EXPRESSION_TAGS = ('bind', 'innerBind', 'userData', 'background9Slice')

class Finding(object):
    __slots__ = ('severity', 'code', 'where', 'message')

    def __init__(self, severity, code, where, message):
        self.severity = severity
        self.code = code
        self.where = where
        self.message = message

    def __repr__(self):
        return '%s %s %s: %s' % (self.severity, self.code, self.where,
                                 self.message)

class Context(object):
    def __init__(self, classNames=None, cssNames=None, exprKeys=None,
                 classes=None, controllers=None):
        self.classNames = classNames
        self.cssNames = cssNames
        self.exprKeys = exprKeys

        self.classes = classes
        self.controllers = controllers

EVIDENCE = {
    'A1': 'probed: a registered payload that will not load hangs at LOGIN',
    'B1': 'probed: #1006 null is not a function at UbNativeExpression/eval',
    'B4': 'probed: #1006 null is not a function at UbNativeExpression/eval',
    'C1': 'probed: #1056 unknown write; #1074 read-only write',
    'C2': 'bytecode: setBlockSettings writes block[name]; #1056 as C1',
    'C4': 'bytecode: reads part 0 of an empty vector; #1125 as C5',
    'C5': 'probed: #1125 index out of range',
    'C6': 'bytecode: mounts String(null); missing construction plan as E2',
    'C8': 'probed: #1006 at UbStyleParser/process',
    'C10': 'probed: #1065 at UbControllerBinding/doInit; #1034 as C13',
    'C13': 'probed: #1009 at UbInstanceBinding/createChild',
    'E2': 'probed: missing construction plan at UbBlockFactory/construct',
    'F1': 'probed: unknown value for property flow, LOGIN past 200 s',
    'F6': 'probed: #1009 in objectProcessor, null scope, LOGIN past 200 s',
    'F7': 'bytecode: AdaptativeSize.parse indexes [1] unchecked; load throw '
          'as F6',
}

UNPROVEN = {
    'C12': 'enum-part throws are read from the audit, not probed',
}

PART_HANDLERS = {
    'styleProperty': 'partStyleProperty',
    'cssClass': 'partCssClass',
    'controllerClass': 'partControllerClass',
    'className': 'partClassName',
    'enum': 'partEnum',
}

DEFERRED_KINDS = {
    'number': 'the audit took its throws from Flash Player Timer docs; '
              'new Timer(-1, 1) measured not to throw in Scaleform',
    'boolean': 'each throw also depends on part 2: a compound rule, not a kind',
    'elementName': 'needs descendant name resolution across the document',
}

def refuses(finding):
    return finding.severity in (STALL, THROW) and finding.code in EVIDENCE

def introduced(findings, baseline):
    left = {}
    for f in baseline:
        key = (f.code, f.message)
        left[key] = left.get(key, 0) + 1
    out = []
    for f in findings:
        key = (f.code, f.message)
        if left.get(key):
            left[key] -= 1
        else:
            out.append(f)
    return out

_STRING = re.compile(r"""^\s*(?:'([^']*)'|"([^"]*)")\s*$""")
_INTEGER = re.compile(r'^\s*-?\d+\s*$')
_OBJECT_STRING_VALUE = re.compile(r""":\s*(?:'([^']*)'|"([^"]*)")""")

_ADAPTATIVE = re.compile(r'^\s*-?\d+\s*:\s*[^,]*,\s*-?\d+\s*:\s*-?[\d.]+(aw|ah)\s*$')

def literal(part):
    m = _STRING.match(part)
    if m:
        return ('string', m.group(1) if m.group(1) is not None else m.group(2))
    if _INTEGER.match(part):
        return ('int', int(part))
    s = part.strip()
    if s == 'null':
        return ('null', None)
    if s.startswith('{') and s.endswith('}'):
        return ('object', s)
    return (None, None)

def runtimeParts(value):
    if not value:
        return []
    return value.split(';')

class Linter(object):
    def __init__(self, context=None):
        self.ctx = context or Context()
        self.findings = []

    def add(self, severity, code, where, message):
        self.findings.append(Finding(severity, code, where, message))

    def registration(self, entries, exists, sizeOf=None):
        seen = {}
        for i, (kind, path) in enumerate(entries):
            where = '%s[%d] %s' % (kind, i, path)
            if not exists(path):
                self.add(STALL, 'A1', where,
                         'registered but missing: a SWF that fails to load '
                         'leaves _totalSwfFiles above zero forever, and a '
                         'missing XML throws out of onPlanLoadError before the '
                         'loader queue advances')
            elif sizeOf is not None and not sizeOf(path):
                self.add(STALL, 'A1', where,
                         'registered but empty: it parses to nothing and the '
                         'loader never completes')
            if kind == 'xmlfile' and ('/markup.xml' in path
                                      or '/styles.xml' in path):
                self.add(DEAD, 'E4', where,
                         'once the generated markup is in, preloadMarkup '
                         'splices out every xmlfile whose path contains '
                         '"/markup.xml" or "/styles.xml" -- never loaded')
            if path in seen:
                self.add(WARN, 'A4', where,
                         'already registered at %s: an xmlfile url listed '
                         'twice never completes the markup load, so the client '
                         'hangs at login; a duplicate SWF pays its load cost '
                         'twice' % seen[path])
            else:
                seen[path] = where
        return self.findings

    def lintDocument(self, root):
        for i, el in enumerate(root):
            if not isinstance(el.tag, basestring):
                continue
            if el.tag == 'block':
                name = el.get('className')
                where = name or 'block[%d]' % i
                if not name:
                    self.add(WARN, 'E5', where, 'top-level <block> has no '
                             'className; it registers under the empty name')
                if el.get('type') is not None:
                    self.add(DEAD, 'D9', where, 'type= on a top-level block is '
                             'ignored: a definition is always an element')
                self.attrs(el, where)
                self.block(el, 'element', where)
            elif el.tag == 'css':
                where = 'css[%s]' % (el.get('name') or i)
                self.attrs(el, where)
                self.styleChildren(el, where)
            else:
                self.add(DEAD, 'D1', '<%s>' % el.tag, 'loadPlansFromXml reads only '
                         'top-level <block> and <css>; this is never looked at')
        return self.findings

    def attrs(self, el, where):
        allowed = V.TAG_ATTRS.get(el.tag)
        if allowed is None:
            return
        for name in sorted(el.attrib):
            if name not in allowed:
                self.add(DEAD, 'D2', where, '%s= is never read on <%s>'
                         % (name, el.tag))

    def block(self, el, blockType, where):
        cls = el.get('className') or ''
        if blockType == 'native' and '.' in cls and cls not in V.NATIVE_CLASSES:
            self.add(WARN, 'C3', where, 'native class %r is not one the '
                     'vocabulary knows; its bindings are unchecked' % cls)
        counters = {}
        for ch in el:
            if not isinstance(ch.tag, basestring):
                continue
            n = counters.get(ch.tag, 0)
            counters[ch.tag] = n + 1
            here = '%s > %s' % (where, self.label(ch, n))
            if ch.tag not in V.BLOCK_CHILD_TAGS:
                hint = ''
                if ch.tag in V.STYLE:
                    hint = ' -- it is a style property; it belongs inside <style>'
                self.add(DEAD, 'D1', here, '<%s> is not read under <block>%s'
                         % (ch.tag, hint))
                continue
            self.attrs(ch, here)
            need = V.CHILD_TAG_NEEDS_TYPE.get(ch.tag)
            if need and blockType != need:
                message = ('<%s> is only read on a %s block; this one is %s'
                           % (ch.tag, need, blockType))
                if ch.tag == 'innerBind':
                    self.add(DEAD, 'D3', here, message)
                else:
                    self.add(DEAD, 'D4', here, message)
                continue
            if ch.tag == 'block':
                raw = ch.get('type', '')
                if raw not in V.ELEMENT_TYPES:
                    self.add(DEAD, 'D8', here, 'type=%r is unknown and silently '
                             'becomes %r' % (raw, V.UNKNOWN_TYPE_BECOMES))
                self.block(ch, V.ELEMENT_TYPES.get(raw, V.UNKNOWN_TYPE_BECOMES),
                           here)
            elif ch.tag in ('bind', 'innerBind'):
                self.bind(ch, blockType, cls, here)
            elif ch.tag == 'style':
                self.styleChildren(ch, here)
            elif ch.tag == 'styleClass':
                self.styleClass(ch, here)
            elif ch.tag == 'params':
                self.params(ch, blockType, cls, here)

    def label(self, el, n):
        if el.tag == 'block' and el.get('className'):
            return 'block[%s]' % el.get('className')
        if el.tag in ('bind', 'innerBind') and el.get('name') is not None:
            return '%s[%s]' % (el.tag, el.get('name'))
        return '%s[%d]' % (el.tag, n)

    def bind(self, el, blockType, cls, where):
        name = el.get('name', '')
        value = el.get('value')
        parts = runtimeParts(value)
        self.expressions(value or '', where)
        if el.tag == 'innerBind':
            return
        if name in V.VERBS:
            if blockType == 'native' and name in V.REQUIRES_BLOCK_HOST:
                self.add(THROW, 'C13', where, '%s needs a UbBlock host, but on '
                         'a native block the binding target is the native '
                         'child: the cast yields null and the block cannot be '
                         'built' % name)
            self.arity(name, parts, where)
            self.verbParts(name, parts, where)
            if name in V.CONSTRUCT:
                self.construct(name, parts, where)
            return
        self.fallback(name, parts, blockType, cls, where)

    def fallback(self, raw, parts, blockType, cls, where):
        bang = raw.endswith('!')
        name = raw[:-1] if bang else raw
        if not name:
            self.add(THROW, 'C1', where, 'empty binding name')
            return
        if not parts and not bang:
            self.add(THROW, 'C4', where, 'a property binding needs a value: '
                     'it reads part 0 of an empty expression vector')
            return
        target, label = self.targetFor(blockType, cls, name)
        if target is None or target['dynamic']:
            return
        if bang:
            if name not in target['methods']:
                self.add(WARN, 'D7', where, '%r is not a method of %s; this '
                         'only works if a controller puts a scope function of '
                         'that name in scope, and otherwise does nothing'
                         % (name, label))
            return
        if name in target['write']:
            return
        if name in target['read'] or name in target['methods']:
            self.add(THROW, 'C1', where, '%r is read-only on %s (#1074)'
                     % (name, label))
        else:
            self.add(THROW, 'C1', where, '%r is neither a verb nor a property '
                     'of %s (#1056 -- in a port block this stops the port '
                     'from presenting)' % (name, label))

    def targetFor(self, blockType, cls, name):
        if blockType == 'native' and name not in V.NATIVE_SELF:
            if cls in V.NATIVE_CLASSES:
                return V.NATIVE_CLASSES[cls], cls
            return None, 'library symbol %r' % cls
        return V.TARGETS[blockType], _className(blockType)

    def arity(self, verb, parts, where):
        bounds = VB.MIN_PARTS.get(verb)
        if bounds is None:
            return
        initMin, allMin = bounds
        n = len(parts)
        if n < initMin:
            self.add(THROW, 'C5', where, '%s reads part %d while the block is '
                     'built and this has %d: past the end of the expression '
                     'vector (#1125)' % (verb, initMin - 1, n))
        elif n < allMin:
            self.add(THROW, 'C5', where, '%s reads part %d on a path ordinary '
                     'use triggers and this has %d: it throws #1125 the moment '
                     'that runs' % (verb, allMin - 1, n))
        ceiling = VB.MAX_READ.get(verb)
        if ceiling is not None and n > ceiling:
            self.add(DEAD, 'C15', where, '%s reads %d part(s); the %d after '
                     'that are compiled and never read'
                     % (verb, ceiling, n - ceiling))
        need = VB.NEEDED.get(verb)
        if need is not None and max(initMin, allMin) <= n < need:
            self.add(DEAD, 'C7', where, '%s needs %d parts to do anything and '
                     'has %d: it is built without error and then never acts'
                     % (verb, need, n))

    def verbParts(self, verb, parts, where):
        for index, kind, allowed, effect in VB.PARTS.get(verb, ()):
            if index >= len(parts):
                continue
            lit, value = literal(parts[index])
            if lit != 'string' and kind != 'enum':
                continue
            handler = PART_HANDLERS.get(kind)
            if handler is not None:
                getattr(self, handler)(verb, parts, index, value, allowed,
                                       effect, where)

    def partStyleProperty(self, verb, parts, index, value, allowed, effect,
                          where):
        self.styleKey(verb, parts, index, value, where)

    def partCssClass(self, verb, parts, index, value, allowed, effect, where):
        if self.ctx.cssNames is not None and value not in self.ctx.cssNames:
            self.add(DEAD, 'C9', where, '%s names the style class %r, '
                     'which no <css> defines; addStyleClass ignores it'
                     % (verb, value))

    def partControllerClass(self, verb, parts, index, value, allowed, effect,
                            where):
        if '.' not in value or self.ctx.classes is None:
            return
        if value not in self.ctx.classes:
            self.add(THROW, 'C10', where, '%s names %r, which is not a '
                     'class in the scene: getDefinitionByName throws '
                     '#1065' % (verb, value))
        elif (self.ctx.controllers is not None
              and value.split('.')[-1] not in self.ctx.controllers):
            self.add(THROW, 'C10', where, '%s names %r, which exists '
                     'but does not extend UbController: the coercion '
                     'throws #1034' % (verb, value))

    def partClassName(self, verb, parts, index, value, allowed, effect, where):
        if verb != 'mc' or self.ctx.classes is None:
            return
        if '.' in value and value not in self.ctx.classes:
            self.add(DEAD, 'C11', where, '%s names %r, '
                     'which is not a class in the scene: hasDefinition fails '
                     'and the binding silently does nothing' % (verb, value))

    def partEnum(self, verb, parts, index, value, allowed, effect, where):
        if allowed:
            self.enumPart(verb, index, parts[index], allowed, effect, where)

    def styleKey(self, verb, parts, index, value, where):
        if value in V.STYLE:
            return
        writable = value in V.STYLE_OBJECT_WRITE
        valueKind = literal(parts[1])[0] if len(parts) > 1 else None
        if valueKind == 'string':
            self.add(THROW, 'C8', where, '%r is not in the style parser table, '
                     'and the value is a string, so process() calls undefined'
                     % value)
        elif writable:
            return
        elif valueKind is None:
            self.add(WARN, 'C8', where, '%r is neither a parsed style property '
                     'nor a property of UbStyle: it throws either way once the '
                     'value is known (#1056, or a call to undefined for a '
                     'string)' % value)
        else:
            self.add(THROW, 'C8', where, '%r is not a property of UbStyle, '
                     'which is sealed: writing it throws #1056' % value)

    def enumPart(self, verb, index, part, allowed, effect, where):
        lit, value = literal(part)
        if lit is None:
            return
        text = value if lit == 'string' else part.strip()

        bad = [t.strip() for t in text.split(',') if t.strip() not in allowed]
        if not bad:
            return
        severity = THROW if effect in ('throw-init', 'throw-lazy') else DEAD
        self.add(severity, 'C12', where, '%s part %d has %s, not %s'
                 % (verb, index, ', '.join(repr(b) for b in bad),
                    ' / '.join(sorted(allowed))))

    def construct(self, verb, parts, where):
        minParts, at = V.CONSTRUCT[verb]
        if len(parts) < minParts:
            return
        if at == 'child':
            names = self.childNames(verb, parts, where)
        else:
            kind, val = literal(parts[at])
            names = [val] if kind == 'string' else []
        known = self.ctx.classNames
        if known is None:
            return
        for name in names:
            if name and name not in known:
                self.add(THROW, 'E2', where, '%s names %r, which nothing '
                         'defines: "missing construction plan"' % (verb, name))

    def childNames(self, verb, parts, where):
        dm = 1
        if len(parts) > 2:
            kind, _ = literal(parts[1])
            if kind in ('object', 'null'):
                dm = 2
            elif kind is None:
                return []
        kind, val = literal(parts[dm])
        if kind == 'object':
            return [a or b for a, b in _OBJECT_STRING_VALUE.findall(val)]
        if kind is None:
            return []
        names = []
        for p in parts[dm:]:
            k, v = literal(p)
            if k == 'string':
                names.append(v)
        idxKind, idx = literal(parts[0])
        count = len(parts) - dm
        if idxKind == 'int' and not 0 <= idx < count:
            self.add(THROW, 'C6', where, '%s index %d is past its %d names, so '
                     'it mounts String(null) == "null" and constructs it'
                     % (verb, idx, count))
        return names

    def expressions(self, value, where):
        try:
            compiled = UssTrans.split_row(value)
        except Exception as exc:
            self.add(COMPILE, 'B2', where, str(exc).split('\n')[0])
            return
        if value and compiled != value.split(';'):
            self.add(THROW, 'B4', where, 'a ";" inside a string literal: the '
                     'compiler splits around quotes but the runtime does not, '
                     'so the runtime asks for keys that were never compiled')
        for part in compiled:
            try:
                UssTrans.parse_part(part)
            except Exception as exc:
                self.add(COMPILE, 'B2', where, '%r does not compile: %s'
                         % (part.strip()[:60], str(exc).split('\n')[0]))
                continue
            keys = self.ctx.exprKeys
            if keys is not None and part and part not in keys:
                self.add(THROW, 'B1', where, 'no loaded SWF carries the key %r '
                         '(#1006 on first evaluation)' % part.strip()[:60])

    def styleChildren(self, el, where):
        for ch in el:
            if not isinstance(ch.tag, basestring):
                continue
            here = '%s > %s' % (where, ch.tag)
            spec = V.STYLE.get(ch.tag)
            if spec is None:
                self.add(DEAD, 'F2', here, 'not a style property; '
                         'parseXml drops it')
                continue
            for name in sorted(ch.attrib):
                if name != 'value':
                    self.add(DEAD, 'D2', here, '%s= is never read on a style '
                             'property' % name)
            value = ch.get('value', '')
            self.styleValue(ch.tag, spec, value, here)

    def styleValue(self, prop, spec, value, where):
        kind, arg = spec
        if kind == 'enum':
            if value not in arg:
                self.add(STALL, 'F1', where, '%r is not one of %s: '
                         'enumStyleProcessor throws while the XML loads'
                         % (value, ', '.join(sorted(arg))))
        elif kind == 'flags':
            bad = [t for t in value.split('|') if t not in arg]
            if bad:
                self.add(DEAD, 'F3', where, 'unknown %s token(s) %s are skipped'
                         % (prop, ', '.join(repr(b) for b in bad)))
        elif kind == 'boolean':
            if value not in ('true', 'false'):
                self.add(DEAD, 'F4', where, '%r is false: only the exact string '
                         '"true" is true' % value)
        elif kind == 'hex':
            if not re.match(r'^\s*(0[xX][0-9a-fA-F]+|\d+)\s*$', value):
                self.add(DEAD, 'F5', where, '%r is not a number; uint() makes it 0'
                         % value)
        elif kind == 'number':
            if not re.match(r'^\s*-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\s*$',
                            value):
                self.add(DEAD, 'F5', where, '%r is not a number; Number() makes '
                         'it NaN' % value)
        elif kind == 'dimension':
            self.dimension(prop, value, where, adaptative=True)
        elif kind == 'fontSize':
            self.dimension(prop, value, where, adaptative=False)
        elif kind == 'rect':
            sep = arg[0] if arg else '|'
            fields = value.split(sep)
            if len(fields) not in (1, 2, 4):
                self.add(DEAD, 'F9', where, '%d %r-separated values: UbRect '
                         'reads 1 as all sides and 4 as l|r|t|b, and anything '
                         'else as just the first two' % (len(fields), sep))
            for field in fields:
                self.dimension(prop, field, where, adaptative=True)
        elif kind == 'object':
            self.expressions(value, where)
            try:
                reads = [p for part in UssTrans.split_row(value) if part
                         for p in UssTrans.parse_part(part)[2]]
            except Exception:
                return
            if reads:
                self.add(STALL, 'F6', where, 'evalNoScope runs this with a null '
                         'scope while the XML loads, and it reads %s'
                         % ', '.join(sorted(set(reads))))

    def dimension(self, prop, value, where, adaptative):
        if adaptative and ('aw' in value or 'ah' in value):
            if not _ADAPTATIVE.match(value):
                self.add(STALL, 'F7', where, '%r uses aw/ah without the two '
                         'breakpoints: AdaptativeSize.parse splits on "," and '
                         'indexes [1] unchecked, so this is a null dereference '
                         'while the XML loads' % value)
            return
        if 'auto' in value:
            return
        digits = [c for c in value if c == '.' or c == '-' or c.isdigit()]
        if digits:
            try:
                float(''.join(digits))
                return
            except Exception:
                pass
        if 'f' in value:
            return
        self.add(DEAD, 'F8', where, '%r has no usable number: everything but '
                 'digits, "." and "-" is stripped, and what is left is not a '
                 'number, so the value becomes NaN' % value)

    def styleClass(self, el, where):
        names = self.ctx.cssNames
        value = el.get('value', '')
        if names is not None and value not in names:
            self.add(DEAD, 'D5', where, 'styleClass %r names no <css>; '
                     'addStyleClass ignores it without a word' % value)

    def params(self, el, blockType, cls, where):
        for i, p in enumerate(el):
            if not isinstance(p.tag, basestring):
                continue
            here = '%s > param[%s]' % (where, p.get('name', i))
            if p.tag != 'param':
                self.add(DEAD, 'D1', here, '<%s> under <params> is not read'
                         % p.tag)
                continue
            self.attrs(p, here)
            name = p.get('name', '')
            if blockType == 'native':
                target = V.NATIVE_CLASSES.get(cls)
                label = cls
            else:
                target = V.TARGETS[blockType]
                label = _className(blockType)
            if target is None or target['dynamic']:
                continue
            if name not in target['write']:
                self.add(THROW, 'C2', here, '<param name=%r>: setBlockSettings '
                         'writes it onto %s, which has no such writable property'
                         % (name, label))

def _className(blockType):
    return V.TARGETS[blockType]['chain'][0].split('.')[-1]

def lintDocument(root, context=None):
    return Linter(context).lintDocument(root)

def lintRegistration(entries, exists, sizeOf=None, context=None):
    return Linter(context).registration(entries, exists, sizeOf)

def definitions(root):
    blocks = [el.get('className') for el in root
              if getattr(el, 'tag', None) == 'block' and el.get('className')]
    css = [el.get('name') for el in root
           if getattr(el, 'tag', None) == 'css' and el.get('name')]
    return blocks, css
