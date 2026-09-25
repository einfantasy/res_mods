# coding=utf-8

import UssAst as ast
import UssOrTable

GETLOCAL0, GETLOCAL1, GETLOCAL2, GETLOCAL3 = 0xD0, 0xD1, 0xD2, 0xD3
SETLOCAL3 = 0xD7
PUSHSCOPE, POPSCOPE, GETSCOPEOBJECT = 0x30, 0x1D, 0x65
RETURNVOID, RETURNVALUE, CONSTRUCTSUPER = 0x47, 0x48, 0x49
GETLEX, FINDPROPSTRICT = 0x60, 0x5D
GETPROPERTY, SETPROPERTY, INITPROPERTY = 0x66, 0x61, 0x68
CALLPROPERTY, CALLPROPVOID = 0x46, 0x4F
NEWCLASS, NEWOBJECT, NEWARRAY = 0x58, 0x55, 0x56
APPLYTYPE, CONSTRUCT = 0x53, 0x42
PUSHNULL, PUSHTRUE, PUSHFALSE = 0x20, 0x26, 0x27
PUSHSTRING, PUSHBYTE, PUSHSHORT, PUSHINT, PUSHDOUBLE = 0x2C, 0x24, 0x25, 0x2D, 0x2F
DUP, POP, COERCE_A, COERCE_S, NOT = 0x2A, 0x29, 0x82, 0x85, 0x96
CONVERT_B, CONVERT_S, DECREMENT = 0x76, 0x70, 0x93
JUMP, IFTRUE, IFFALSE = 0x10, 0x11, 0x12

BINOP = {
    u'+': 0xA0, u'-': 0xA1, u'*': 0xA2, u'/': 0xA3, u'%': 0xA4,
    u'<<': 0xA5, u'>>': 0xA6, u'>>>': 0xA7,
    u'&': 0xA8, u'|': 0xA9, u'^': 0xAA,
    u'==': 0xAB, u'===': 0xAC,
    u'<': 0xAD, u'<=': 0xAE, u'>': 0xAF, u'>=': 0xB0,
    u'instanceof': 0xB1,
}
NEGATED = {u'!=': 0xAB, u'!==': 0xAC}
UNOP = {u'!': NOT, u'-': 0x90, u'~': 0x97}

BOOLEAN_WRAPPED = (u'&&', u'<', u'>', u'<=', u'>=')

NS_PACKAGE, NS_PACKAGE_INTERNAL, NS_PRIVATE = 0x16, 0x18, 0x05
NS_PROTECTED, NS_PLAIN, NS_STATIC_PROTECTED = 0x17, 0x08, 0x1A

BUILTIN_NS = 'http://adobe.com/AS3/2006/builtin'

CTX_VALUE, CTX_TERNARY, CTX_NOT, CTX_AND = ('value', 'ternary',
                                            'notop', 'andop')

def u30_bytes(v):
    out = bytearray()
    v &= 0xFFFFFFFF
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return out

