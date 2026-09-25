# coding=utf-8

EOF_CHAR = u''
ESCAPE = u'\\'

HEX_DIGITS = frozenset(u'0123456789abcdefABCDEF')
DECIMAL_DIGITS = frozenset(u'0123456789')
SINGLE_ESCAPE_CHARS = frozenset(u'\'"\\bfnrtv')

RESERVED_NAMES = frozenset((
    u'abstract enum int short boolean export interface static byte extends '
    u'long super char final native synchronized class float package throws '
    u'const goto private transient debugger implements protected volatile '
    u'double import public').split())

ZS_CHARS = frozenset([u' ', u' ', u' ', u' ', u' ',
                      u' ', u' ', u' ', u' ', u' ',
                      u' ', u' ', u' ', u' ', u' ',
                      u' ', u'　'])
WHITESPACE_CHARS = frozenset((u'\t', u'\x0b', u'\x0c', u' ', u'\xa0'))
LINE_TERMINATOR_CHARS = frozenset((u'\n', u'\r', u' ', u' '))
IDENTIFIER_EXTRA = frozenset((u'$', u'_'))

def is_identifier_start(char):
    return char in IDENTIFIER_EXTRA or char.isalpha()

def is_identifier_part(char):
    return char in IDENTIFIER_EXTRA or char.isalpha() or char.isdigit()

def is_whitespace_char(char):
    return char in WHITESPACE_CHARS or char in ZS_CHARS

def is_line_terminator(char):
    return char in LINE_TERMINATOR_CHARS

(INVALID, EOF, EOL, RETURN, BITOR, BITXOR, BITAND, EQ, NE, LT, LE, GT, GE,
 LSH, RSH, ADD, SUB, MUL, DIV, MOD, NOT, BITNOT, NEW, DELETE, TYPEOF, STRING,
 NULL, THIS, FALSE, TRUE, SHEQ, SHNE, REGEXP, THROW, IN, INSTANCEOF, TRY,
 LEFT_BRACKET, RIGHT_BRACKET, LEFT_CURLY_BRACE, RIGHT_CURLY_BRACE, LEFT_PAREN,
 RIGHT_PAREN, COMMA, ASSIGN, ASSIGN_BITOR, ASSIGN_BITXOR, ASSIGN_BITAND,
 ASSIGN_LSH, ASSIGN_RSH, ASSIGN_URSH, ASSIGN_ADD, ASSIGN_SUB, ASSIGN_MUL,
 ASSIGN_DIV, ASSIGN_MOD, HOOK, COLON, OR, AND, INC, DEC, DOT, FUNCTION, IF,
 ELSE, SWITCH, CASE, DEFAULT, WHILE, DO, FOR, BREAK, CONTINUE, VAR, WITH,
 CATCH, RESERVED, IDENTIFIER, SPACE, COMMENT, SEMICOLON, FINALLY, VOID,
 DECIMAL, INTEGER, URSH, LINETERM) = (
    'INVALID EOF EOL RETURN BITOR BITXOR BITAND EQ NE LT LE GT GE LSH RSH ADD '
    'SUB MUL DIV MOD NOT BITNOT NEW DELETE TYPEOF STRING NULL THIS FALSE TRUE '
    'SHEQ SHNE REGEXP THROW IN INSTANCEOF TRY LEFT_BRACKET RIGHT_BRACKET '
    'LEFT_CURLY_BRACE RIGHT_CURLY_BRACE LEFT_PAREN RIGHT_PAREN COMMA ASSIGN '
    'ASSIGN_BITOR ASSIGN_BITXOR ASSIGN_BITAND ASSIGN_LSH ASSIGN_RSH '
    'ASSIGN_URSH ASSIGN_ADD ASSIGN_SUB ASSIGN_MUL ASSIGN_DIV ASSIGN_MOD HOOK '
    'COLON OR AND INC DEC DOT FUNCTION IF ELSE SWITCH CASE DEFAULT WHILE DO '
    'FOR BREAK CONTINUE VAR WITH CATCH RESERVED IDENTIFIER SPACE COMMENT '
    'SEMICOLON FINALLY VOID DECIMAL INTEGER URSH LINETERM').split()

