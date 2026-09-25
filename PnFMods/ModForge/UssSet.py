# coding=utf-8

MASK = 0xFFFFFFFF
SIGN = 0x80000000
PERTURB_SHIFT = 5

def strhash(s):
    if isinstance(s, unicode):
        s = s.encode('utf-8')
    n = len(s)
    if n == 0:
        return 0
    x = (ord(s[0]) << 7) & MASK
    for ch in s:
        x = ((1000003 * x) & MASK) ^ ord(ch)
    x ^= n
    x &= MASK
    if x >= SIGN:
        x -= (SIGN << 1)
    if x == -1:
        x = -2
    return x

def set_order(items):
    size = 8
    table = [None] * size
    used = 0
    for key in items:
        hv = strhash(key)
        i = _slot(table, size, key, hv)
        if table[i] is not None:
            continue
        table[i] = (hv, key)
        used += 1
        if used * 3 >= size * 2:
            newsize = 8
            minused = used * 4
            while newsize <= minused:
                newsize <<= 1
            old = [e for e in table if e is not None]
            size = newsize
            table = [None] * size
            for h2, k2 in old:
                table[_slot(table, size, k2, h2)] = (h2, k2)
    return [e[1] for e in table if e is not None]

def _slot(table, size, key, hv):
    mask = size - 1
    i = hv & mask
    if table[i] is None or table[i][1] == key:
        return i
    perturb = hv & MASK
    while True:
        i = (i * 5 + perturb + 1) & MASK
        j = i & mask
        if table[j] is None or table[j][1] == key:
            return j
        perturb >>= PERTURB_SHIFT

class OrderedPropSet(object):
    def __init__(self):
        self._seq = []
        self._seen = {}

    def add(self, v):
        if v not in self._seen:
            self._seen[v] = True
            self._seq.append(v)

    def __len__(self):
        return len(self._seq)

    def __contains__(self, v):
        return v in self._seen

    def __iter__(self):
        return iter(self._seq)

    def ordered(self):
        return set_order(self._seq)
