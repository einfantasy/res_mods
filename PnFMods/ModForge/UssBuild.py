# coding=utf-8

import UssAbc
from UssAbc import (Pool, Asm, Emitter,
                    NS_PACKAGE, NS_PACKAGE_INTERNAL, NS_PRIVATE,
                    NS_PROTECTED, NS_PLAIN, NS_STATIC_PROTECTED, BUILTIN_NS,
                    GETLOCAL0, GETLOCAL1, GETLOCAL2, GETLOCAL3, SETLOCAL3,
                    PUSHSCOPE, POPSCOPE, GETSCOPEOBJECT, RETURNVOID,
                    RETURNVALUE, CONSTRUCTSUPER, GETLEX, FINDPROPSTRICT,
                    GETPROPERTY, SETPROPERTY, INITPROPERTY, CALLPROPVOID,
                    NEWCLASS, APPLYTYPE, CONSTRUCT, PUSHNULL, PUSHSTRING,
                    PUSHBYTE, COERCE_S, DUP)

ABC_MAJOR, ABC_MINOR = 46, 16

def _method(ret, params):
    return {'param_types': list(params), 'return_type': ret, 'name': 0,
            'flags': 0x00}

def _body(mi, asm, local_count, init_scope, max_scope, max_stack=None):
    return {'method': mi,
            'max_stack': asm.max if max_stack is None else max_stack,
            'local_count': local_count,
            'init_scope_depth': init_scope,
            'max_scope_depth': max_scope,
            'code': asm.code,
            'exceptions': [],
            'traits': []}

def _trivial(depth):
    a = Asm()
    a.op(GETLOCAL0, +1)
    a.op(PUSHSCOPE, -1)
    a.op(RETURNVOID)
    return a

def _ctor():
    a = Asm()
    a.op(GETLOCAL0, +1)
    a.op(PUSHSCOPE, -1)
    a.op(GETLOCAL0, +1)
    a.op_u30(CONSTRUCTSUPER, 0, -1)
    a.op(RETURNVOID)
    return a

