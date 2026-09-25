# coding=utf-8

TAGS = ('bind', 'innerBind', 'userData', 'background9Slice')

def local_name(tag):
    if tag[:1] == '{':
        return tag[tag.find('}') + 1:]
    return tag

def scan_element(root, collector):
    for el in root.iter():
        if local_name(el.tag) in TAGS:
            v = el.get('value')
            if v is None:
                v = u''
            elif not isinstance(v, unicode):
                v = v.decode('utf-8')
            collector.add_row(v)

def scan_string(et, data, collector):
    scan_element(et.fromstring(data), collector)
