# coding=utf-8

from Codec import _u4, _u5
from Logger import logInfo, logError

TITLE = 'ModForge'

TEXT = 'IDS_MODFORGE_RESTARTING'

def restartClient(relPaths, engine=None, notify=None):


    engine = engine or _u4
    notify = notify or _u5
    if engine is None:
        logError('%s changed but the client cannot be restarted from here; '
                 'restart it by hand' % ', '.join(relPaths))
        return False
    logInfo('%s changed; restarting the client so it takes effect'
            % ', '.join(relPaths))


    engine.callback(0, lambda: _fire(engine, notify))
    return True

def _fire(engine, notify):


    if notify is not None:
        try:
            if notify.isBalloonShown():
                notify.hideBalloon()
            notify.showBalloon(TITLE, TEXT)
        except Exception as exc:
            logError('restart notice failed: %s' % exc)
    engine.restartGame()
