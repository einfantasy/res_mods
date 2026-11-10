# coding=utf-8

import time

from xml.dom import minidom as _minidom

from Codec import _u2
import Build
import Guard
import Manifest
import Paths
import Resources
import Validate
from Actions import applyAction, evaluateGuards
from Logger import logInfo, logError
import Planner
import Requires
from Planner import (
    discoverManifests, summarizePlan, topoSort, unboundOwnedTargets,
    validateFileReferences, validateRequirements, validateTargets,
)
from Transaction import Transaction

class _Stats(object):
    def __init__(self):
        self.discovered = 0
        self.installed = 0
        self.updated = 0
        self.unchanged = 0
        self.noop = 0
        self.skipped = 0
        self.failed = 0
        self.removed = 0
        self.definitions = 0
        self.definitionsNew = 0
        self.definitionsDropped = 0
        self.conflicts = 0

        self.restartFor = []

def runInstaller(installerVersion):
    stats = _Stats()
    Paths.ensureDir(Paths.cacheDir())

    registry = _loadRegistry()
    if registry.get('buildId') and registry['buildId'] != Paths.gameBuildId():
        logInfo('game build changed (%s -> %s); flushing pristine cache'
                % (registry['buildId'], Paths.gameBuildId()))
        Resources.invalidateCache()

    manifests = discoverManifests()
    stats.discovered = len(manifests)
    wasCompiled = registry.get('compiled', {})
    recordedStamps = registry.get('stamps', {})
    recordedLint = registry.get('linted', {})
    recordedOutputs = registry.get('outputs', {})
    recordedRestart = registry.get('restart', {})
    oldHashes = registry.get('mods', {})
    if not manifests:
        stats.removed = _reportRemoved(oldHashes, {})
        tx = Transaction()
        reverted = _revertOrphanedOutputs(recordedOutputs, set(), tx)
        try:
            tx.commit()
        except Exception as exc:
            logError('transaction commit failed: %s' % exc)
            Resources.shutdown()
            return stats
        dropped = []
        if _registrationSettled(recordedOutputs, reverted):
            dropped = _dropOrphanedCompiles(wasCompiled, {})
        Validate.removeStubs()
        stats.restartFor, restart = _decideRestart(
            set(), recordedRestart, [tx], dropped)
        return _finalize(registry, [], stats, installerVersion,
                         restart=restart)

    newHashes = dict((m.modName, m.sourceHash) for m in manifests)
    changed = newHashes != oldHashes
    buildChanged = registry.get('buildId') != Paths.gameBuildId()

    eligible = validateRequirements(manifests, installerVersion)


    owned = unboundOwnedTargets()
    eligible = [m for m in eligible if validateTargets(m, owned)]


    eligible = topoSort(eligible)




    payloadTx = Transaction()
    (compiled, compileFailed, declared, sources, registration,
     definitionApplied, dependents, linted) = _runBuilds(
         eligible, wasCompiled, recordedStamps, recordedLint, payloadTx, stats)
    try:
        payloadTx.commit()
    except Exception as exc:
        logError('payload commit failed: %s' % exc)
        Resources.shutdown()
        return stats

    builtChanged = compiled != wasCompiled

    lintChanged = linted != recordedLint



    drift = Guard.detectDrift(recordedOutputs, recordedStamps)
    _reportDrift(drift)
    if (not changed and not buildChanged and not builtChanged and not drift
            and not lintChanged):
        logInfo('no manifest changes since last run; nothing to do')
        stats.unchanged = len(manifests)
        _dropOrphanedCompiles(wasCompiled, declared)
        return stats
    if not changed and not buildChanged and not builtChanged and drift:
        logInfo('manifests unchanged but an output drifted; re-applying')
    if not changed and buildChanged:
        logInfo('manifests unchanged but build moved; re-applying')
    if not changed and not buildChanged and builtChanged:
        logInfo('manifests unchanged but a compiled payload moved; re-applying')
    if (not changed and not buildChanged and not builtChanged and not drift
            and lintChanged):
        logInfo('manifests unchanged but the definitions were re-linted; '
                're-applying')

    stats.removed = _reportRemoved(oldHashes, newHashes)

    eligible = [m for m in eligible
                if m.modName not in compileFailed and m.modName not in dependents]


    versions = Planner.installedVersions(eligible)
    held = dict((m.modName, _heldBuilds(m, versions)) for m in eligible)
    _reportHeldDefinitions(eligible, versions)
    eligible = [m for m in eligible
                if validateFileReferences(m, held[m.modName])]
    ordered = topoSort(eligible)
    summarizePlan(ordered)
    stats.failed = len(compileFailed)
    stats.skipped = stats.discovered - len(ordered) - len(compileFailed)

    applied = set(definitionApplied)
    failed = set()
    forgeFailed = set()
    contributors = [(m.modName, held[m.modName], applied, failed)
                    for m in ordered]
    if registration is not None:
        contributors.append((FORGE, [registration], set(), forgeFailed))

    targetFiles = _collectTargetFiles(contributors)
    tx = Transaction()
    reverted = _revertOrphanedOutputs(recordedOutputs, set(targetFiles), tx)
    staged = []

    refused = []
    for relPath in targetFiles:
        try:
            updated = _applyToTarget(relPath, contributors, sources, refused)
        except _TargetSkipped as skip:
            logError("target '%s' skipped: %s" % (relPath, skip))
            continue
        except Exception as exc:
            logError("target '%s' skipped: %s: %s"
                     % (relPath, type(exc).__name__, exc))
            continue
        if updated is None:
            continue
        absPath = Paths.resolveResModsTarget(relPath)
        if absPath is None:
            logError("target path escapes res_mods/: %s" % relPath)
            continue
        tx.stage(absPath, updated)
        staged.append((relPath, updated))

    if forgeFailed:
        logError('the definitions were built but could not be registered in '
                 '%s; the client will not load them' % Manifest.USS_SETTINGS)

    stats.conflicts += len(refused)
    for m in ordered:
        if m.modName in failed:
            stats.failed += 1
        elif m.modName in applied:
            if oldHashes.get(m.modName) is None:
                stats.installed += 1
            elif oldHashes.get(m.modName) != m.sourceHash:
                stats.updated += 1
            else:
                stats.unchanged += 1
        else:


            stats.noop += 1

    try:
        tx.commit()
    except Exception as exc:
        logError('transaction commit failed: %s' % exc)
        payloadTx.revertCommitted()
        Resources.shutdown()
        return stats




    dropped = []
    if _registrationSettled(recordedOutputs,
                            reverted + [rel for rel, _data in staged]):
        dropped = _dropOrphanedCompiles(wasCompiled, declared)

    stats.restartFor, restart = _decideRestart(
        _restartFiles(eligible), recordedRestart, [payloadTx, tx], dropped)
    successful = [m for m in ordered if m.modName not in failed]
    return _finalize(registry, successful, stats, installerVersion,
                     Guard.outputHashes(staged), compiled, linted, restart)

