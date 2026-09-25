# coding=utf-8

import UssAst as ast
from UssLex import (
    make_string_scanner, TokenStreamAllowReserved, Token,
    PRECEDENCE, UNARY_OPS, COMPARISON_OPS, ASSIGNMENT_OPS, COUNT_OPS,
    IDENTIFIER, STRING, DECIMAL, INTEGER, REGEXP, EOF,
    THIS, NULL, TRUE, FALSE, NEW, FUNCTION, IN,
    LEFT_BRACKET, RIGHT_BRACKET, LEFT_CURLY_BRACE, RIGHT_CURLY_BRACE,
    LEFT_PAREN, RIGHT_PAREN, COMMA, COLON, DOT, HOOK,
    DIV, ASSIGN_DIV, TYPEOF, DELETE, VOID)

STATIC_PROPS = None
STATIC_CONSTANTS = None

class Parser(object):
    def __init__(self, token_stream):
        self.token_stream = token_stream
        self.precedence_table = PRECEDENCE
        self.accept_in = True

    def next(self):
        return self.token_stream.next()

    def peek(self):
        return self.token_stream.peek().type

    def raise_unexpected_token(self, token, expected=None):
        locator = token.locator or (None, 0, 0, 0)
        message = ("Unexpected token '%s' on line %d, column %d."
                   % (token.value, locator[1], locator[2]))
        if expected:
            message = message + " Expected '%s'." % expected
        raise Exception(message)

    def expect(self, expected):
        next = self.next()
        if next.type != expected:
            self.raise_unexpected_token(next, expected)
        return next

    def has_line_terminator_before_next(self):
        return self.token_stream.has_line_terminator_before_next

    def scan_regexp(self):
        return self.token_stream.scan_regexp()

    def scan_regexp_flags(self):
        return self.token_stream.scan_regexp_flags()

    def precedence(self, token):
        if not self.accept_in and token == IN:
            return 0
        return self.precedence_table.get(token, 0)

    def is_unary_op(self, token):
        return token in UNARY_OPS

    def is_comparison_op(self, token):
        return token in COMPARISON_OPS

    def is_assignment_op(self, token):
        return token in ASSIGNMENT_OPS

    def is_count_op(self, token):
        return token in COUNT_OPS

    def is_valid_left_hand_side(self, expression):
        return (isinstance(expression, ast.Node)
                and expression.is_valid_left_hand_side())

    def parse_property_assignment(self):
        next = self.next()
        type = next.type
        if type == IDENTIFIER and next.value in (u'get', u'set'):
            if self.peek() == COLON:
                self.expect(COLON)
                name = ast.PropertyName(next.value)
                value = self.parse_assignment_expression()
                assignment = ast.ObjectProperty(name, value)
            elif next.value == u'get':
                name = self.expect(IDENTIFIER).value
                self.expect(LEFT_PAREN)
                self.expect(RIGHT_PAREN)
                assignment = ast.PropertyGetter(name, self.parse_function_body())
            else:
                name = self.expect(IDENTIFIER).value
                self.expect(LEFT_PAREN)
                parameter = self.expect(IDENTIFIER).value
                self.expect(RIGHT_PAREN)
                assignment = ast.PropertySetter(name, parameter,
                                                self.parse_function_body())
        else:
            if type == IDENTIFIER:
                name = ast.PropertyName(next.value)
            elif type == STRING:
                name = ast.StringLiteral(next.value)
            elif type in (DECIMAL, INTEGER):
                name = ast.NumberLiteral(next.value)
            else:
                self.raise_unexpected_token(next)
            self.expect(COLON)
            value = self.parse_assignment_expression()
            assignment = ast.ObjectProperty(name, value)
        if self.peek() != RIGHT_CURLY_BRACE:
            self.expect(COMMA)
        return assignment

    def parse_object_literal(self):
        self.expect(LEFT_CURLY_BRACE)
        properties = []
        while self.peek() != RIGHT_CURLY_BRACE:
            properties.append(self.parse_property_assignment())
        self.expect(RIGHT_CURLY_BRACE)
        return ast.ObjectLiteral(properties)

    def parse_array_literal(self):
        values = []
        self.expect(LEFT_BRACKET)
        while self.peek() != RIGHT_BRACKET:
            if self.peek() == COMMA:
                self.expect(COMMA)
                values.append(ast.Elision())
                continue
            values.append(self.parse_assignment_expression())
            if self.peek() != RIGHT_BRACKET:
                self.expect(COMMA)
        self.expect(RIGHT_BRACKET)
        return ast.ArrayLiteral(values)

    def parse_regexp_literal(self):
        pattern = self.scan_regexp()
        if pattern.type != REGEXP:
            raise Exception('Invalid regexp pattern')
        flags = self.scan_regexp_flags()
        if flags.type != IDENTIFIER:
            raise Exception('Invalid regexp flags')
        return ast.RegExpLiteral(pattern.value, flags.value)

    def parse_expression(self):
        result = self.parse_assignment_expression()
        while self.peek() == COMMA:
            comma = self.expect(COMMA)
            right = self.parse_assignment_expression()
            result = ast.BinaryOperation(comma.value, result, right)
        return result

    def parse_primary_expression(self):
        type = self.peek()
        if type == THIS:
            self.next()
            return ast.ThisNode()
        if type == NULL:
            self.next()
            return ast.NullNode()
        if type == TRUE:
            self.next()
            return ast.TrueNode()
        if type == FALSE:
            self.next()
            return ast.FalseNode()
        if type == IDENTIFIER:
            return ast.Name(self.next().value)
        if type in (DECIMAL, INTEGER):
            return ast.NumberLiteral(self.next().value)
        if type == STRING:
            return ast.StringLiteral(self.next().value)
        if type == LEFT_BRACKET:
            return self.parse_array_literal()
        if type == LEFT_CURLY_BRACE:
            return self.parse_object_literal()
        if type in (DIV, ASSIGN_DIV):
            return self.parse_regexp_literal()
        if type == LEFT_PAREN:
            self.expect(LEFT_PAREN)
            previous = self.accept_in
            self.accept_in = True
            result = self.parse_expression()
            self.accept_in = previous
            self.expect(RIGHT_PAREN)
            return result
        self.raise_unexpected_token(self.next())

    def parse_arguments(self):
        self.expect(LEFT_PAREN)
        result = []
        while self.peek() != RIGHT_PAREN:
            result.append(self.parse_assignment_expression())
            if self.peek() != RIGHT_PAREN:
                self.expect(COMMA)
        self.expect(RIGHT_PAREN)
        return result

    def parse_member_expression(self, allow_call=True):
        type = self.peek()
        if type == NEW:
            self.expect(NEW)
            expression = self.parse_member_expression(False)
            result = ast.NewExpression(expression, self.parse_arguments())
        elif type == FUNCTION:
            result = self.parse_function_expression()
        else:
            result = self.parse_primary_expression()
        isConstantExpression = False
        isConstantToValidate = False
        if type == IDENTIFIER:
            if STATIC_PROPS is not None:
                isConstantExpression = result.value in STATIC_PROPS
            if STATIC_CONSTANTS is not None:
                isConstantToValidate = result.value in STATIC_CONSTANTS
        return self.parse_member_expression_tail(
            allow_call, result, isConstantExpression, isConstantToValidate)

    def parse_member_expression_tail(self, allow_call, node,
                                     isConstantExpression,
                                     isConstantToValidate):
        type = self.peek()
        if type == DOT:
            self.expect(DOT)
            key = self.expect(IDENTIFIER)
            node = ast.DotProperty(node, key.value, isConstantExpression,
                                   isConstantToValidate)
        elif type == LEFT_BRACKET:
            self.expect(LEFT_BRACKET)
            index = self.parse_expression()
            node = ast.BracketProperty(node, index, isConstantExpression,
                                       isConstantToValidate)
            self.expect(RIGHT_BRACKET)
        elif type == LEFT_PAREN and allow_call:
            node = ast.CallExpression(node, self.parse_arguments(),
                                      isConstantExpression,
                                      isConstantToValidate)
        else:
            return node
        return self.parse_member_expression_tail(
            allow_call, node, isConstantExpression, isConstantToValidate)

    def parse_new_expression(self):
        raise Exception("'new' expressions are not supported")

    def parse_left_hand_side_expression(self):
        if self.peek() == NEW:
            return self.parse_new_expression()
        return self.parse_member_expression()

    def parse_postfix_expression(self):
        expression = self.parse_left_hand_side_expression()
        if not self.has_line_terminator_before_next():
            if self.is_count_op(self.peek()):
                op = self.next()
                return ast.PostfixCountOperation(op.value, expression)
        return expression

    def parse_unary_expression(self):
        type = self.peek()
        if self.is_count_op(type):
            op = self.next()
            return ast.PrefixCountOperation(op.value,
                                            self.parse_unary_expression())
        if self.is_unary_op(type):
            op = self.next()
            expression = self.parse_unary_expression()
            if type == TYPEOF:
                return ast.TypeofOperation(expression)
            if type == DELETE:
                return ast.DeleteOperation(expression)
            if type == VOID:
                return ast.VoidOperation(expression)
            return ast.UnaryOperation(op.value, expression)
        return self.parse_postfix_expression()

    def parse_binary_operator_expression(self, lhs, min_precedence=4):
        while self.precedence(self.peek()) >= min_precedence:
            op = self.next()
            precedence = self.precedence(op.type)
            rhs = self.parse_unary_expression()
            next_precedence = self.precedence(self.peek())
            while next_precedence > precedence:
                rhs = self.parse_binary_operator_expression(rhs,
                                                            next_precedence)
                next_precedence = self.precedence(self.peek())
            if self.is_comparison_op(op.type):
                lhs = ast.CompareOperation(op.value, lhs, rhs)
            else:
                lhs = ast.BinaryOperation(op.value, lhs, rhs)
        return lhs

    def parse_assignment_expression(self):
        expression = self.parse_conditional_expression()
        if not self.is_assignment_op(self.peek()):
            return expression
        if not (expression is None
                or self.is_valid_left_hand_side(expression)):
            raise Exception('Invalid assignment')
        op = self.next()
        right = self.parse_assignment_expression()
        return ast.Assignment(op.value, expression, right)

    def parse_conditional_expression(self):
        expression = self.parse_binary_operator_expression(
            self.parse_unary_expression())
        if self.peek() != HOOK:
            return expression
        self.expect(HOOK)
        left = self.parse_assignment_expression()
        self.expect(COLON)
        right = self.parse_assignment_expression()
        return ast.Conditional(expression, left, right)

    def parse_function_expression(self):
        raise Exception('function expressions are not supported')

    def parse_function_body(self):
        raise Exception('function bodies are not supported')

def make_string_parser(string, filename=None, line=0, column=0):
    scanner = make_string_scanner(string, filename, line, column)
    return Parser(TokenStreamAllowReserved(scanner))
