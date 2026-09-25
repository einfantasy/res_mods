# coding=utf-8

import re

from UssParse import make_string_parser
from UssSet import OrderedPropSet

ROW_SPLIT_PATTERN = re.compile(u";(?=(?:[^']*'[^']*')*[^']*$)", re.UNICODE)

def split_row(row):
    parts = re.split(ROW_SPLIT_PATTERN, row)
    if u';'.join(parts) != row or row.count(u"'") % 2:
        raise Exception('Error in splitting expression:\n' + row)
    return parts

def translate(row):
    out = []
    for part in split_row(row):
        out.append((part,) + make_expression(part))
    return out

def parse_part(row):
    if row == u'':
        return (None, u'null', [])
    node = make_string_parser(row).parse_expression()
    props = OrderedPropSet()
    node.makePropSet(props, OrderedPropSet())
    return (node, node.makeCode(None), props.ordered())

def make_expression(row):
    node, code, props = parse_part(row)
    return (code, props)

class Collector(object):
    def __init__(self):
        self.expressions = {}

    def add_row(self, row):
        for part in split_row(row):
            if part not in self.expressions:
                self.expressions[part] = parse_part(part)

    def entries(self):
        out = []
        for row in sorted(self.expressions):
            node, body, props = self.expressions[row]
            out.append((row.replace(u'\n', u' ').replace(u'\t', u' '),
                        node, props))
        return out