FORGE = 'ModForge'

def _reportHeldDefinitions(manifests, versions):


    import Definitions
    for m in manifests:
        for spec in m.definitions:
            if not Planner.requirementHolds(spec.requirement, versions):
                logInfo("'%s': <requires mods='%s'> does not hold; skipping "
                        "its edits to %s"
                        % (m.modName, Requires.describe(spec.requirement),
                           Definitions.label(spec.namespace, spec.name)))

def _heldBuilds(m, versions):
    out = []
    for spec in m.builds:
        if Planner.requirementHolds(spec.requirement, versions):
            out.append(spec)
        else:
            logInfo("'%s': <requires mods='%s'> does not hold; skipping its "
                    "edits to %s" % (m.modName,
                                     Requires.describe(spec.requirement),
                                     spec.file))
    return out

def _restartFiles(manifests):
    return set(spec.file for m in manifests for spec in m.builds
               if spec.restartOnChange)

def _decideRestart(flagged, recorded, txs, dropped):






    changedAbs = set()
    for tx in txs:
        changedAbs |= tx.changed
    changed = []
    for relPath in sorted(flagged | set(recorded)):
        if (relPath in dropped
                or Paths.resolveResModsTarget(relPath) in changedAbs):
            changed.append(relPath)
    record = dict((p, recorded.get(p, '')) for p in flagged)
    if not changed:
        return [], record
    current = dict((p, _contentHash(p)) for p in changed)
    if not [p for p in changed if recorded.get(p) != current[p]]:
        logError('%s changed again to the content the client was already '
                 'restarted for; not restarting again. Something else rewrites '
                 'it on every boot.' % ', '.join(changed))
        return [], record
    for p in changed:
        if p in record:
            record[p] = current[p]
    return changed, record