class Pool(object):
    def __init__(self):
        self.ints = []
        self.uints = []
        self.doubles = []
        self.strings = []
        self.namespaces = []
        self.ns_sets = []
        self.multinames = []
        self._st = {}
        self._ns = {}
        self._nss = {}
        self._mn = {}
        self._int = {}
        self._dbl = {}

    def st(self, v):
        if isinstance(v, unicode):
            v = v.encode('utf-8')
        i = self._st.get(v)
        if i is None:
            self.strings.append(v)
            i = self._st[v] = len(self.strings)
        return i

    def ns(self, kind, name, unique=False):
        key = (kind, name, len(self.namespaces) if unique else None)
        i = self._ns.get(key)
        if i is None:
            self.namespaces.append({'kind': kind, 'name': self.st(name)})
            i = self._ns[key] = len(self.namespaces)
        return i

    def ns_raw(self, kind, name_index):
        self.namespaces.append({'kind': kind, 'name': name_index})
        return len(self.namespaces)

    def nss(self, members):
        key = tuple(members)
        i = self._nss.get(key)
        if i is None:
            self.ns_sets.append(list(members))
            i = self._nss[key] = len(self.ns_sets)
        return i

    def _mname(self, d):
        key = tuple(sorted(d.items()))
        i = self._mn.get(key)
        if i is None:
            self.multinames.append(d)
            i = self._mn[key] = len(self.multinames)
        return i

    def qname(self, ns, name):
        return self._mname({'kind': 0x07, 'ns': ns, 'name': self.st(name)})

    def multi(self, name, ns_set):
        return self._mname({'kind': 0x09, 'name': self.st(name),
                            'ns_set': ns_set})

    def multil(self, ns_set):
        return self._mname({'kind': 0x1B, 'ns_set': ns_set})

    def i32(self, v):
        v &= 0xFFFFFFFF
        i = self._int.get(v)
        if i is None:
            self.ints.append(v)
            i = self._int[v] = len(self.ints)
        return i

    def dbl(self, v):
        key = repr(v)
        i = self._dbl.get(key)
        if i is None:
            self.doubles.append(v)
            i = self._dbl[key] = len(self.doubles)
        return i

class Asm(object):
    def __init__(self, depth=0):
        self.code = bytearray()
        self.depth = depth
        self.max = depth
        self.last = None
        self.last_start = None
        self._dup_bytes = None
        self._dup_run = 0
        self._fix = []

    def _grow(self, delta):
        self.depth += delta
        if self.depth > self.max:
            self.max = self.depth

    def op(self, code, delta=0):
        self._dup_bytes = None
        self._dup_run = 0
        self.last_start = len(self.code)
        self.code.append(code)
        self.last = code
        self._grow(delta)

    def op_u30(self, code, arg, delta=0):
        self._dup_bytes = None
        self._dup_run = 0
        self.last_start = len(self.code)
        self.code.append(code)
        self.last = code
        self.code += u30_bytes(arg)
        self._grow(delta)

    def op_u8(self, code, arg, delta=0):
        self._dup_bytes = None
        self._dup_run = 0
        self.last_start = len(self.code)
        self.code.append(code)
        self.last = code
        self.code.append(arg & 0xFF)
        self._grow(delta)

    def op_u30_u30(self, code, a, b, delta=0):
        self._dup_bytes = None
        self._dup_run = 0
        self.last_start = len(self.code)
        self.code.append(code)
        self.last = code
        self.code += u30_bytes(a)
        self.code += u30_bytes(b)
        self._grow(delta)

    def push(self, buf, delta=1):
        run = self._dup_run
        if self._dup_bytes is not None and self._dup_bytes == buf and run < 2:
            self.op(DUP, delta)
            self._dup_bytes = buf
            self._dup_run = run + 1
            return
        self.last_start = len(self.code)
        self.code += buf
        self.last = buf[0]
        self._grow(delta)
        self._dup_bytes = bytearray(buf)
        self._dup_run = 0

    def reserve(self, n):
        if self.depth + n > self.max:
            self.max = self.depth + n

    def coerce_once(self, bool_ctx=False):
        if bool_ctx:
            if self.last not in (NOT, CONVERT_B):
                self.op(CONVERT_B)
        elif self.last != COERCE_A:
            self.op(COERCE_A)

    def branch(self, code):
        self.code.append(code)
        self.last = code
        pos = len(self.code)
        self.code += b'\x00\x00\x00'
        if code in (IFTRUE, IFFALSE):
            self._grow(-1)
        return pos

    def here(self, pos, depth=None):
        target = len(self.code)
        off = target - (pos + 3)
        if off < 0:
            off += 1 << 24
        self.code[pos] = off & 0xFF
        self.code[pos + 1] = (off >> 8) & 0xFF
        self.code[pos + 2] = (off >> 16) & 0xFF
        if depth is not None:
            self.depth = depth
            if depth > self.max:
                self.max = depth

_HEX_DIGITS = frozenset(u'0123456789abcdefABCDEF')

