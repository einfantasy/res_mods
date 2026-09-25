# coding=utf-8

import struct

class Reader(object):
    def __init__(self, buf, pos=0):
        self.b = bytearray(buf)
        self.p = pos

    def u8(self):
        v = self.b[self.p]
        self.p += 1
        return v

    def u16(self):
        v = self.b[self.p] | (self.b[self.p + 1] << 8)
        self.p += 2
        return v

    def u32raw(self):
        v = struct.unpack_from('<I', self.b, self.p)[0]
        self.p += 4
        return v

    def var(self):
        v = 0
        shift = 0
        while True:
            c = self.b[self.p]
            self.p += 1
            v |= (c & 0x7F) << shift
            shift += 7
            if not (c & 0x80) or shift >= 35:
                break
        return v & 0xFFFFFFFF

    u30 = var
    u32 = var
    s32 = var

    def d64(self):
        v = struct.unpack_from('<d', self.b, self.p)[0]
        self.p += 8
        return v

    def raw(self, n):
        v = self.b[self.p:self.p + n]
        self.p += n
        return v

    def string(self):
        return self.raw(self.var())

    def eof(self):
        return self.p >= len(self.b)

class Writer(object):
    def __init__(self):
        self.b = bytearray()

    def u8(self, v):
        self.b.append(v & 0xFF)

    def u16(self, v):
        self.b.append(v & 0xFF)
        self.b.append((v >> 8) & 0xFF)

    def u32raw(self, v):
        self.b.extend(struct.pack('<I', v & 0xFFFFFFFF))

    def var(self, v):
        v &= 0xFFFFFFFF
        while True:
            c = v & 0x7F
            v >>= 7
            if v:
                self.b.append(c | 0x80)
            else:
                self.b.append(c)
                return

    u30 = var
    u32 = var
    s32 = var

    def d64(self, v):
        self.b.extend(struct.pack('<d', v))

    def raw(self, v):
        self.b.extend(v)

    def string(self, v):
        self.var(len(v))
        self.b.extend(v)

def _read_multiname(r):
    k = r.u8()
    m = {'kind': k}
    if k in (0x07, 0x0D):
        m['ns'] = r.u30()
        m['name'] = r.u30()
    elif k in (0x0F, 0x10):
        m['name'] = r.u30()
    elif k in (0x11, 0x12):
        pass
    elif k in (0x09, 0x0E):
        m['name'] = r.u30()
        m['ns_set'] = r.u30()
    elif k in (0x1B, 0x1C):
        m['ns_set'] = r.u30()
    elif k == 0x1D:
        m['name'] = r.u30()
        m['params'] = [r.u30() for _ in range(r.u30())]
    else:
        raise Exception('unknown multiname kind 0x%02X at %d' % (k, r.p - 1))
    return m

def _write_multiname(w, m):
    k = m['kind']
    w.u8(k)
    if k in (0x07, 0x0D):
        w.u30(m['ns'])
        w.u30(m['name'])
    elif k in (0x0F, 0x10):
        w.u30(m['name'])
    elif k in (0x11, 0x12):
        pass
    elif k in (0x09, 0x0E):
        w.u30(m['name'])
        w.u30(m['ns_set'])
    elif k in (0x1B, 0x1C):
        w.u30(m['ns_set'])
    elif k == 0x1D:
        w.u30(m['name'])
        w.u30(len(m['params']))
        for p in m['params']:
            w.u30(p)
    else:
        raise Exception('unknown multiname kind 0x%02X' % k)

def _read_cpool(r):
    cp = {}
    n = r.u30()
    cp['ints'] = [r.s32() for _ in range(max(n - 1, 0))]
    n = r.u30()
    cp['uints'] = [r.u32() for _ in range(max(n - 1, 0))]
    n = r.u30()
    cp['doubles'] = [r.d64() for _ in range(max(n - 1, 0))]
    n = r.u30()
    cp['strings'] = [r.string() for _ in range(max(n - 1, 0))]
    n = r.u30()
    cp['namespaces'] = [{'kind': r.u8(), 'name': r.u30()} for _ in range(max(n - 1, 0))]
    n = r.u30()
    cp['ns_sets'] = [[r.u30() for _ in range(r.u30())] for _ in range(max(n - 1, 0))]
    n = r.u30()
    cp['multinames'] = [_read_multiname(r) for _ in range(max(n - 1, 0))]
    return cp