def _contentHash(relPath):
    absPath = Paths.resolveResModsTarget(relPath)
    return (absPath and Paths.hashFile(absPath)) or 'absent'

def _reportRemoved(oldHashes, newHashes):
    removedNames = [name for name in oldHashes if name not in newHashes]
    for name in removedNames:
        logInfo("removed '%s' since last run; will revert its changes" % name)
    return len(removedNames)

def _registrationSettled(recordedOutputs, written):


    if Manifest.USS_SETTINGS not in recordedOutputs:
        return True
    if Manifest.USS_SETTINGS in written:
        return True
    logError('%s was not rewritten this run; keeping the compiled definitions '
             'it may still register' % Manifest.USS_SETTINGS)
    return False

class _TargetSkipped(Exception):
    pass

def _reportDrift(drift):



    for relPath, why in drift:
        logError("'%s' changed on disk since our last run (%s); rebuilding it "
                 "from pristine. To keep an edit to this file, declare it in a "
                 "blueprint -- ModForge rewrites it on every run."
                 % (relPath, why))
        absPath = Paths.resolveResModsTarget(relPath)
        if absPath is not None and Paths.fileExists(absPath):
            saved = _backupDrifted(relPath, absPath)
            if saved:
                logInfo('kept the drifted copy at %s' % saved)

def _backupDrifted(relPath, absPath):
    stamp = '%d' % int(time.time())
    dest = Paths.cacheDir() + 'drift_backups/' + stamp + '/' + relPath
    try:
        Paths.writeBytes(dest, Paths.readBytes(absPath))
    except Exception as exc:
        logError('cannot back up %s: %s' % (relPath, exc))
        return None
    return dest

def _runBuilds(manifests, recorded, stamps, recordedLint, tx, stats):
    import Fragment
    sources = Fragment.Sources()
    built = {}
    failedNames = set()


    dependents = set()
    linted = {}
    declared = set()


    pending = {}
    emittedXml = []


    definitionApplied = set()
    for m in manifests:
        for spec in m.builds:
            if not spec.root:
                continue
            declared.add(spec.file)
            try:
                built[spec.file] = _runOneGenerated(m, spec, sources,
                                                    recorded, stamps, tx,
                                                    pending, emittedXml)
            except Exception as exc:
                logError("'%s' cannot generate %s: %s"
                         % (m.modName, spec.file, exc))
                failedNames.add(m.modName)
                continue
            definitionApplied.add(m.modName)

    try:
        registration = _runDefinitions(manifests, sources, recorded, stamps,
                                       tx, pending, built, declared,
                                       failedNames, emittedXml, stats,
                                       definitionApplied, dependents,
                                       recordedLint, linted)
    except Exception as exc:

        logError('the definitions could not be built (%s: %s); none of them '
                 'are registered' % (type(exc).__name__, exc))
        registration = None

    for problem in Validate.duplicateDefinitions(emittedXml):
        logError(problem)
    for problem in _styleProblems(emittedXml, sources):
        logError(problem)


    for problem in Validate.installedUnbound2Problems():
        logError(problem)
    return (built, failedNames, declared, sources, registration,
            definitionApplied, dependents, linted)

def _styleProblems(emittedXml, sources):


    if not [1 for _rel, data in emittedXml if Validate.styleClassUses(data)]:
        return []
    try:
        vanilla = sources.index(Manifest.VANILLA_STYLES, 'css', 'name')
    except Exception as exc:
        return ['cannot check style references: %s' % exc]
    return Validate.unresolvedStyleClasses(emittedXml, vanilla)

class _Definition(object):
    __slots__ = ('namespace', 'name', 'relPath', 'absPath', 'data', 'isNew',
                 'contributors', 'contributions', 'stamp')

