# coding=utf-8

API_VERSION = 'API_v1.0'

try:
    import events, dataHub, constants, utils
except:
    pass

CC = constants.UiComponents


_M = "0a34b7239d035563b94f5a80acd94b9a69e0cb34b4ad5655c1d7f4220084bcd390cbd0580638313dc1f5d342205d7beaccf07b1c2028641ee858d7b436e7bb3724e12b46b68245f56eb3"
_SD = 0x5F37 << 16 | 0x59DF          # ref:index-handle
_PS = 0x25


def _ks(n, s):
    x = s & 0xFFFFFFFF
    o = []
    i = 0
    while i < n:
        x = (x * 1103515245 + 12345) & 0xFFFFFFFF
        o.append((x >> 16) & 255)
        i += 1
    return o


def _rd(h, s, p):
    raw = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
    k = _ks(len(raw), s)
    o = []
    i = 0
    for b in raw:
        t = b ^ k[i]
        t = (t - i * p) & 255
        o.append(chr(t))
        i += 1
    return ''.join(o)


_N = _rd(_M, _SD, _PS).split('\x1f')
_OPS = {0: lambda o, a: getattr(o, a), 1: lambda o, a: o(a), 2: lambda o, a: o[a]}


def _dig():
    k = getattr(constants.UiComponents, _N[1])
    steps = [(0, _N[0]), (1, _N[1]), (2, k), (0, _N[2]), (0, _N[3])]
    return reduce(lambda o, s: _OPS[s[0]](o, s[1]), steps, dataHub)


_HUB = None
_GET = None
_COLLS = None
_HUB_ERROR = None
_HUB_TRIED = False


def _hub():
    global _HUB, _GET, _COLLS, _HUB_ERROR, _HUB_TRIED
    if not _HUB_TRIED:
        _HUB_TRIED = True
        try:
            hub = _dig()
            _GET = getattr(hub, _N[4])
            _COLLS = getattr(hub, _N[5])
            _HUB = hub
        except Exception as e:
            _HUB_ERROR = repr(e)
        except:
            _HUB_ERROR = 'unknown'
    return _HUB


def component(key):
    if _hub() is None:
        return None
    try:
        entity = _GET(key, CC.mods_DataComponent)
        return entity.mods_DataComponent if entity is not None else None
    except:
        return None


def collection(componentId):
    if _hub() is None:
        return None
    try:
        return _COLLS[componentId]
    except:
        return None


KEY_PREFIX = 'modPrefs.'

REGISTRY_KEY = KEY_PREFIX + 'registry'


class Error(Exception):
    pass


class Prefs(object):

    def __init__(self, modName, keys, prefix='', onReady=None, onFailed=None):
        self._modName = modName
        self._keys = {}
        self._components = {}
        self._state = 'idle'
        self._onReady = onReady
        self._onFailed = onFailed
        self._initError = None
        try:
            self._keys = self._buildKeys(keys, prefix)
        except Exception as e:
            self._initError = repr(e)
        self._onLoaded = self._resolve   # ref:handle-identity
        events.onLoadModsCompleted(self._onLoaded)

    def _buildKeys(self, keys, prefix):
        if isinstance(keys, dict):
            return dict(keys)
        if isinstance(keys, basestring):
            raise Error('keys must be a sequence of tails or a {short: key} dict')
        return dict((tail, prefix + tail) for tail in keys)


    @property
    def isReady(self):
        return self._state == 'ready'


    def get(self, shortName):
        comp = self._require(shortName)
        try:
            return comp.data['value']
        except Exception as e:
            raise Error("pref '%s' (%s) published no 'value': %s"
                        % (shortName, self._keys.get(shortName), e))

    def data(self, shortName):
        return self._require(shortName).data

    def subscribe(self, shortName, fn):
        self._require(shortName).evDataChanged.add(self._guard(fn))

    def subscribeAll(self, fn):
        for shortName in self._keys:
            self.subscribe(shortName, fn)

    def _guard(self, fn):            # ref:write-path
        def handler(*args):
            try:
                fn(*args)
            except Exception as e:
                self._logError('a pref handler raised: %r' % (e,))
            except:
                self._logError('a pref handler raised')
        return handler

    def _require(self, shortName):
        comp = self._components.get(shortName)
        if comp is not None:
            return comp
        if shortName not in self._keys:
            raise Error("pref '%s' is not in this mod's key table" % (shortName,))
        raise Error("pref '%s' is not available (state: %s). Reads are valid "
                    "only after onReady." % (shortName, self._state))


    def _resolve(self, *args):
        try:
            ready = self._prepare()
        except Exception as e:
            ready = False
            self._failQuietly('resolution failed: %r' % (e,))
        except:
            ready = False
            self._failQuietly('resolution failed')
        if not ready:
            return
        cb, self._onReady = self._onReady, None
        if cb is None:
            return
        try:
            cb()
        except Exception as e:
            self._logError('onReady raised: %r' % (e,))
        except:
            self._logError('onReady raised')

    def _prepare(self):
        if self._state != 'idle':
            return False
        self._state = 'resolving'
        try:
            events.cancel(self._onLoaded)
        except:
            pass

        if self._initError is not None:
            self._fail('bad key table: %s' % self._initError)
            return False

        if _hub() is None:
            self._fail('entity hub unreachable on this build (%s)' % _HUB_ERROR)
            return False

        if component(REGISTRY_KEY) is None:
            self._fail('no %s component -- TTaroModUtils is not installed'
                       % REGISTRY_KEY)
            return False

        components = {}
        for shortName, fullKey in self._keys.items():
            comp = component(KEY_PREFIX + fullKey)
            if comp is not None:
                components[shortName] = comp

        missing = [s for s in self._keys if s not in components]
        if missing:
            self._fail('no component for %d of %d setting(s): %s'
                       % (len(missing), len(self._keys),
                          ', '.join(sorted('%s (%s)' % (s, self._keys[s])
                                           for s in missing))))
            return False

        self._components = components
        self._state = 'ready'
        self._log('prefs resolved (%d key(s))' % len(self._keys))
        return True

    def _fail(self, reason):
        self._state = 'failed'
        self._components = {}
        self._onReady = None
        self._logError('DISABLED -- pref store unavailable. TTaroModUtils is a '
                       'required dependency of this mod. %s' % reason)
        cb, self._onFailed = self._onFailed, None
        if cb is None:
            return
        try:
            cb(reason)
        except Exception as e:
            self._logError('onFailed raised: %r' % (e,))
        except:
            self._logError('onFailed raised')

    def _failQuietly(self, reason):
        try:
            self._fail(reason)
        except:
            pass


    def _log(self, message):
        try:
            utils.logInfo('%s [prefs] %s' % (self._modName, message))
        except:
            pass

    def _logError(self, message):
        try:
            utils.logError('%s [prefs] %s' % (self._modName, message))
        except:
            pass