def _write_cpool(w, cp):
    def count(seq):
        return len(seq) + 1 if seq else 0

    w.u30(count(cp['ints']))
    for v in cp['ints']:
        w.s32(v)
    w.u30(count(cp['uints']))
    for v in cp['uints']:
        w.u32(v)
    w.u30(count(cp['doubles']))
    for v in cp['doubles']:
        w.d64(v)
    w.u30(count(cp['strings']))
    for v in cp['strings']:
        w.string(v)
    w.u30(count(cp['namespaces']))
    for ns in cp['namespaces']:
        w.u8(ns['kind'])
        w.u30(ns['name'])
    w.u30(count(cp['ns_sets']))
    for s in cp['ns_sets']:
        w.u30(len(s))
        for x in s:
            w.u30(x)
    w.u30(count(cp['multinames']))
    for m in cp['multinames']:
        _write_multiname(w, m)

TRAIT_SLOT, TRAIT_METHOD, TRAIT_GETTER, TRAIT_SETTER = 0, 1, 2, 3
TRAIT_CLASS, TRAIT_FUNCTION, TRAIT_CONST = 4, 5, 6
ATTR_METADATA = 0x04

def _read_trait(r):
    t = {'name': r.u30()}
    kb = r.u8()
    t['kind_byte'] = kb
    kind = kb & 0x0F
    if kind in (TRAIT_SLOT, TRAIT_CONST):
        t['slot_id'] = r.u30()
        t['type_name'] = r.u30()
        t['vindex'] = r.u30()
        if t['vindex']:
            t['vkind'] = r.u8()
    elif kind == TRAIT_CLASS:
        t['slot_id'] = r.u30()
        t['classi'] = r.u30()
    elif kind == TRAIT_FUNCTION:
        t['slot_id'] = r.u30()
        t['function'] = r.u30()
    elif kind in (TRAIT_METHOD, TRAIT_GETTER, TRAIT_SETTER):
        t['disp_id'] = r.u30()
        t['method'] = r.u30()
    else:
        raise Exception('unknown trait kind %d at %d' % (kind, r.p - 1))
    if (kb >> 4) & ATTR_METADATA:
        t['metadata'] = [r.u30() for _ in range(r.u30())]
    return t

def _write_trait(w, t):
    w.u30(t['name'])
    kb = t['kind_byte']
    w.u8(kb)
    kind = kb & 0x0F
    if kind in (TRAIT_SLOT, TRAIT_CONST):
        w.u30(t['slot_id'])
        w.u30(t['type_name'])
        w.u30(t['vindex'])
        if t['vindex']:
            w.u8(t['vkind'])
    elif kind == TRAIT_CLASS:
        w.u30(t['slot_id'])
        w.u30(t['classi'])
    elif kind == TRAIT_FUNCTION:
        w.u30(t['slot_id'])
        w.u30(t['function'])
    else:
        w.u30(t['disp_id'])
        w.u30(t['method'])
    if (kb >> 4) & ATTR_METADATA:
        w.u30(len(t['metadata']))
        for m in t['metadata']:
            w.u30(m)

def _read_traits(r):
    return [_read_trait(r) for _ in range(r.u30())]

def _write_traits(w, ts):
    w.u30(len(ts))
    for t in ts:
        _write_trait(w, t)

HAS_OPTIONAL = 0x08
HAS_PARAM_NAMES = 0x80
CLASS_PROTECTEDNS = 0x08

def _read_method(r):
    m = {}
    pc = r.u30()
    m['return_type'] = r.u30()
    m['param_types'] = [r.u30() for _ in range(pc)]
    m['name'] = r.u30()
    f = r.u8()
    m['flags'] = f
    if f & HAS_OPTIONAL:
        m['options'] = [{'val': r.u30(), 'kind': r.u8()} for _ in range(r.u30())]
    if f & HAS_PARAM_NAMES:
        m['param_names'] = [r.u30() for _ in range(pc)]
    return m

def _write_method(w, m):
    w.u30(len(m['param_types']))
    w.u30(m['return_type'])
    for t in m['param_types']:
        w.u30(t)
    w.u30(m['name'])
    f = m['flags']
    w.u8(f)
    if f & HAS_OPTIONAL:
        w.u30(len(m['options']))
        for o in m['options']:
            w.u30(o['val'])
            w.u8(o['kind'])
    if f & HAS_PARAM_NAMES:
        for n in m['param_names']:
            w.u30(n)

def _read_instance(r):
    i = {'name': r.u30(), 'super_name': r.u30()}
    f = r.u8()
    i['flags'] = f
    if f & CLASS_PROTECTEDNS:
        i['protected_ns'] = r.u30()
    i['interfaces'] = [r.u30() for _ in range(r.u30())]
    i['iinit'] = r.u30()
    i['traits'] = _read_traits(r)
    return i

def _write_instance(w, i):
    w.u30(i['name'])
    w.u30(i['super_name'])
    f = i['flags']
    w.u8(f)
    if f & CLASS_PROTECTEDNS:
        w.u30(i['protected_ns'])
    w.u30(len(i['interfaces']))
    for x in i['interfaces']:
        w.u30(x)
    w.u30(i['iinit'])
    _write_traits(w, i['traits'])