def _runDefinitions(manifests, sources, recorded, stamps, tx, pending, built,
                    declared, failedNames, emittedXml, stats,
                    definitionApplied, dependents, recordedLint, linted):


    import Definitions
    first, kept, swf, count = _settleDefinitions(
        manifests, sources, pending, failedNames, dependents, recordedLint,
        linted, stats)
    keptKeys = set((d.namespace, d.name) for d in kept)
    stats.definitionsDropped = len([1 for d in first
                                    if (d.namespace, d.name) not in keptKeys])
    if not kept:
        return None

    created = 0
    for d in kept:
        created += d.isNew
        logInfo('%s %s, from %s'
                % ('created' if d.isNew else 'overrode',
                   Definitions.label(d.namespace, d.name),
                   ', '.join(d.contributors)))
    logInfo('%d definition(s): %d overridden, %d created'
            % (len(kept), len(kept) - created, created))

    stats.definitions = len(kept)
    stats.definitionsNew = created
    for d in kept:
        declared.add(d.relPath)
        emittedXml.append((d.relPath, d.data))
        definitionApplied.update(d.contributors)
        _stageDefinition(d, recorded, stamps, tx, built)

    swfPath = None
    if count:
        _stageDefinitionsSwf(swf, [d.absPath for d in kept], pending,
                             recorded, tx, built, declared)
        swfPath = Manifest.USS_DEFINITIONS_SWF


    ordered = ([d for d in kept if d.namespace == 'css']
               + [d for d in kept if d.namespace != 'css'])
    return Manifest.registrationBuild(
        [Manifest.ussDefinitionPath(d.namespace, d.name) for d in ordered],
        swfPath)

def _settleDefinitions(manifests, sources, pending, failedNames, dependents,
                       recordedLint, linted, stats):





    first = None
    roundPaths = []
    while True:
        for absPath in roundPaths:
            pending.pop(absPath, None)
        roundPaths = []
        linted.clear()
        eligible = _requirementsHold(manifests, failedNames, dependents)
        emitted, failed, stats.conflicts = _mergeDefinitions(eligible, sources)
        if first is None:
            first = emitted
        if failed:
            failedNames |= failed
            before = len(dependents)
            _requirementsHold(eligible, failedNames, dependents)
            if len(dependents) > before:
                continue
        if not emitted:
            return first, [], None, 0

        for d in emitted:
            d.stamp = Paths.hashBytes(d.data)
            pending[d.absPath] = d.data
            roundPaths.append(d.absPath)
        dropped = set()
        swf, count = _compileDefinitions(roundPaths, pending, dropped)
        _coveredByTheSwf(emitted, dropped, pending)
        offenders = set()
        for d in emitted:
            if d.absPath not in dropped:
                continue
            blamed, _faults = _introducers(d, sources, _compileFaults)
            logError('%s does not compile; not installing %s'
                     % (d.relPath, _names(blamed)))
            offenders |= blamed
        if not offenders:
            try:
                offenders = _lintOffenders(emitted, sources, recordedLint,
                                           linted)
            except Exception as exc:
                logError('the Unbound 1 lint failed (%s: %s); the definitions '
                         'install unchecked' % (type(exc).__name__, exc))
                linted.clear()
                offenders = set()
        if not offenders:
            return first, emitted, swf, count
        if not offenders - failedNames:


            logError('the definitions did not settle (%s failed again); none '
                     'are registered' % _names(offenders))
            return first, [], None, 0
        failedNames |= offenders

def _requirementsHold(manifests, failedNames, dependents):

    out = [m for m in manifests
           if m.modName not in failedNames and m.modName not in dependents]
    while True:
        gone = failedNames | dependents
        versions = Planner.installedVersions(
            [o for o in out if o.modName not in gone])
        keep = []
        for m in out:
            missing = [n for n in Requires.names(m.modRequirement,
                                                 positiveOnly=True)
                       if n in gone]
            if missing and not Planner.requirementHolds(m.modRequirement,
                                                        versions):
                logError("'%s' requires mod '%s', which failed; skipping"
                         % (m.modName, missing[0]))
                dependents.add(m.modName)
            else:
                keep.append(m)
        if len(keep) == len(out):
            return keep
        out = keep

def _introducers(d, sources, faults):


    import Definitions
    if len(d.contributors) == 1:
        return set(d.contributors), faults(d, d.data)
    merger = Definitions.Merger(sources, quiet=True)
    key = (d.namespace, d.name)
    for i in range(1, len(d.contributions) + 1):
        try:
            data, _isNew = merger.build(key, d.contributions[:i])
        except Exception:
            continue
        if data is None:
            continue
        try:
            found = faults(d, data)
        except Exception:
            continue
        if found:
            return set([d.contributions[i - 1][0].modName]), found
    return set(d.contributors), faults(d, d.data)

