# coding=utf-8

MOD_NAME = 'ModForge'

def _text(value):
    if isinstance(value, unicode):
        return value.encode('utf-8')
    return str(value)

def logInfo(*args):
    data = [_text(i) for i in args]
    utils.logInfo('[{}] {}'.format(MOD_NAME, ', '.join(data)))

def logError(*args):
    data = [_text(i) for i in args]
    utils.logError('[{}] {}'.format(MOD_NAME, ', '.join(data)))
