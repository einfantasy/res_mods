# coding=utf-8

import Paths
from Logger import logInfo, logError
from PkgMgr import PkgMgr
from Codec import _u1

_pkgMgrs = {}

def _packageNameFor(relPath):
    head = relPath.split('/', 1)[0]
    return head or 'gui'

def _getPkgMgr(pkgName):
    mgr = _pkgMgrs.get(pkgName)
    if mgr is None:
        mgr = PkgMgr(pkgName)
        _pkgMgrs[pkgName] = mgr
    return mgr

def _cachePath(relPath):
    return Paths.originalsDir() + relPath

def _stockResPath(relPath):
    return Paths.gameBuildDir() + 'res/' + relPath

def loadPristine(relPath):
    cached = _cachePath(relPath)
    if Paths.fileExists(cached):
        return Paths.readBytes(cached)

    stock = _stockResPath(relPath)
    if Paths.fileExists(stock):
        data = Paths.readBytes(stock)
        Paths.writeBytes(cached, data)
        return data

    pkgName = _packageNameFor(relPath)
    mgr = _getPkgMgr(pkgName)
    data = mgr.getFileContents(relPath)
    if data is None:
        loadErr = mgr.loadError()
        if loadErr:
            logError('cannot read package %s (%s)' % (pkgName, loadErr))
        else:
            logError('file not found in package %s: %s' % (pkgName, relPath))
        return None

    Paths.writeBytes(cached, data)
    logInfo('pristine extracted: %s (%d bytes)' % (relPath, len(data)))
    return data

def pristineExists(relPath):
    if Paths.fileExists(_cachePath(relPath)):
        return True
    if Paths.fileExists(_stockResPath(relPath)):
        return True
    return _getPkgMgr(_packageNameFor(relPath)).hasFile(relPath)

def invalidateCache():
    od = Paths.originalsDir()
    if not Paths.dirExists(od):
        return

    walk = list(_u1.walk(od))
    for root, dirs, files in reversed(walk):
        rootSlash = root if root.endswith('/') or root.endswith('\\') else root + '/'
        for name in files:
            try:
                _u1.remove(rootSlash + name)
            except Exception:
                pass
        for name in dirs:
            try:
                _u1.rmdir(rootSlash + name)
            except Exception:
                pass

def shutdown():
    for mgr in _pkgMgrs.values():
        mgr.clear()
    _pkgMgrs.clear()