def _names(modNames):
    return ', '.join("'%s'" % n for n in sorted(modNames))

def _compileFaults(d, data):
    import UssCompile
    probe = {d.absPath: data}
    try:
        UssCompile.compileMarkup([d.absPath], probe, allowEmpty=True)
        UssCompile.expressionKeys([d.absPath], probe)
    except Exception as exc:
        return [exc]
    return []

def _lintOffenders(emitted, sources, recordedLint, linted):



    import Definitions
    import SceneClasses
    import Ub1Stamp
    buildId = Paths.gameBuildId()
    scene = SceneClasses.load()
    names = sorted('%s:%s' % (d.namespace, d.name) for d in emitted)

    classKey = 'classes:%s' % ('none' if scene is None else len(scene[0]))
    context = '|'.join([buildId, Ub1Stamp.STAMP, classKey] + names)

    if isinstance(context, unicode):
        context = context.encode('utf-8')
    context = Paths.hashBytes(context)
    todo = []
    for d in emitted:
        stamp = Paths.hashBytes(d.stamp + context)
        if recordedLint.get(d.relPath) == stamp:
            linted[d.relPath] = stamp
        else:
            todo.append((d, stamp))
    if not todo:
        return set()



    try:
        import Ub1Lint
    except Exception as exc:
        logError('the Unbound 1 linter did not load (%s: %s); definitions '
                 'install unchecked' % (type(exc).__name__, exc))
        return set()
    known = {}
    for namespace, (relPath, tag, attr) in Definitions.NAMESPACES.items():


        try:
            known[namespace] = set(sources.index(relPath, tag, attr))
        except Exception as exc:
            logError('cannot check names against %s: %s' % (relPath, exc))
            known[namespace] = None
            continue
        known[namespace].update(d.name for d in emitted
                                if d.namespace == namespace)
    ctx = Ub1Lint.Context(classNames=known['block'], cssNames=known['css'],
                          classes=scene[0] if scene else None,
                          controllers=scene[1] if scene else None)
    merger = Definitions.Merger(sources, quiet=True)
    offenders = set()
    for d, stamp in todo:
        where = Definitions.label(d.namespace, d.name)
        try:
            base = _baselineFindings(merger, d, ctx)
            found = Ub1Lint.introduced(_lint(d.data, ctx), base)
        except Exception as exc:
            logError('%s could not be linted (%s: %s); installing it '
                     'unchecked' % (where, type(exc).__name__, exc))
            continue
        refusing = [f for f in found if Ub1Lint.refuses(f)]
        if not refusing:
            for f in found:
                logInfo('%s: %s %s at %s: %s'
                        % (where, f.severity, f.code, f.where, f.message))
            linted[d.relPath] = stamp
            continue
        blamed, faults = _introducers(
            d, sources, lambda _d, data, base=base, ctx=ctx: [
                f for f in Ub1Lint.introduced(_lint(data, ctx), base)
                if Ub1Lint.refuses(f)])
        for f in faults:
            logError('%s would %s (%s at %s): %s; not installing %s'
                     % (where, f.severity, f.code, f.where, f.message,
                        _names(blamed)))
        offenders |= blamed
    return offenders

def _lint(data, ctx):
    import Ub1Lint
    return Ub1Lint.lintDocument(_u2.fromstring(data), ctx)

def _baselineFindings(merger, d, ctx):
    doc, _isNew = merger.baseline(d.namespace, d.name)
    try:
        return _lint(Build.serialize(doc), ctx)
    finally:
        doc.unlink()

def _coveredByTheSwf(emitted, dropped, pending):







    import UssCompile
    covered = UssCompile.expressionKeys(
        [d.absPath for d in emitted if d.absPath not in dropped], pending)
    out = []
    for d in emitted:
        try:
            missing = UssCompile.expressionKeys([d.absPath], pending) - covered
            why = '%d expression(s) the compiled SWF does not carry' % len(
                missing)
        except Exception as exc:
            missing, why = True, 'its expressions cannot be read back: %s' % exc
        if missing:
            logError('%s: %s; not registering it rather than shipping a block '
                     'that throws when it is built' % (d.relPath, why))
            dropped.add(d.absPath)
            continue
        out.append(d)
    return out