def _unquote(tok):
    if len(tok) >= 2 and tok[0] in u'\'"' and tok[-1] == tok[0]:
        body = tok[1:-1]
    else:
        body = tok
    if u'\\' not in body:
        return body
    out = []
    i = 0
    simple = {u'n': u'\n', u't': u'\t', u'r': u'\r', u'b': u'\b',
              u'f': u'\f', u'v': u'\v', u'0': u'\0'}
    while i < len(body):
        c = body[i]
        if c != u'\\' or i + 1 >= len(body):
            out.append(c)
            i += 1
            continue
        n = body[i + 1]
        hex4 = body[i + 2:i + 6]

        if n == u'u' and len(hex4) == 4 and all(h in _HEX_DIGITS for h in hex4):
            out.append(unichr(int(hex4, 16)))
            i += 6
        elif n == u'x':
            out.append(unichr(int(body[i + 2:i + 4], 16)))
            i += 4
        else:
            out.append(simple.get(n, n))
            i += 2
    return u''.join(out)

def _number(tok):
    t = tok.strip()
    if t[:2].lower() in ('0x', '-0', '+0') and t.lower().lstrip('+-')[:2] == '0x':
        return (int(t, 16), False)
    if t.lower().startswith('0x'):
        return (int(t, 16), False)
    decimal = (u'.' in t) or (u'e' in t.lower())
    if decimal:
        return (float(t), True)
    return (int(t), False)

def static_bool(node):
    if isinstance(node, ast.UnaryOperation):
        return node.op == u'!'
    if isinstance(node, ast.BinaryOperation):
        return node.op in BOOLEAN_WRAPPED
    if isinstance(node, ast.CompareOperation):
        return node.op != u'in'
    return False

def _is_one(tok):
    try:
        v, _ = _number(tok)
    except Exception:
        return False
    return v == 1

