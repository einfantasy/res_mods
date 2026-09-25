# coding=utf-8

from Codec import _u1

def installerDir():
    return utils.getModDir().replace('\\', '/').rstrip('/') + '/'

def resModsDir():
    return _u1.path.abspath(installerDir() + '../../').replace('\\', '/') + '/'

def gameBuildDir():
    return _u1.path.abspath(resModsDir() + '../').replace('\\', '/') + '/'

def gameBuildId():
    path = gameBuildDir().rstrip('/')
    return path.rsplit('/', 1)[-1]

def cacheDir():
    return installerDir() + '.installer_cache/'

def originalsDir():
    return cacheDir() + 'originals/'

def installedRegistryPath():
    return cacheDir() + 'installed.xml'

def blueprintsDir():
    return resModsDir() + 'ForgeBlueprints/'

def pnfModsDir():
    return resModsDir() + 'PnFMods/'

def resolveResModsTarget(relPath):
    base = resModsDir()
    full = _u1.path.abspath(base + relPath).replace('\\', '/')

    if not full.startswith(base):
        return None
    return full

def dirName(path):
    norm = path.replace('\\', '/')
    if '/' not in norm:
        return ''
    return norm.rsplit('/', 1)[0]

def ensureDir(path):
    if _u1.path.isdir(path):
        return
    try:
        _u1.makedirs(path)
    except Exception:
        pass

def fileExists(path):
    return _u1.path.isfile(path)

def pathExists(path):
    return _u1.path.exists(path)

def dirExists(path):
    return _u1.path.isdir(path)

_O_BINARY = getattr(_u1, 'O_BINARY', 0)

def openRead(path):
    return _u1.fdopen(_u1.open(path, _u1.O_RDONLY | _O_BINARY), 'rb')

def openWrite(path):
    return _u1.fdopen(
        _u1.open(path, _u1.O_WRONLY | _u1.O_CREAT | _u1.O_TRUNC | _O_BINARY),
        'wb')

def readBytes(path):
    f = openRead(path)
    try:
        return f.read()
    finally:
        f.close()

def writeBytes(path, data):
    ensureDir(dirName(path))
    f = openWrite(path)
    try:
        f.write(data)
    finally:
        f.close()

def removeFile(path):
    if _u1.path.isfile(path):
        _u1.remove(path)

def renameFile(src, dst):
    if _u1.path.isfile(dst):
        _u1.remove(dst)
    _u1.rename(src, dst)

def listFiles(directory, suffix=''):
    if not _u1.path.isdir(directory):
        return []
    out = []
    for name in _u1.listdir(directory):
        if suffix and not name.endswith(suffix):
            continue
        if _u1.path.isfile(_u1.path.join(directory, name)):
            out.append(name)
    return sorted(out)

def listSubdirs(directory):
    if not _u1.path.isdir(directory):
        return []
    out = []
    for name in _u1.listdir(directory):
        if _u1.path.isdir(_u1.path.join(directory, name)):
            out.append(name)
    return sorted(out)

_FNV_OFFSET = 0xcbf29ce484222325
_FNV_PRIME = 0x100000001b3
_FNV_MASK = (1 << 64) - 1

def hashBytes(data):
    # unicode would hash code points where the same content read back off disk
    # hashes utf-8 bytes -- the two silently disagree above ASCII. Encode at
    # the producer (Build.serialize, Installer._serialize), never here.
    if isinstance(data, unicode):
        raise Exception('hashBytes needs bytes, got unicode: %r'
                        % (data[:40],))
    h = _FNV_OFFSET
    for ch in data:
        h ^= ord(ch)
        h = (h * _FNV_PRIME) & _FNV_MASK
    return '%016x' % h

def hashFile(path):
    if not fileExists(path):
        return None
    return hashBytes(readBytes(path))

def statOf(path):
    """(size, mtime) as strings, or None. Cheap enough to call per run; the
    hash stays the authority, this only ever proves a file is UNCHANGED."""
    try:
        st = _u1.stat(path)
    except Exception:
        return None
    return (str(st.st_size), '%.6f' % st.st_mtime)