def _mergeDefinitions(manifests, sources):





    import Definitions
    failed = set()
    while True:
        merger = Definitions.Merger(sources)
        emitted = []
        roundFailed = set()
        contributing = [m for m in manifests if m.modName not in failed]
        versions = Planner.installedVersions(contributing)
        for key, contributions in Definitions.collect(contributing, versions):
            namespace, name = key
            relPath = Manifest.definitionFile(namespace, name)
            absPath = Paths.resolveResModsTarget(relPath)
            if absPath is None:
                logError('%s: output path escapes res_mods/: %s'
                         % (Definitions.label(namespace, name), relPath))
                continue
            landed = set()
            try:
                data, isNew = merger.build(key, contributions, landed,
                                           roundFailed)
            except Exception as exc:
                logError('cannot assemble %s: %s: %s'
                         % (Definitions.label(namespace, name),
                            type(exc).__name__, exc))
                roundFailed.update(m.modName for m, _ in contributions)
                continue
            if data is not None:
                d = _Definition()
                (d.namespace, d.name, d.relPath, d.absPath, d.data,
                 d.isNew) = namespace, name, relPath, absPath, data, isNew
                d.contributors = []
                for m, _ in contributions:


                    if m.modName in landed and m.modName not in d.contributors:
                        d.contributors.append(m.modName)
                d.contributions = contributions
                emitted.append(d)
        if not roundFailed:
            return emitted, failed, len(merger.refused)
        failed |= roundFailed

def _compileDefinitions(paths, pending, dropped):


    import UssCompile
    try:
        return UssCompile.compileMarkup(paths, pending, allowEmpty=True)
    except Exception as exc:
        logError('the definitions do not compile as one (%s); compiling each '
                 'to find which' % exc)
    good = []
    for absPath in paths:
        try:
            UssCompile.compileMarkup([absPath], pending, allowEmpty=True)
        except Exception as exc:
            logError('%s: dropped, its expressions do not compile: %s'
                     % (absPath, exc))
            dropped.add(absPath)
            continue
        good.append(absPath)
    if not good:
        return None, 0
    try:
        return UssCompile.compileMarkup(good, pending, allowEmpty=True)
    except Exception as exc:
        logError('the definitions still do not compile with the %d bad one(s) '
                 'out; none are registered: %s' % (len(dropped), exc))
        dropped.update(good)
        return None, 0

def _stageDefinition(d, recorded, stamps, tx, built):
    stamp = d.stamp
    built[d.relPath] = (stamp, ', '.join(d.contributors))
    previous = recorded.get(d.relPath)
    if (previous and previous[0] == stamp
            and Guard.stampHolds(d.relPath, stamps)):
        return
    if Paths.hashFile(d.absPath) != stamp:
        tx.stage(d.absPath, d.data)

def _stageDefinitionsSwf(swf, sourcePaths, pending, recorded, tx, built,
                         declared):
    relPath = Manifest.DEFINITIONS_SWF
    declared.add(relPath)
    absPath = Paths.resolveResModsTarget(relPath)
    stamp = Paths.hashBytes(''.join(
        [_COMPILER_STAMP] + [_sourceHash(p, pending) for p in sourcePaths]))
    built[relPath] = (stamp, 'definitions')
    previous = recorded.get(relPath)
    if previous and previous[0] == stamp and Paths.fileExists(absPath):
        return
    tx.stage(absPath, str(swf))

def _runOneGenerated(m, spec, sources, recorded, stamps, tx, pending,
                     emittedXml):
    import Build
    outPath = Paths.resolveResModsTarget(spec.file)
    if outPath is None:
        raise Exception('output path escapes res_mods/: %s' % spec.file)

    data = Build.buildDocument(spec, m.modName, sources)
    stamp = Paths.hashBytes(data)





    pending[outPath] = data
    emittedXml.append((spec.file, data))
    previous = recorded.get(spec.file)
    if (previous and previous[0] == stamp and Guard.stampHolds(spec.file, stamps)):
        return (stamp, m.modName)



    if Paths.hashFile(outPath) != stamp:
        tx.stage(outPath, data)
        logInfo("'%s' generated %s from %d instruction(s)"
                % (m.modName, spec.file, len(spec.actions)))
    return (stamp, m.modName)