class Emitter(object):
    def __init__(self, pool):
        self.p = pool
        self.open_ns_set = None
        self.public_ns = None
        self._helpers = {}

    def helper(self, name):
        mn = self._helpers.get(name)
        if mn is None:
            mn = self._helpers[name] = self.p.multi(name, self.open_ns_set)
        return mn

    def boolean(self):
        mn = self._helpers.get(u'#Boolean')
        if mn is None:
            mn = self._helpers[u'#Boolean'] = self.p.qname(self.public_ns,
                                                           'Boolean')
        return mn

    def push_number(self, asm, tok, negate=False):
        v, decimal = _number(tok)
        if negate:
            v = -v
        integral = (v == int(v)) if isinstance(v, float) else True
        if integral and not ((decimal or negate) and v == 0):
            iv = int(v)
            if -2147483648 <= iv <= 2147483647:
                if -128 <= iv <= 127:
                    asm.push(bytearray([PUSHBYTE, iv & 0xFF]))
                elif -32768 <= iv <= 32767:
                    asm.push(bytearray([PUSHSHORT]) + u30_bytes(iv & 0xFFFFFFFF))
                else:
                    asm.push(bytearray([PUSHINT]) + u30_bytes(self.p.i32(iv)))
                return

        dv = -0.0 if (negate and not decimal and v == 0) else float(v)
        asm.op_u30(PUSHDOUBLE, self.p.dbl(dv), +1)

    def value(self, asm, node, ctx=CTX_VALUE):
        cls = node.__class__

        if cls is ast.NullNode:
            asm.op(PUSHNULL, +1)
        elif cls is ast.TrueNode:
            asm.op(PUSHTRUE, +1)
        elif cls is ast.FalseNode:
            asm.op(PUSHFALSE, +1)
        elif cls is ast.StringLiteral:
            asm.op_u30(PUSHSTRING, self.p.st(_unquote(node.value)), +1)
        elif cls is ast.NumberLiteral:
            self.push_number(asm, node.value)
        elif cls is ast.Name:
            asm.op(GETLOCAL1, +1)
            asm.op_u30(GETPROPERTY, self.p.multi(node.value, self.open_ns_set))
        elif cls is ast.DotProperty or cls is ast.BracketProperty:
            self._property(asm, node)
        elif cls is ast.CallExpression:
            asm.op(GETLOCAL1, +1)
            self.value(asm, node.expression)
            for a in node.arguments:
                self.value(asm, a)
            asm.op_u30_u30(CALLPROPERTY, self.helper(u'callFunctionSecure'),
                           1 + len(node.arguments),
                           -(1 + len(node.arguments)))
        elif cls is ast.ObjectLiteral:
            for prop in node.properties:
                if isinstance(prop.name, ast.NumberLiteral):
                    self.push_number(asm, prop.name.value)
                    asm.op(CONVERT_S)
                else:
                    asm.op_u30(PUSHSTRING,
                               self.p.st(self._key_text(prop.name)), +1)
                self.value(asm, prop.value)
            asm.op_u30(NEWOBJECT, len(node.properties),
                       -2 * len(node.properties) + 1)
        elif cls is ast.ArrayLiteral:
            for el in node.elements:
                self.value(asm, el)
            asm.op_u30(NEWARRAY, len(node.elements), -len(node.elements) + 1)
        elif cls is ast.UnaryOperation:
            self._unary(asm, node)
        elif cls is ast.BinaryOperation:
            self._binary(asm, node, ctx)
        elif cls is ast.CompareOperation:
            self._compare(asm, node)
        elif cls is ast.Conditional:
            self._conditional(asm, node)
        else:
            raise Exception('no bytecode for %s' % cls.__name__)

    def _key_text(self, name):
        if isinstance(name, ast.StringLiteral):
            return _unquote(name.value)
        return name.value

    def _property(self, asm, node):
        args = []
        cur = node
        while isinstance(cur, ast.PropertyAccess):
            args.append(cur)
            cur = cur.object
        args.reverse()
        asm.op(GETLOCAL1, +1)

        if isinstance(cur, ast.Name):
            asm.op_u30(PUSHSTRING, self.p.st(cur.value), +1)
        else:
            self.value(asm, cur)
        n = 1
        for link in args:
            if isinstance(link, ast.DotProperty):
                asm.op_u30(PUSHSTRING, self.p.st(link.key), +1)
            else:
                self.value(asm, link.key)
            n += 1
        asm.op_u30_u30(CALLPROPERTY, self.helper(u'getPropertySecure'), n, -n)

    def _unary(self, asm, node):
        op = node.op
        inner = node.expression
        if op in (u'-', u'+') and isinstance(inner, ast.NumberLiteral):
            self.push_number(asm, inner.value, negate=(op == u'-'))
            return

        self.value(asm, inner, CTX_NOT if op == u'!' else CTX_VALUE)
        if op == u'+':
            return
        code = UNOP.get(op)
        if code is None:
            raise Exception('unsupported unary %r' % (op,))
        asm.op(code)

    def _binary(self, asm, node, ctx=CTX_VALUE):
        op = node.op
        if op == u'&&':
            self._boolean_call(asm, self._short_circuit_and, node, IFFALSE)
        elif op == u'||':
            if ctx == CTX_TERNARY:
                to_bool = True
            elif ctx == CTX_NOT:
                to_bool = static_bool(node.left) == static_bool(node.right)
            else:
                to_bool = False
            if self._or_chain(asm, node, ctx):
                return
            self._short_circuit(asm, node, IFTRUE, to_bool)
        elif op in BOOLEAN_WRAPPED:
            self._boolean_call(asm, self._plain_binary, node, None)
        else:
            self._plain_binary(asm, node, None)

    def _or_chain(self, asm, node, ctx):
        ops = []
        cur = node
        while isinstance(cur, ast.BinaryOperation) and cur.op == u'||':
            ops.append(cur.right)
            cur = cur.left
        ops.append(cur)
        ops.reverse()

        if ctx in UssOrTable.COLLAPSED:
            kinds = ''.join('T' if static_bool(o) else 'P' for o in ops)
        else:
            kinds = ''.join(
                'N' if (isinstance(o, ast.UnaryOperation) and o.op == u'!')
                else 'B' if static_bool(o) else 'P' for o in ops)
        pairs = UssOrTable.lookup(ctx, kinds)
        if pairs is None:
            return False
        sub = CTX_TERNARY if ctx in (CTX_TERNARY, CTX_NOT) else CTX_VALUE

        def coerce(spec):
            for c in spec:
                asm.op(CONVERT_B if c == 'b' else COERCE_A)

        self.value(asm, ops[0], sub)
        for i in range(len(ops) - 1):
            cl, cr = pairs[i]
            coerce(cl)
            asm.op(DUP, +1)
            j = asm.branch(IFTRUE)
            depth = asm.depth
            asm.op(POP, -1)
            right = ops[i + 1]
            self.value(asm, right, sub)
            if (isinstance(right, ast.BinaryOperation) and right.op == u'||'
                    and cr):
                cr = cr[1:]
            coerce(cr)
            asm.here(j, depth)
        return True

    LITERALS = (ast.StringLiteral, ast.NumberLiteral, ast.NullNode,
                ast.TrueNode, ast.FalseNode)

    def _plain_binary(self, asm, node, _unused):
        if node.op == u',':
            if not isinstance(node.left, self.LITERALS):
                self.value(asm, node.left)
                asm.op(POP, -1)
            self.value(asm, node.right)
            return

        if (node.op == u'-' and isinstance(node.right, ast.NumberLiteral)
                and _is_one(node.right.value)):
            self.value(asm, node.left)
            asm.reserve(1)
            asm.op(DECREMENT)
            return
        self.value(asm, node.left)
        self.value(asm, node.right)
        code = BINOP.get(node.op)
        if code is not None:
            asm.op(code, -1)
            return
        code = NEGATED.get(node.op)
        if code is None:
            raise Exception('unsupported binary %r' % (node.op,))
        asm.op(code, -1)
        asm.op(NOT)

    def _short_circuit_and(self, asm, node, _unused):
        self._short_circuit(asm, node, IFFALSE, False, CTX_AND)

    def _short_circuit(self, asm, node, brancher, to_bool=False, sub=None):
        if sub is None:
            sub = CTX_TERNARY if to_bool else CTX_VALUE
        self.value(asm, node.left, sub)
        asm.coerce_once(to_bool)
        asm.op(DUP, +1)
        j = asm.branch(brancher)
        depth = asm.depth
        asm.op(POP, -1)
        self.value(asm, node.right, sub)
        asm.coerce_once(to_bool)
        asm.here(j, depth)

    def _boolean_call(self, asm, inner, node, arg):
        asm.op_u30(FINDPROPSTRICT, self.boolean(), +1)
        inner(asm, node, arg)
        asm.op_u30_u30(CALLPROPERTY, self.boolean(), 1, -1)

    def _compare(self, asm, node):
        if node.op == u'in':
            asm.op(GETLOCAL1, +1)
            self.value(asm, node.left)
            self.value(asm, node.right)
            asm.op_u30_u30(CALLPROPERTY, self.helper(u'isInSecure'), 2, -2)
            return
        self._boolean_call(asm, self._plain_binary, node, None)

    def _conditional(self, asm, node):
        cond = node.condition
        brancher = IFFALSE
        if (isinstance(cond, ast.UnaryOperation) and cond.op == u'!'):
            cond = cond.expression
            brancher = IFTRUE

        const = (True if isinstance(cond, ast.TrueNode)
                 else False if isinstance(cond, ast.FalseNode) else None)
        if const is not None and (const is (brancher == IFTRUE)):
            j1 = asm.branch(JUMP)
        else:
            self.value(asm, cond, CTX_TERNARY)
            j1 = asm.branch(brancher)
        depth = asm.depth
        self.value(asm, node.then_expression)
        asm.coerce_once()
        j2 = asm.branch(JUMP)
        asm.here(j1, depth)
        self.value(asm, node.else_expression)
        asm.coerce_once()
        asm.here(j2, depth + 1)