ASSIGN_DIV = 'ASSIGN_DIV'

LITERAL_TO_TYPE = {
    u'.': DOT, u':': COLON, u';': SEMICOLON, u'?': HOOK, u'=': ASSIGN,
    u',': COMMA, u'(': LEFT_PAREN, u')': RIGHT_PAREN, u'{': LEFT_CURLY_BRACE,
    u'}': RIGHT_CURLY_BRACE, u'[': LEFT_BRACKET, u']': RIGHT_BRACKET,
    u'~': BITNOT, u'&': BITOR, u'^': BITXOR, u'!': NOT, u'%': MOD, u'/': DIV,
    u'*': MUL, u'-': SUB, u'+': ADD, u'>': GT, u'<': LT,
}

KEYWORD_TO_TYPE = {
    u'true': TRUE, u'false': FALSE, u'null': NULL, u'break': BREAK,
    u'else': ELSE, u'new': NEW, u'var': VAR, u'case': CASE,
    u'finally': FINALLY, u'return': RETURN, u'void': VOID, u'catch': CATCH,
    u'for': FOR, u'switch': SWITCH, u'while': WHILE, u'continue': CONTINUE,
    u'function': FUNCTION, u'this': THIS, u'with': WITH, u'if': IF,
    u'throw': THROW, u'delete': DELETE, u'in': IN, u'try': TRY, u'do': DO,
    u'instanceof': INSTANCEOF, u'typeof': TYPEOF,
}

PRECEDENCE = {
    EOF: 0, LEFT_PAREN: 0, RIGHT_PAREN: 0, LEFT_BRACKET: 0, RIGHT_BRACKET: 0,
    LEFT_CURLY_BRACE: 0, RIGHT_CURLY_BRACE: 0, COLON: 0, SEMICOLON: 0, DOT: 0,
    HOOK: 0, INC: 0, DEC: 0,
    ASSIGN: 2, ASSIGN_BITOR: 2, ASSIGN_BITXOR: 2, ASSIGN_BITAND: 2,
    ASSIGN_LSH: 2, ASSIGN_RSH: 2, ASSIGN_URSH: 2, ASSIGN_ADD: 2,
    ASSIGN_SUB: 2, ASSIGN_MUL: 2, ASSIGN_DIV: 2, ASSIGN_MOD: 2,
    COMMA: 1, OR: 4, AND: 5, BITOR: 6, BITXOR: 7, BITAND: 8,
    LSH: 11, RSH: 11, URSH: 11, ADD: 12, SUB: 12, MUL: 13, DIV: 13, MOD: 13,
    EQ: 9, NE: 9, SHEQ: 9, SHNE: 9, LT: 10, GT: 10, LE: 10, GE: 10,
    INSTANCEOF: 10, IN: 10,
}

UNARY_OPS = frozenset((DELETE, VOID, TYPEOF, INC, DEC, ADD, SUB, BITNOT, NOT))
COMPARISON_OPS = frozenset((EQ, NE, SHEQ, SHNE, LT, GT, LE, GE, INSTANCEOF, IN))
ASSIGNMENT_OPS = frozenset((
    ASSIGN, ASSIGN_BITOR, ASSIGN_BITXOR, ASSIGN_BITAND, ASSIGN_LSH,
    ASSIGN_RSH, ASSIGN_URSH, ASSIGN_ADD, ASSIGN_SUB, ASSIGN_MUL, ASSIGN_DIV,
    ASSIGN_MOD))
COUNT_OPS = frozenset((INC, DEC))

class Token(object):
    __slots__ = ('type', 'value', 'locator')

    def __init__(self, type, value, locator=None):
        self.type = type
        self.value = value
        self.locator = locator

    def __repr__(self):
        return '<Token %s %r>' % (self.type, self.value)