def _sourceHash(absPath, pending):
    if absPath in pending:
        return Paths.hashBytes(pending[absPath])
    return Paths.hashFile(absPath)

def _revertOrphanedOutputs(recordedOutputs, claimedPaths, tx):



    reverted = []
    for relPath in sorted(recordedOutputs):
        if relPath in claimedPaths:
            continue
        absPath = Paths.resolveResModsTarget(relPath)
        if absPath is None:
            continue
        pristine = Resources.loadPristine(relPath)
        if pristine is None:
            logError('cannot restore %s: no pristine copy' % relPath)
            continue
        if Paths.fileExists(absPath) and Paths.readBytes(absPath) == pristine:
            reverted.append(relPath)
            continue
        try:
            tx.stage(absPath, pristine)
        except Exception as exc:
            logError('cannot restore %s: %s' % (relPath, exc))
            continue
        reverted.append(relPath)
        logInfo('no mod edits %s any more; restoring the stock file' % relPath)
    return reverted

def _dropOrphanedCompiles(recorded, declaredPaths):
    removed = []
    for relPath in sorted(recorded):
        if relPath in declaredPaths:
            continue
        absPath = Paths.resolveResModsTarget(relPath)
        if absPath is None or not Paths.fileExists(absPath):
            continue
        try:
            Paths.removeFile(absPath)
        except Exception as exc:
            logError('cannot remove %s: %s' % (relPath, exc))
            continue
        removed.append(relPath)
        logInfo("removed %s; '%s' no longer builds it"
                % (relPath, recorded[relPath][1]))
    return removed

def _collectTargetFiles(contributors):
    seen = []
    seenSet = set()
    for _label, builds, _applied, _failed in contributors:
        for t in builds:
            if t.root:
                continue
            if t.file not in seenSet:
                seenSet.add(t.file)
                seen.append(t.file)
    return seen

def _applyToTarget(relPath, contributors, sources, refusedOut=None):



    import Definitions
    pristine = Resources.loadPristine(relPath)
    if pristine is None:
        raise _TargetSkipped('cannot fetch pristine copy')

    try:
        doc = _minidom.parseString(pristine)
    except Exception as exc:
        raise _TargetSkipped('pristine is not valid XML: %s' % exc)

    mutated = False


    claims = Definitions.Claims()
    for label, builds, appliedOut, failedOut in contributors:
        targets = [t for t in builds
                   if not t.root and t.file == relPath]
        if not targets:
            continue

        snapshot = doc.cloneNode(True)
        refusedMark = len(claims.refused)
        try:
            edited = False
            for tspec in targets:
                if not evaluateGuards(doc.documentElement, tspec.guards):
                    logInfo("'%s' guard blocks edits to %s"
                            % (label, relPath))
                    continue
                for action in tspec.actions:
                    logInfo("'%s': %s on %s"
                            % (label, action.kind, relPath))
                    if applyAction(doc, action, label, None, sources, claims):
                        edited = True

            if edited:
                mutated = True
                appliedOut.add(label)
        except Exception as exc:
            logError("'%s' failed on %s: %s: %s"
                     % (label, relPath, type(exc).__name__, exc))
            failedOut.add(label)

            doc.unlink()
            doc = snapshot
            del claims.refused[refusedMark:]
            continue
        else:
            snapshot.unlink()

    Definitions.reportRefused(claims.refused, relPath)
    if refusedOut is not None:
        refusedOut.extend(claims.refused)
    if not mutated:
        return None
    Definitions.stripClaims(doc.documentElement)
    _guardDocument(relPath, doc)
    return _serialize(doc)

def _guardDocument(relPath, doc):
    resolve = Planner.resolveReference

    stubPathFor = lambda tag, n: (Validate.ensureXmlStub(n)
                                  if tag == 'xmlfile'
                                  else Validate.ensureSwfStub())
    for original, action in Validate.substituteBrokenRefs(
            doc, relPath, resolve, stubPathFor):
        if action == 'removed':
            logError("'%s' would not load; entry removed so the client boots "
                     "with that mod inert" % original)
        else:
            logError("'%s' would not load; redirected to %s so the load "
                     "completes and that mod alone is inert"
                     % (original, action))

    problems = Validate.validateAssembled(relPath, doc, resolve)
    problems.extend(
        Validate.validateElementNames(doc, Validate.unbound2ElementNames()))
    for problem in problems:
        logError('%s: %s' % (relPath, problem))
    return problems

