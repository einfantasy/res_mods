# coding=utf-8

import Paths

_RES_PACKAGES_REL = '../../../../../res_packages/'
_IDX_PACKAGES_REL = '../../../idx/'

def _hexBe(buf4):
    return int(buf4[::-1].encode('hex'), 16)

def _hexId(buf8):
    return buf8.encode('hex')

class _Node(object):
    __slots__ = ('id', 'parentId', 'name', 'children')

    def __init__(self, id_, parentId):
        self.id = id_
        self.parentId = parentId
        self.name = None
        self.children = {}

    def addChild(self, child):
        self.children[child.name] = child

    def childByName(self, name):
        return self.children.get(name)

class _FileLoc(object):
    __slots__ = ('offset', 'size')

    def __init__(self, offset, size):
        self.offset = offset
        self.size = size

class PkgMgr(object):
    def __init__(self, pkgName):
        self._pkgName = pkgName
        self._nodes = []
        self._byId = {}
        self._byName = {}
        self._files = {}
        self._pkgPath = None
        self._loaded = False
        self._loadError = None

    def _load(self):
        if self._loaded:
            return self._loadError is None
        idxPath = Paths.installerDir() + _IDX_PACKAGES_REL + '%s.idx' % self._pkgName
        if not Paths.fileExists(idxPath):
            self._loadError = 'idx not found: %s' % idxPath
            self._loaded = True
            return False
        try:
            self._parseIdx(idxPath)
        except Exception as exc:
            self._loadError = 'idx parse failed (%s): %s' % (idxPath, exc)
            self._loaded = True
            return False
        self._loaded = True
        return True

    def _parseIdx(self, idxPath):
        f = Paths.openRead(idxPath)
        try:
            f.seek(16)
            itemsAmount = _hexBe(f.read(4))
            filesAmount = _hexBe(f.read(4))
            f.seek(56)

            for _ in xrange(itemsAmount):
                f.read(8)
                f.read(8)
                id_ = _hexId(f.read(8))
                parentId = _hexId(f.read(8))
                node = _Node(id_, parentId)
                self._nodes.append(node)
                self._byId[id_] = node

            for i in xrange(itemsAmount):
                name = ''
                ch = f.read(1)
                while ch != '\x00':
                    name += ch
                    ch = f.read(1)
                self._nodes[i].name = name

            for _ in xrange(filesAmount):
                id_ = _hexId(f.read(8))
                f.read(8)
                offset = _hexBe(f.read(4))
                f.read(12)
                size = _hexBe(f.read(4))
                f.read(4)
                f.read(8)
                self._files[id_] = _FileLoc(offset, size)

            f.read(24)
            pkgRel = f.read()
            if pkgRel.endswith('\x00'):
                pkgRel = pkgRel[:-1]
            self._pkgPath = Paths.installerDir() + _RES_PACKAGES_REL + pkgRel
        finally:
            f.close()

        for node in self._nodes:
            self._byName[node.name] = node
            parent = self._byId.get(node.parentId)
            if parent is not None:
                parent.addChild(node)

    def _lookup(self, relativePath):
        if not self._load():
            return None
        components = relativePath.split('/')
        node = self._byName.get(components[0])
        if node is None:
            return None
        for component in components[1:]:
            node = node.childByName(component)
            if node is None:
                return None
        return node

    def hasFile(self, relativePath):
        node = self._lookup(relativePath)
        return node is not None and node.id in self._files

    def listFiles(self, relativeDir, suffix=''):
        node = self._lookup(relativeDir)
        if node is None:
            return []
        out = []
        stack = [(relativeDir.rstrip('/'), node)]
        while stack:
            prefix, current = stack.pop()
            for name, child in current.children.items():
                path = prefix + '/' + name
                if child.id in self._files:
                    if not suffix or path.endswith(suffix):
                        out.append(path)
                else:
                    stack.append((path, child))
        return out

    def getFileContents(self, relativePath):
        node = self._lookup(relativePath)
        if node is None:
            return None
        loc = self._files.get(node.id)
        if loc is None:
            return None
        if not Paths.fileExists(self._pkgPath):
            return None
        f = Paths.openRead(self._pkgPath)
        try:
            f.seek(loc.offset)
            return f.read(loc.size)
        finally:
            f.close()

    def loadError(self):
        self._load()
        return self._loadError

    def clear(self):
        del self._nodes[:]
        self._byId.clear()
        self._byName.clear()
        self._files.clear()
        self._loaded = False
        self._loadError = None