def build_abc(entries):
    p = Pool()
    em = Emitter(p)
    n = len(entries)

    ns_public = p.ns(NS_PACKAGE, '')
    mn_void = p.qname(ns_public, 'void')
    ns_lue = p.ns(NS_PACKAGE, 'lesta.unbound.expression')
    mn_ed = p.qname(ns_lue, 'ExpressionsDict')
    mn_object = p.qname(ns_public, 'Object')
    mn_main = p.qname(ns_public, 'main')
    ns_fd = p.ns(NS_PACKAGE, 'flash.display')
    mn_sprite = p.qname(ns_fd, 'Sprite')
    mn_doinit = p.qname(ns_public, 'doInitialize')
    ns_main_int = p.ns(NS_PACKAGE_INTERNAL, 'main')
    ns_fu = p.ns(NS_PACKAGE, 'flash.utils')
    mn_dict = p.qname(ns_fu, 'Dictionary')
    ns_ed_int = p.ns(NS_PACKAGE_INTERNAL,
                     'lesta.unbound.expression:ExpressionsDict')
    mn_uss = p.qname(ns_public, 'USSExpressions')
    ns_uss_int = p.ns(NS_PACKAGE_INTERNAL, 'USSExpressions')
    mn_dis = p.qname(ns_public, 'doInitializeStatic')
    mn_e = [p.qname(ns_public, 'e%d' % (i + 1)) for i in range(n)]

    methods = [
        _method(0, []),
        _method(mn_void, []),
        _method(mn_void, [mn_ed, mn_ed]),
        _method(0, []),
        _method(0, []),
        _method(0, []),
        _method(0, []),
        _method(0, []),
        _method(mn_void, [mn_ed, mn_ed]),
    ]
    for _ in range(n):
        methods.append(_method(0, [mn_object]))
    methods.append(_method(0, []))
    methods.append(_method(0, []))
    mi_uss_init = 9 + n
    mi_script2 = 10 + n

    bodies = []
    bodies.append(_body(0, _trivial(8), 1, 8, 9))
    bodies.append(_body(1, _ctor(), 1, 9, 10))

    a = Asm()
    a.op(GETLOCAL0, +1)
    a.op(PUSHSCOPE, -1)
    a.op_u30(GETLEX, mn_uss, +1)
    a.op(GETLOCAL1, +1)
    a.op(GETLOCAL2, +1)
    a.op_u30_u30(CALLPROPVOID, mn_dis, 2, -3)
    a.op(RETURNVOID)
    bodies.append(_body(2, a, 3, 9, 10))

    ns_fe = p.ns(NS_PACKAGE, 'flash.events')
    mn_evd = p.qname(ns_fe, 'EventDispatcher')
    mn_do = p.qname(ns_fd, 'DisplayObject')
    mn_io = p.qname(ns_fd, 'InteractiveObject')
    mn_doc = p.qname(ns_fd, 'DisplayObjectContainer')
    a = Asm()
    a.op(GETLOCAL0, +1)
    a.op(PUSHSCOPE, -1)
    a.op_u8(GETSCOPEOBJECT, 0, +1)
    for mn in (mn_object, mn_evd, mn_do, mn_io, mn_doc, mn_sprite):
        a.op_u30(GETLEX, mn, +1)
        a.op(PUSHSCOPE, -1)
    a.op_u30(GETLEX, mn_sprite, +1)
    a.op_u30(NEWCLASS, 0)
    for _ in range(6):
        a.op(POPSCOPE)
    a.op_u30(INITPROPERTY, mn_main, -2)
    a.op(RETURNVOID)
    bodies.append(_body(3, a, 1, 1, 8))

    bodies.append(_body(4, _trivial(4), 1, 4, 5))
    bodies.append(_body(5, _ctor(), 1, 5, 6))

    nss_lue = p.nss([ns_lue])
    mn_ed_multi = p.multi('ExpressionsDict', nss_lue)
    a = Asm()
    a.op(GETLOCAL0, +1)
    a.op(PUSHSCOPE, -1)
    a.op_u30(FINDPROPSTRICT, mn_ed_multi, +1)
    for mn in (mn_object, mn_dict):
        a.op_u30(GETLEX, mn, +1)
        a.op(PUSHSCOPE, -1)
    a.op_u30(GETLEX, mn_dict, +1)
    a.op_u30(NEWCLASS, 1)
    a.op(POPSCOPE)
    a.op(POPSCOPE)
    a.op_u30(INITPROPERTY, mn_ed, -2)
    a.op(RETURNVOID)
    bodies.append(_body(6, a, 1, 1, 4))

    bodies.append(_body(7, _trivial(3), 1, 3, 4))

    a = Asm()
    a.op(GETLOCAL0, +1)
    a.op(PUSHSCOPE, -1)
    a.op(PUSHNULL, +1)
    a.op(COERCE_S)
    a.op(SETLOCAL3, -1)

    mn_l_open = None
    mn_vec_only = None
    mn_vec_open = None
    mn_string = None
    mn_l_public = None

    for i, (key, node, props) in enumerate(entries):
        a.op_u30(PUSHSTRING, p.st(key), +1)
        a.op(SETLOCAL3, -1)
        a.op(GETLOCAL1, +1)
        a.op(GETLOCAL3, +1)
        a.op_u30(GETLEX, mn_e[i], +1)
        if mn_l_open is None:
            ns_priv_a = p.ns_raw(NS_PRIVATE, 0)
            ns_priv_b = p.ns_raw(NS_PRIVATE, 0)
            ns_prot = p.ns(NS_PROTECTED, '')
            ns_builtin = p.ns(NS_PLAIN, BUILTIN_NS)
            ns_static_prot = p.ns(NS_STATIC_PROTECTED, 'USSExpressions')
            open_list = [ns_priv_a, ns_public, ns_priv_b, ns_prot, ns_builtin,
                         ns_uss_int, ns_static_prot]
            em.open_ns_set = p.nss(open_list)
            em.public_ns = ns_public
            mn_l_open = p.multil(em.open_ns_set)
        a.op_u30(SETPROPERTY, mn_l_open, -3)

        a.op(GETLOCAL2, +1)
        a.op(GETLOCAL3, +1)
        if props:
            if mn_vec_only is None:
                p.st('Vector')
                ns_vec = p.ns(NS_PACKAGE, '__AS3__.vec')
                mn_vec_only = p.multi('Vector', p.nss([ns_vec]))
                mn_vec_open = p.multi(
                    'Vector', p.nss(list(open_list) + [ns_vec]))
                mn_string = p.qname(ns_public, 'String')
                mn_l_public = p.multil(p.nss([ns_public]))
            a.op_u30(FINDPROPSTRICT, mn_vec_only, +1)
            a.op_u30(GETPROPERTY, mn_vec_open)
            a.op_u30(GETLEX, mn_string, +1)
            a.op_u30(APPLYTYPE, 1, -1)
            em.push_number(a, u'%d' % len(props))
            a.op_u30(CONSTRUCT, 1, -1)
            for j, prop in enumerate(props):
                a.op(DUP, +1)
                em.push_number(a, u'%d' % j)
                a.op_u30(PUSHSTRING, p.st(prop), +1)
                a.op_u30(SETPROPERTY, mn_l_public, -3)
        else:
            a.op(PUSHNULL, +1)
        a.op_u30(SETPROPERTY, mn_l_open, -3)
    a.op(RETURNVOID)
    bodies.append(_body(8, a, 4, 3, 4))

    if em.open_ns_set is None:
        raise Exception('no expressions: nothing opens the namespace set')
    for i, (key, node, props) in enumerate(entries):
        a = Asm()
        a.op(GETLOCAL0, +1)
        a.op(PUSHSCOPE, -1)
        if node is None:
            a.op(PUSHNULL, +1)
        else:
            em.value(a, node)
        a.op(RETURNVALUE, -1)
        bodies.append(_body(9 + i, a, 2, 3, 4))

    bodies.append(_body(mi_uss_init, _ctor(), 1, 4, 5))

    mn_uss_multi = p.multi('USSExpressions', p.nss([ns_public]))
    a = Asm()
    a.op(GETLOCAL0, +1)
    a.op(PUSHSCOPE, -1)
    a.op_u30(FINDPROPSTRICT, mn_uss_multi, +1)
    a.op_u30(GETLEX, mn_object, +1)
    a.op(PUSHSCOPE, -1)
    a.op_u30(GETLEX, mn_object, +1)
    a.op_u30(NEWCLASS, 2)
    a.op(POPSCOPE)
    a.op_u30(INITPROPERTY, mn_uss, -2)
    a.op(RETURNVOID)
    bodies.append(_body(mi_script2, a, 1, 1, 3))

    instances = [
        {'name': mn_main, 'super_name': mn_sprite, 'flags': 0x09,
         'protected_ns': ns_main_int, 'interfaces': [], 'iinit': 1,
         'traits': [{'name': mn_doinit, 'kind_byte': 0x01, 'disp_id': 0,
                     'method': 2}]},
        {'name': mn_ed, 'super_name': mn_dict, 'flags': 0x09,
         'protected_ns': ns_ed_int, 'interfaces': [], 'iinit': 5,
         'traits': []},
        {'name': mn_uss, 'super_name': mn_object, 'flags': 0x09,
         'protected_ns': ns_uss_int, 'interfaces': [], 'iinit': mi_uss_init,
         'traits': []},
    ]
    class2_traits = [{'name': mn_dis, 'kind_byte': 0x11, 'disp_id': 3,
                      'method': 8}]
    for i in range(n):
        class2_traits.append({'name': mn_e[i], 'kind_byte': 0x11,
                              'disp_id': 4 + i, 'method': 9 + i})
    classes = [
        {'cinit': 0, 'traits': []},
        {'cinit': 4, 'traits': []},
        {'cinit': 7, 'traits': class2_traits},
    ]
    scripts = [
        {'init': 3, 'traits': [{'name': mn_main, 'kind_byte': 0x04,
                                'slot_id': 1, 'classi': 0}]},
        {'init': 6, 'traits': [{'name': mn_ed, 'kind_byte': 0x04,
                                'slot_id': 0, 'classi': 1}]},
        {'init': mi_script2, 'traits': [{'name': mn_uss, 'kind_byte': 0x04,
                                         'slot_id': 0, 'classi': 2}]},
    ]

    return {
        'major': ABC_MAJOR, 'minor': ABC_MINOR,
        'cpool': {'ints': p.ints, 'uints': p.uints, 'doubles': p.doubles,
                  'strings': p.strings, 'namespaces': p.namespaces,
                  'ns_sets': p.ns_sets, 'multinames': p.multinames},
        'methods': methods,
        'metadata': [],
        'instances': instances,
        'classes': classes,
        'scripts': scripts,
        'bodies': bodies,
        'tail': b'',
    }
