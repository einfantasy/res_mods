# coding=utf-8

import time

import Paths

# Windows file timestamps advance on the ~15 ms system tick, so two writes
# close together can share an mtime. A stamp that young proves nothing; only
# one older than this is trusted to mean "unchanged". Measured: time.time()
# is coarser than the mtime source here, so a fresh stamp can read ~1 ms in
# the future -- the window is one-sided on purpose.
_STAMP_SETTLE_SECONDS = 2.0

def outputHashes(stagedPairs):
    return dict((rel, Paths.hashBytes(data)) for rel, data in stagedPairs)

def stampsFor(relPaths):
    out = {}
    for rel in relPaths:
        absPath = Paths.resolveResModsTarget(rel)
        if absPath is None:
            continue
        st = Paths.statOf(absPath)
        if st is not None:
            out[rel] = st
    return out

def stampHolds(relPath, stamps):
    absPath = Paths.resolveResModsTarget(relPath)
    if absPath is None:
        return False
    return _stampProvesUnchanged(absPath, stamps.get(relPath))

def _stampProvesUnchanged(absPath, known):
    if known is None:
        return False
    current = Paths.statOf(absPath)
    if current is None or current != known:
        return False
    try:
        return (time.time() - float(current[1])) > _STAMP_SETTLE_SECONDS
    except Exception:
        return False

def detectDrift(recordedHashes, recordedStamps=None):
    """Recorded stat is a fast path to 'definitely unchanged' and nothing
    else -- a mismatch always falls through to the hash, so the gate can
    never invent drift, only (given a byte-length AND microsecond mtime
    forgery) miss it."""
    stamps = recordedStamps or {}
    drifted = []
    for rel, expected in sorted(recordedHashes.items()):
        absPath = Paths.resolveResModsTarget(rel)
        if absPath is None:
            continue
        if _stampProvesUnchanged(absPath, stamps.get(rel)):
            continue
        if not Paths.fileExists(absPath):
            drifted.append((rel, 'missing'))
            continue
        try:
            actual = Paths.hashBytes(Paths.readBytes(absPath))
        except Exception as exc:
            drifted.append((rel, 'unreadable: %s' % exc))
            continue
        if actual != expected:
            drifted.append((rel, 'overwritten by something else'))
    return drifted
