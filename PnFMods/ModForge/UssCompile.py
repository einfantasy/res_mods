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
    """The keys these sources reference, by the same scan the compile uses.

    An expression key no loaded SWF carries is not a load error:
    `UbNativeExpression` stores null and `eval` calls it, so it is a #1006 on
    whatever screen first builds that block."""
    return set(_collect(absXmlPaths, contents).expressions)

def compileMarkup(absXmlPaths, contents=None, allowEmpty=False):
    """`contents` supplies a source that is staged but not yet on disk, so a
    payload and the SWF built from it can land in one commit.

    `allowEmpty` returns (None, 0) for sources that carry no expression at
    all, instead of raising. A mod naming a source it meant to compile wants
    the error; Forge's own definitions are simply not all expression-bearing
    -- and a registered SWF with no expressions stalls the boot."""
    abcFmt, ussBuild, ussSwf, ussTrans, ussXml = _modules()

    entries = _collect(absXmlPaths, contents).entries()
    if allowEmpty and not entries:
        return None, 0
    abc = ussBuild.build_abc(entries)

    # ref:uss-censor
    hits = censoredStrings(abc['cpool']['strings'])
    if hits:
        raise CompileError(
            'the client blanks these strings in an unsigned SWF, so the '
            'compiled expressions would not behave as written: %s'
            % ', '.join(sorted(set(hits))))

    return ussSwf.build_swf(abcFmt.serialize_abc(abc)), len(entries)
