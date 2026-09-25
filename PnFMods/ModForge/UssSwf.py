# coding=utf-8

_PREFIX_HEX = (
    '780004e200000ea600001e01004411190000004113004410e8033c00430200'
    '00005a0a0300000006000000040c8b513301000000008964aac19f010000c5'
    '0a6d61696e00')

_SUFFIX_HEX = '0913010000006d61696e0040000000'

_DOABC2_HEX = '010000006672616d653100'

_ADLER_BASE = 65521
_ADLER_NMAX = 5552

def _unhex(h):
    out = bytearray()
    i = 0
    while i < len(h):
        out.append(int(h[i:i + 2], 16))
        i += 2
    return out

def _u32le(v):
    return bytearray([v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255])

def adler32(data):
    a, b = 1, 0
    i, n = 0, len(data)
    while i < n:
        end = i + _ADLER_NMAX
        if end > n:
            end = n
        for c in data[i:end]:
            a += c
            b += a
        a %= _ADLER_BASE
        b %= _ADLER_BASE
        i = end
    return (b << 16) | a

def zlib_stored(data):
    out = bytearray([0x78, 0x9C])
    i, n = 0, len(data)
    while True:
        chunk = n - i
        if chunk > 65535:
            chunk = 65535
        out.append(1 if i + chunk >= n else 0)
        out += bytearray([chunk & 255, (chunk >> 8) & 255,
                          (~chunk) & 255, ((~chunk) >> 8) & 255])
        out += data[i:i + chunk]
        i += chunk
        if i >= n:
            break
    s = adler32(data)
    out += bytearray([(s >> 24) & 255, (s >> 16) & 255, (s >> 8) & 255, s & 255])
    return out

def _long_tag_header(code, length):
    v = (code << 6) | 0x3F
    return bytearray([v & 255, (v >> 8) & 255]) + _u32le(length)

def build_swf(abc, compress=True):
    abc = bytearray(abc)
    tag = _unhex(_DOABC2_HEX) + abc
    body = _unhex(_PREFIX_HEX)

    body += _long_tag_header(82, len(tag))
    body += tag
    body += _unhex(_SUFFIX_HEX)

    out = bytearray(b'CWS' if compress else b'FWS')
    out.append(12)
    out += _u32le(8 + len(body))
    out += zlib_stored(body) if compress else body
    return out