class Scanner(object):
    def __init__(self, source, filename=None, line=0, column=0, offset=0):
        self.src = source
        self.pos = 0
        self.filename = filename
        self.line = line
        self.column = column
        self.buffer = []
        self.locator = None

    def peek_char(self):
        if self.pos >= len(self.src):
            return EOF_CHAR
        return self.src[self.pos]

    def next_in(self, collection):
        next = self.peek_char()
        return next != EOF_CHAR and next in collection

    def advance(self):
        c = self.peek_char()
        if c != EOF_CHAR:
            self.pos += 1
        self.buffer.append(c)
        self.column += 1
        if self.locator is None:
            self.locator = (self.filename, self.line, self.column, self.pos)

    def make_token(self, type):
        token = Token(type, u''.join(self.buffer), self.locator)
        self.buffer = []
        self.locator = None
        return token

    def make_invalid_token(self):
        self.advance()
        return self.make_token(INVALID)

    def _is_ws(self, char):
        return char != EOF_CHAR and is_whitespace_char(char)

    def _is_lt(self, char):
        return char != EOF_CHAR and is_line_terminator(char)

    def _is_id_start(self, char):
        return char != EOF_CHAR and is_identifier_start(char)

    def _is_id_part(self, char):
        return char != EOF_CHAR and is_identifier_part(char)

    def consume_whitespace(self):
        while self._is_ws(self.peek_char()):
            self.advance()

    def consume_line_terminators(self):
        next = self.peek_char()
        while self._is_lt(next):
            self.advance()
            if next == u'\r' and self.peek_char() == u'\n':
                self.advance()
            self.line += 1
            self.column = 0
            next = self.peek_char()

    def scan_single_line_comment(self):
        while True:
            next = self.peek_char()
            if next == EOF_CHAR or self._is_lt(next):
                break
            self.advance()
        return self.make_token(COMMENT)

    def scan_multiline_comment(self):
        while True:
            next = self.peek_char()
            if next == EOF_CHAR:
                return self.make_invalid_token()
            if self._is_lt(next):
                self.consume_line_terminators()
                continue
            if next == u'*':
                self.advance()
                if self.peek_char() == u'/':
                    self.advance()
                    break
                continue
            self.advance()
        return self.make_token(COMMENT)

    def consume_unicode_escape(self):
        if self.peek_char() != ESCAPE:
            return
        self.advance()
        if self.peek_char() != u'u':
            return
        self.advance()
        self.consume_hex_digits(4)

    def consume_escape(self):
        if self.peek_char() != ESCAPE:
            return
        self.advance()
        next = self.peek_char()
        if next == EOF_CHAR:
            return
        if next == u'x':
            self.advance()
            self.consume_hex_digits()
        elif next == u'u':
            self.advance()
            self.consume_hex_digits(4)
        else:
            self.advance()

    def scan_identifier_or_keyword(self):
        next = self.peek_char()
        if next == ESCAPE:
            self.consume_unicode_escape()
        elif not self._is_id_start(next):
            return self.make_invalid_token()
        else:
            self.advance()
        next = self.peek_char()
        while next != EOF_CHAR:
            if self._is_id_part(next):
                self.advance()
            elif next == ESCAPE:
                self.consume_unicode_escape()
            else:
                break
            next = self.peek_char()
        value = u''.join(self.buffer)
        if value in KEYWORD_TO_TYPE:
            return self.make_token(KEYWORD_TO_TYPE[value])
        if value in RESERVED_NAMES:
            return self.make_token(RESERVED)
        return self.make_token(IDENTIFIER)

    def consume_decimal_digits(self):
        while self.next_in(DECIMAL_DIGITS):
            self.advance()

    def consume_hex_digits(self, length=2):
        for _ in range(length):
            if not self.next_in(HEX_DIGITS):
                break
            self.advance()

    def scan_number(self, decimal=False):
        type = decimal and DECIMAL or INTEGER
        next = self.peek_char()
        if next == EOF_CHAR:
            return None
        if next == u'0':
            self.advance()
            if self.next_in(u'xX'):
                self.advance()
                while self.next_in(HEX_DIGITS):
                    self.advance()
                return self.make_token(INTEGER)
        self.consume_decimal_digits()
        next = self.peek_char()
        if next == u'.':
            if decimal:
                return self.make_token(DECIMAL)
            self.advance()
            type = DECIMAL
        self.consume_decimal_digits()
        if self.next_in(u'eE'):
            self.advance()
            if self.next_in(u'-+'):
                if next == u'-':
                    type = DECIMAL
                self.advance()
            self.consume_decimal_digits()
        return self.make_token(type)

    def scan_string(self):
        quote = self.peek_char()
        self.advance()
        while True:
            next = self.peek_char()
            if next == EOF_CHAR:
                return self.make_invalid_token()
            if self._is_lt(next):
                return self.make_invalid_token()
            if next == quote:
                self.advance()
                break
            elif next == ESCAPE:
                self.consume_escape()
            else:
                self.advance()
        return self.make_token(STRING)

    def scan_regexp(self):
        if self.next_in(u'*/'):
            return self.make_invalid_token()
        in_character_class = False
        while True:
            next = self.peek_char()
            if next == EOF_CHAR:
                return self.make_invalid_token()
            if self._is_lt(next):
                return self.make_invalid_token()
            if next == u'[':
                in_character_class = True
            elif next == u']':
                in_character_class = False
            elif next == ESCAPE:
                self.advance()
                next = self.peek_char()
                if next == EOF_CHAR or self._is_lt(next):
                    return self.make_invalid_token()
            elif next == u'/' and not in_character_class:
                self.advance()
                break
            self.advance()
        return self.make_token(REGEXP)

    def scan_regexp_flags(self):
        next = self.peek_char()
        while next != EOF_CHAR and self._is_id_part(next):
            if next == ESCAPE:
                self.consume_unicode_escape()
            else:
                self.advance()
            next = self.peek_char()
        return self.make_token(IDENTIFIER)

    def next(self):
        return self.scan()

    def scan(self):
        self.locator = None
        next = self.peek_char()
        if next == EOF_CHAR:
            self.advance()
            return self.make_token(EOF)
        if self._is_ws(next):
            self.consume_whitespace()
            return self.make_token(SPACE)
        if self._is_lt(next):
            self.consume_line_terminators()
            return self.make_token(LINETERM)
        if self._is_id_start(next) or next == ESCAPE:
            return self.scan_identifier_or_keyword()
        if next in u'\'"':
            return self.scan_string()
        if next == u'.':
            self.advance()
            if self.next_in(DECIMAL_DIGITS):
                return self.scan_number(decimal=True)
            return self.make_token(DOT)
        if next in DECIMAL_DIGITS:
            return self.scan_number()
        if next == u'/':
            self.advance()
            next = self.peek_char()
            if next == u'/':
                return self.scan_single_line_comment()
            if next == u'*':
                return self.scan_multiline_comment()
            if next == u'=':
                self.advance()
                return self.make_token(ASSIGN_DIV)
            return self.make_token(DIV)
        if next == u'=':
            self.advance()
            if self.peek_char() == u'=':
                self.advance()
                if self.peek_char() == u'=':
                    self.advance()
                    return self.make_token(SHEQ)
                return self.make_token(EQ)
            return self.make_token(ASSIGN)
        if next == u'!':
            self.advance()
            if self.peek_char() == u'=':
                self.advance()
                if self.peek_char() == u'=':
                    self.advance()
                    return self.make_token(SHNE)
                return self.make_token(NE)
            return self.make_token(NOT)
        if next == u'+':
            self.advance()
            next = self.peek_char()
            if next == u'=':
                self.advance()
                return self.make_token(ASSIGN_ADD)
            if next == u'+':
                self.advance()
                return self.make_token(INC)
            return self.make_token(ADD)
        if next == u'-':
            self.advance()
            next = self.peek_char()
            if next == u'=':
                self.advance()
                return self.make_token(ASSIGN_SUB)
            if next == u'-':
                self.advance()
                return self.make_token(DEC)
            return self.make_token(SUB)
        if next == u'&':
            self.advance()
            next = self.peek_char()
            if next == u'&':
                self.advance()
                return self.make_token(AND)
            if next == u'=':
                self.advance()
                return self.make_token(ASSIGN_BITAND)
            return self.make_token(BITAND)
        if next == u'|':
            self.advance()
            next = self.peek_char()
            if next == u'|':
                self.advance()
                return self.make_token(OR)
            if next == u'=':
                self.advance()
                return self.make_token(ASSIGN_BITOR)
            return self.make_token(BITOR)
        if next == u'*':
            self.advance()
            if self.peek_char() == u'=':
                self.advance()
                return self.make_token(ASSIGN_MUL)
            return self.make_token(MUL)
        if next == u'<':
            self.advance()
            next = self.peek_char()
            if next == u'=':
                self.advance()
                return self.make_token(LE)
            if next == u'<':
                self.advance()
                if self.peek_char() == u'=':
                    self.advance()
                    return self.make_token(ASSIGN_LSH)
                return self.make_token(LSH)
            return self.make_token(LT)
        if next == u'>':
            self.advance()
            next = self.peek_char()
            if next == u'=':
                self.advance()
                return self.make_token(GE)
            if next == u'>':
                self.advance()
                next = self.peek_char()
                if next == u'=':
                    self.advance()
                    return self.make_token(ASSIGN_RSH)
                if next == u'>':
                    self.advance()
                    if self.peek_char() == u'=':
                        self.advance()
                        return self.make_token(ASSIGN_URSH)
                    return self.make_token(URSH)
                return self.make_token(RSH)
            return self.make_token(GT)
        if next == u'%':
            self.advance()
            if self.peek_char() == u'=':
                self.advance()
                return self.make_token(ASSIGN_MOD)
            return self.make_token(MOD)
        if next == u'^':
            self.advance()
            if self.peek_char() == u'=':
                self.advance()
                return self.make_token(ASSIGN_BITXOR)
            return self.make_token(BITXOR)
        if next in LITERAL_TO_TYPE:
            self.advance()
            return self.make_token(LITERAL_TO_TYPE[next])
        return self.make_invalid_token()