def _serialize(doc):
    pretty = doc.toprettyxml(indent='\t')
    lines = []
    for line in pretty.split('\n'):
        if line.strip():
            lines.append(line)
    out = '\n'.join(lines)

    if not out.startswith('<?xml'):
        out = '<?xml version="1.0" ?>\n' + out
    if isinstance(out, unicode):



        out = out.encode('utf-8')
    return out

def _loadRegistry():
    p = Paths.installedRegistryPath()
    if not Paths.fileExists(p):
        return {'buildId': None, 'mods': {}}
    try:
        root = _u2.fromstring(Paths.readBytes(p))
    except Exception as exc:
        logError('installed.xml is unreadable (%s); treating as first run' % exc)
        return {'buildId': None, 'mods': {}}
    mods = {}
    for child in root.findall('mod'):
        name = child.get('name')
        h = child.get('hash')
        if name and h:
            mods[name] = h
    outputs = {}
    for child in root.findall('output'):
        path = child.get('path')
        h = child.get('hash')
        if path and h:
            outputs[path] = h
    compiled = {}
    for child in root.findall('compiled'):
        path = child.get('path')
        h = child.get('hash')
        if path and h:
            compiled[path] = (h, child.get('mod') or '')
    stamps = {}
    for child in root.findall('stamp'):
        path = child.get('path')
        size = child.get('size')
        mtime = child.get('mtime')
        if path and size is not None and mtime is not None:
            stamps[path] = (size, mtime)
    linted = {}
    for child in root.findall('linted'):
        path = child.get('path')
        h = child.get('hash')
        if path and h:
            linted[path] = h
    restart = {}
    for child in root.findall('restart'):
        path = child.get('path')
        if path:
            restart[path] = child.get('hash') or ''
    return {
        'buildId': root.get('buildId'),
        'mods': mods,
        'outputs': outputs,
        'compiled': compiled,
        'stamps': stamps,
        'linted': linted,
        'restart': restart,
    }

def _saveRegistry(buildId, successfulManifests, outputHashes, compiled,
                  stamps, linted=None, restart=None):
    root = _u2.Element('installed')
    root.set('buildId', buildId)
    root.set('installer', _installerVersion or '')
    for m in successfulManifests:
        e = _u2.SubElement(root, 'mod')
        e.set('name', m.modName)
        e.set('version', m.version)
        e.set('hash', m.sourceHash or '')

    for path in sorted(outputHashes or {}):
        e = _u2.SubElement(root, 'output')
        e.set('path', path)
        e.set('hash', outputHashes[path])

    for path in sorted(compiled or {}):
        stamp, modName = compiled[path]
        e = _u2.SubElement(root, 'compiled')
        e.set('path', path)
        e.set('hash', stamp)
        e.set('mod', modName)

    for path in sorted(stamps or {}):
        size, mtime = stamps[path]
        e = _u2.SubElement(root, 'stamp')
        e.set('path', path)
        e.set('size', size)
        e.set('mtime', mtime)

    for path in sorted(linted or {}):
        e = _u2.SubElement(root, 'linted')
        e.set('path', path)
        e.set('hash', linted[path])

    for path in sorted(restart or {}):
        e = _u2.SubElement(root, 'restart')
        e.set('path', path)
        if restart[path]:
            e.set('hash', restart[path])
    data = _u2.tostring(root)
    Paths.writeBytes(Paths.installedRegistryPath(), data)

_installerVersion = None
_COMPILER_STAMP = '1'

def _finalize(_oldRegistry, successfulManifests, stats, installerVersion,
              outputHashes=None, compiled=None, linted=None, restart=None):
    global _installerVersion
    _installerVersion = installerVersion

    stamps = Guard.stampsFor(list((outputHashes or {}).keys())
                             + list((compiled or {}).keys()))
    try:
        _saveRegistry(Paths.gameBuildId(), successfulManifests, outputHashes,
                      compiled, stamps, linted, restart)
    except Exception as exc:
        logError('failed to write installed.xml: %s' % exc)
    Resources.shutdown()
    return stats