def _read_body(r):
    b = {
        'method': r.u30(),
        'max_stack': r.u30(),
        'local_count': r.u30(),
        'init_scope_depth': r.u30(),
        'max_scope_depth': r.u30(),
    }
    b['code'] = r.raw(r.u30())
    b['exceptions'] = [{
        'from': r.u30(), 'to': r.u30(), 'target': r.u30(),
        'exc_type': r.u30(), 'var_name': r.u30(),
    } for _ in range(r.u30())]
    b['traits'] = _read_traits(r)
    return b

def _write_body(w, b):
    w.u30(b['method'])
    w.u30(b['max_stack'])
    w.u30(b['local_count'])
    w.u30(b['init_scope_depth'])
    w.u30(b['max_scope_depth'])
    w.u30(len(b['code']))
    w.raw(b['code'])
    w.u30(len(b['exceptions']))
    for e in b['exceptions']:
        w.u30(e['from'])
        w.u30(e['to'])
        w.u30(e['target'])
        w.u30(e['exc_type'])
        w.u30(e['var_name'])
    _write_traits(w, b['traits'])

def parse_abc(buf):
    r = Reader(buf)
    a = {'minor': r.u16(), 'major': r.u16()}
    a['cpool'] = _read_cpool(r)
    a['methods'] = [_read_method(r) for _ in range(r.u30())]
    a['metadata'] = [{
        'name': r.u30(),
        'items': [{'key': r.u30(), 'value': r.u30()} for _ in range(r.u30())],
    } for _ in range(r.u30())]
    n = r.u30()
    a['instances'] = [_read_instance(r) for _ in range(n)]
    a['classes'] = [{'cinit': r.u30(), 'traits': _read_traits(r)} for _ in range(n)]
    a['scripts'] = [{'init': r.u30(), 'traits': _read_traits(r)} for _ in range(r.u30())]
    a['bodies'] = [_read_body(r) for _ in range(r.u30())]
    a['tail'] = r.raw(len(r.b) - r.p)
    return a

def serialize_abc(a):
    w = Writer()
    w.u16(a['minor'])
    w.u16(a['major'])
    _write_cpool(w, a['cpool'])
    w.u30(len(a['methods']))
    for m in a['methods']:
        _write_method(w, m)
    w.u30(len(a['metadata']))
    for md in a['metadata']:
        w.u30(md['name'])
        w.u30(len(md['items']))
        for it in md['items']:
            w.u30(it['key'])
            w.u30(it['value'])
    w.u30(len(a['instances']))
    for i in a['instances']:
        _write_instance(w, i)
    for c in a['classes']:
        w.u30(c['cinit'])
        _write_traits(w, c['traits'])
    w.u30(len(a['scripts']))
    for s in a['scripts']:
        w.u30(s['init'])
        _write_traits(w, s['traits'])
    w.u30(len(a['bodies']))
    for b in a['bodies']:
        _write_body(w, b)
    w.raw(a['tail'])
    return w.b

DOABC, DOABC2 = 72, 82

def split_swf(raw):
    raw = bytearray(raw)
    return raw[:3], raw[3], struct.unpack_from('<I', raw, 4)[0], raw[8:]

def parse_body(body):
    r = Reader(body)
    nbits = r.b[0] >> 3
    d = {
        'rect': r.raw((5 + 4 * nbits + 7) // 8),
        'framerate': r.u16(),
        'framecount': r.u16(),
        'tags': [],
    }
    while not r.eof():
        rh = r.u16()
        code, ln = rh >> 6, rh & 0x3F

        long_form = (ln == 0x3F)
        if long_form:
            ln = r.u32raw()
        d['tags'].append({'code': code, 'long': long_form, 'data': r.raw(ln)})
        if code == 0:
            break
    d['trailer'] = r.raw(len(r.b) - r.p)
    return d

def serialize_body(d):
    w = Writer()
    w.raw(d['rect'])
    w.u16(d['framerate'])
    w.u16(d['framecount'])
    for t in d['tags']:
        n = len(t['data'])
        if t['long'] or n >= 0x3F:
            w.u16((t['code'] << 6) | 0x3F)
            w.u32raw(n)
        else:
            w.u16((t['code'] << 6) | n)
        w.raw(t['data'])
    w.raw(d['trailer'])
    return w.b

def abc_tags(d):
    out = []
    for idx, t in enumerate(d['tags']):
        if t['code'] not in (DOABC, DOABC2):
            continue
        p = 4
        while t['data'][p] != 0:
            p += 1
        out.append((idx, t['data'][:p + 1], t['data'][p + 1:]))
    return out