class TokenStream(object):
    def __init__(self, scanner):
        self.scanner = scanner
        self.next_token = None
        self.has_line_terminator_before_next = False
        self.next()

    def next(self):
        self.has_line_terminator_before_next = False
        token = self.next_token
        next = self.scanner.next()
        type = next.type
        while type != EOF and type in (SPACE, LINETERM, COMMENT):
            if type == LINETERM:
                self.has_line_terminator_before_next = True
            next = self.scanner.next()
            type = next.type
        self.next_token = next
        return token

    def peek(self):
        return self.next_token

    def scan_regexp(self):
        start_token = self.next_token
        token = self.scanner.scan_regexp()
        if token.type == REGEXP:
            token = Token(REGEXP, start_token.value + token.value,
                          start_token.locator)
        else:
            self.next()
        return token

    def scan_regexp_flags(self):
        token = self.scanner.scan_regexp_flags()
        if token.type == IDENTIFIER:
            self.next()
        return token

class TokenStreamAllowReserved(TokenStream):
    def _coerce(self, token):
        if token is not None and token.type == RESERVED:
            return Token(IDENTIFIER, token.value, token.locator)
        return token

    def peek(self):
        return self._coerce(TokenStream.peek(self))

    def next(self):
        return self._coerce(TokenStream.next(self))

def make_string_scanner(string, filename=None, line=0, column=0):
    if isinstance(string, str):
        string = string.decode('utf-8')
    return Scanner(string, filename, line, column)
