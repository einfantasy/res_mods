# coding=utf-8

import Manifest as manifestMod
import Paths
import Resources
from Logger import logError, logInfo
from Codec import _u1

class PlannerError(Exception):
    pass

def discoverManifests():
    found = {}
    seenPaths = []

    blueprintsRoot = Paths.blueprintsDir()
    for name in Paths.listFiles(blueprintsRoot, suffix='.xml'):
        absPath = blueprintsRoot + name
        m = _readManifestFile(absPath)
        if m is None:
            continue
        if m.modName in found:
            logInfo("duplicate mod name '%s' (already from %s); ignoring %s"
                    % (m.modName, found[m.modName].sourcePath, absPath))
            continue
        found[m.modName] = m
        seenPaths.append(absPath)

    pnf = Paths.pnfModsDir()
    for sub in Paths.listSubdirs(pnf):
        candidate = pnf + sub + '/manifest.xml'
        if not Paths.fileExists(candidate):
            continue
        m = _readManifestFile(candidate)
        if m is None:
            continue
        if m.modName in found:
            logInfo("mod '%s' already discovered at %s; ignoring fallback %s"
                    % (m.modName, found[m.modName].sourcePath, candidate))
            continue
        found[m.modName] = m
        seenPaths.append(candidate)

    logInfo('discovered %d manifest(s) at %d location(s)'
            % (len(found), len(seenPaths)))
    return list(found.values())

def _readManifestFile(absPath):
    try:
        data = Paths.readBytes(absPath)
    except Exception as exc:
        logError('cannot read manifest %s: %s' % (absPath, exc))
        return None
    try:
        m = manifestMod.parseManifest(absPath, data)
    except manifestMod.ManifestError as exc:
        logError('invalid manifest %s: %s' % (absPath, exc))
        return None
    m.sourceHash = Paths.hashBytes(data)
    return m

def validateRequirements(manifests, installerVersion):
    present = set(m.modName for m in manifests)
    accepted = [m for m in manifests
                if _checkInstallerRequirement(m, installerVersion)]
    while True:
        byName = dict((m.modName, m) for m in accepted)
        survivors = [m for m in accepted
                     if _checkModRequirements(m, byName, present)]
        if len(survivors) == len(accepted):
            return survivors
        accepted = survivors

def _checkInstallerRequirement(m, installerVersion):
    req = m.installerRequirement
    if not req:
        return True
    if not manifestMod.satisfiesConstraint(installerVersion, req):
        logError(
            "'%s' requires installer %s but ModForge is %s; skipping"
            % (m.modName, req, installerVersion))
        return False
    return True

def _checkModRequirements(m, byName, present):
    for depName, constraint in m.modRequirements:
        dep = byName.get(depName)
        if dep is None:
            if depName in present:
                logError(
                    "'%s' requires mod '%s', which is present but was itself "
                    "skipped; skipping" % (m.modName, depName))
            else:
                logError(
                    "'%s' requires mod '%s' which is not installed; skipping"
                    % (m.modName, depName))
            return False
        if constraint and not manifestMod.satisfiesConstraint(dep.version,
                                                              constraint):
            logError(
                "'%s' requires %s %s but %s %s is installed; skipping"
                % (m.modName, depName, constraint, depName, dep.version))
            return False
    return True

def validateFileReferences(m):
    missing = []
    for t in m.builds:
        for action in t.actions:
            if action.kind not in ('insert', 'replace'):
                continue
            for elem in action.payload:
                _collectReferencedFiles(elem, missing)
    if not missing:
        return True
    for ref in missing:
        logError("'%s' references missing file: %s" % (m.modName, ref))
    logError("skipping '%s' due to %d missing file reference(s)"
             % (m.modName, len(missing)))
    return False

_FILE_REF_TAGS = ('swffile', 'xmlfile')

def _collectReferencedFiles(etElem, missingOut):
    tag = etElem.tag
    if tag in _FILE_REF_TAGS:
        candidate = (etElem.text or '').strip() or etElem.get('path')
        if candidate:
            if not _fileReferenceExists(candidate):
                missingOut.append(candidate)
    for child in etElem:
        _collectReferencedFiles(child, missingOut)

def _fileReferenceExists(candidate):
    return resolveReference(candidate) is not None

def resolveReference(candidate):
    for relPath in _candidateRelPaths(candidate):
        if Paths.fileExists(Paths.resModsDir() + relPath):
            return relPath
        if Resources.pristineExists(relPath):
            return relPath
    return None

_REF_BASE_DIRS = ('gui/unbound/', 'gui/flash/')

