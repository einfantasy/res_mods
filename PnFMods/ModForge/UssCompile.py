# coding=utf-8

import Paths
from Codec import _u2

_CENSORED = ('ExternalInterface', 'GameDelegate', 'GameInfoHolder',
             'InputDelegate', 'gameInfoHolder', 'getDefinitionByName')

class CompileError(Exception):
    pass

def _modules():
    import AbcFmt
    import UssBuild
    import UssSwf
    import UssTrans
    import UssXml
    return AbcFmt, UssBuild, UssSwf, UssTrans, UssXml

def censoredStrings(poolStrings):
    hits = []
    for s in poolStrings:
        if not s:
            continue
        for entry in _CENSORED:
            if entry[:len(s)] == s:
                hits.append(s)
                break
    return hits

def _collect(absXmlPaths, contents):
    _abcFmt, _ussBuild, _ussSwf, ussTrans, ussXml = _modules()
    staged = contents or {}
    collector = ussTrans.Collector()
    for path in absXmlPaths:
        data = staged.get(path)
        if data is None:
            try:
                data = Paths.readBytes(path)
            except Exception as exc:
                raise CompileError('cannot read %s: %s' % (path, exc))
        try:
            root = _u2.fromstring(data)
        except Exception as exc:
            raise CompileError('%s is not valid XML: %s' % (path, exc))
        ussXml.scan_element(root, collector)
    return collector

def expressionKeys(absXmlPaths, contents=None):





    return set(_collect(absXmlPaths, contents).expressions)

def compileMarkup(absXmlPaths, contents=None, allowEmpty=False):







    abcFmt, ussBuild, ussSwf, ussTrans, ussXml = _modules()

    entries = _collect(absXmlPaths, contents).entries()
    if allowEmpty and not entries:
        return None, 0
    abc = ussBuild.build_abc(entries)


    hits = censoredStrings(abc['cpool']['strings'])
    if hits:
        raise CompileError(
            'the client blanks these strings in an unsigned SWF, so the '
            'compiled expressions would not behave as written: %s'
            % ', '.join(sorted(set(hits))))

    return ussSwf.build_swf(abcFmt.serialize_abc(abc)), len(entries)