def _candidateRelPaths(candidate):
    base = Paths.resModsDir()
    out = []
    for prefix in _REF_BASE_DIRS + ('',):
        absPath = _u1.path.abspath(base + prefix + candidate)
        absPath = absPath.replace('\\', '/')
        if not absPath.startswith(base):
            continue
        relPath = absPath[len(base):]
        if relPath and relPath not in out:
            out.append(relPath)
    return out

# Never empty, whatever the derivation below manages. An allowlist that
# silently degrades to "permit everything" is the shape that leaked three
# times in link_mods.py.
_ALWAYS_OWNED = (manifestMod.USS_SETTINGS, manifestMod.VANILLA_MARKUP,
                 manifestMod.VANILLA_STYLES)

_INSTEAD = {
    manifestMod.VANILLA_MARKUP: "edit the definition with <ubBuildBlock name='...'>",
    manifestMod.VANILLA_STYLES: "edit the preset with <ubBuildStyle name='...'>",
    manifestMod.USS_SETTINGS: ("ModForge registers what it emits; declare the "
                               "definitions with <ubBuildBlock name='...'> or "
                               "<ubBuildStyle name='...'> instead"),
}

def unboundOwnedTargets():
    """Every file Unbound 1 owns, taken from vanilla's own `<default>` block.

    Derived rather than listed so a file WG adds to `<default>` in a future
    build is covered without anyone editing anything -- the hand-maintained
    version of this list is what leaked repeatedly elsewhere."""
    owned = set(_ALWAYS_OWNED)
    # Asked for rather than fetched: loadPristine reports a missing package
    # loudly, and this is a refinement of a set that is already correct
    # without it. The floor covers every file Unbound owns today; deriving
    # only adds whatever WG puts in <default> next.
    if not Resources.pristineExists(manifestMod.USS_SETTINGS):
        logInfo('vanilla %s is not available; using the built-in list of '
                'Unbound-owned files' % manifestMod.USS_SETTINGS)
        return owned
    data = Resources.loadPristine(manifestMod.USS_SETTINGS)
    try:
        root = manifestMod._u2.fromstring(data)
    except Exception as exc:
        logError('vanilla %s does not parse (%s); falling back to the built-in '
                 'list of Unbound-owned files' % (manifestMod.USS_SETTINGS, exc))
        return owned
    for default in root.findall('default'):
        for entry in default:
            text = (entry.text or '').strip()
            if not text:
                continue
            rel = resolveReference(text)
            if rel:
                owned.add(rel)
    return owned

def validateTargets(m, owned):
    """A mod may not write what Unbound owns.

    Refusing the whole mod, not just that one `<build>`: its payload would
    otherwise be written and never loaded, which is a mod that looks
    installed and does nothing."""
    ownedByCase = dict((o.lower(), o) for o in owned)
    for t in m.builds:
        rel = t.file
        if rel.lower() in ownedByCase:
            canonical = ownedByCase[rel.lower()]
            logError("'%s' writes %s, which Unbound owns -- %s. Skipping it."
                     % (m.modName, rel,
                        _INSTEAD.get(canonical, "use a definition verb")))
            return False
        if rel.lower().startswith(manifestMod.PAYLOAD_DIR.lower()):
            logError("'%s' writes %s, which is ModForge's own output "
                     "directory -- declare the definition with "
                     "<ubBuildBlock name='...'> or <ubBuildStyle name='...'> "
                     "and it picks the file. Skipping it." % (m.modName, rel))
            return False
    return True

def topoSort(manifests):
    byName = dict((m.modName, m) for m in manifests)

    inDegree = dict((m.modName, 0) for m in manifests)
    dependents = dict((m.modName, []) for m in manifests)
    for m in manifests:
        for depName, _ in m.modRequirements:
            if depName in byName:
                inDegree[m.modName] += 1
                dependents[depName].append(m.modName)

    ready = [m for m in manifests if inDegree[m.modName] == 0]
    ready.sort(key=_orderKey)
    out = []
    while ready:
        nxt = ready.pop(0)
        out.append(nxt)
        for childName in dependents[nxt.modName]:
            inDegree[childName] -= 1
            if inDegree[childName] == 0:
                ready.append(byName[childName])
        ready.sort(key=_orderKey)

    if len(out) != len(manifests):
        unresolved = [m.modName for m in manifests
                      if m.modName not in set(x.modName for x in out)]
        logError('dependency cycle involves: %s; these mods will be skipped'
                 % ', '.join(unresolved))
    return out

def _orderKey(m):
    base = m.sourcePath.rsplit('/', 1)[-1]
    return (-m.priority, base)

def summarizePlan(orderedManifests):
    if not orderedManifests:
        logInfo('no eligible mods to apply')
        return
    logInfo('install order:')
    for idx, m in enumerate(orderedManifests, start=1):
        logInfo('  %d. %s %s (priority %d)'
                % (idx, m.modName, m.version, m.priority))
