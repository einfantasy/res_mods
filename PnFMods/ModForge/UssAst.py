# coding=utf-8

STATIC_ALIASES = {}
requestedPropsKeys = [u'$root']

class Node(object):
    def makeCode(self, caller):
        raise Exception('%s has no AS3 form' % self.__class__.__name__)

    def makePropSet(self, propsSet, rootPropsSet):
        return propsSet

    def is_valid_left_hand_side(self):
        return False

    def _getPropertyOrCall(self, propertyName, methodName):
        attr = getattr(self, propertyName)
        if hasattr(attr, methodName):
            return getattr(attr, methodName)(self)
        return attr

    def _propSetAdd(self, propsSet, rootPropsSet, propertyName):
        attr = getattr(self, propertyName)
        if hasattr(attr, 'makePropSet'):
            attr.makePropSet(propsSet, rootPropsSet)
        else:
            propsSet.add(attr)
            rootPropsSet.add(attr)

class Name(Node):
    def __init__(self, value):
        self.value = value

    def is_valid_left_hand_side(self):
        return True

    def makeCode(self, caller):
        prefix = u"'"
        postfix = u"'"
        if not isinstance(caller, PropertyAccess):
            prefix = u'scope.'
            postfix = u''
        if isinstance(caller, DotProperty) and caller.isConstantExpression:
            if caller.isConstantToValidate:
                return STATIC_ALIASES.get(self.value, self.value)
            return self.value
        return prefix + self.value + postfix

    def makePropSet(self, propsSet, rootPropsSet):
        propsSet.add(self.value)
        rootPropsSet.add(self.value)

class NullNode(Node):
    def makeCode(self, caller):
        return u'null'

class TrueNode(Node):
    def makeCode(self, caller):
        return u'true'

class FalseNode(Node):
    def makeCode(self, caller):
        return u'false'

class ThisNode(Node):
    def makeCode(self, caller):
        return u'this'

class StringLiteral(Node):
    def __init__(self, value):
        self.value = value

    def makeCode(self, caller):
        return self.value

class NumberLiteral(Node):
    def __init__(self, value):
        self.value = value

    def makeCode(self, caller):
        return self.value

class PropertyName(Node):
    def __init__(self, value):
        self.value = value

    def makeCode(self, caller):
        return self.value

class ObjectProperty(Node):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def makeCode(self, caller):
        return (self._getPropertyOrCall('name', 'makeCode') + u': '
                + self.value.makeCode(self))

    def makePropSet(self, propsSet, rootPropsSet):
        self._propSetAdd(propsSet, rootPropsSet, 'name')
        self.value.makePropSet(propsSet, rootPropsSet)

class ObjectLiteral(Node):
    def __init__(self, properties):
        self.properties = properties

    def makeCode(self, caller):
        s = u'{'
        for p in self.properties:
            if s != u'{':
                s += u', '
            s += p.makeCode(self)
        return s + u'}'

    def makePropSet(self, propsSet, rootPropsSet):
        for p in self.properties:
            p.makePropSet(propsSet, rootPropsSet)

class ArrayLiteral(Node):
    def __init__(self, elements):
        self.elements = elements

    def makeCode(self, caller):
        s = u'['
        for p in self.elements:
            if s != u'[':
                s += u', '
            if hasattr(p, 'makeCode'):
                ocode = p.makeCode(self)
            else:
                ocode = p
            s += ocode
        return s + u']'

    def makePropSet(self, propsSet, rootPropsSet):
        for p in self.elements:
            if hasattr(p, 'makePropSet'):
                p.makePropSet(propsSet, rootPropsSet)
            else:
                propsSet.add(p)
                rootPropsSet.add(p)

class Elision(Node):
    pass

class RegExpLiteral(Node):
    def __init__(self, pattern, flags):
        self.pattern = pattern
        self.flags = flags

    def makeCode(self, caller):
        return u'%s%s' % (self.pattern, self.flags)

class PropertyAccess(Node):
    def is_valid_left_hand_side(self):
        return True

    def makePropSet(self, propsSet, rootPropsSet):
        self._propSetAdd(propsSet, rootPropsSet, 'object')
        self._propSetAdd(propsSet, rootPropsSet, 'key')

    def _propSetAdd(self, propsSet, rootPropsSet, propertyName):
        attr = getattr(self, propertyName)
        if hasattr(attr, 'makePropSet'):
            attr.makePropSet(propsSet, rootPropsSet)
        else:
            if len(propsSet) == 0 or all(
                    [p in requestedPropsKeys for p in propsSet]):
                propsSet.add(attr)

class DotProperty(PropertyAccess):
    def __init__(self, object, key, isConstantExpression, isConstantToValidate):
        self.object = object
        self.key = key
        self.isConstantExpression = isConstantExpression
        self.isConstantToValidate = isConstantToValidate

    def makeCode(self, caller):
        prefix = u''
        postfix = u''
        if self.isConstantExpression:
            if not isinstance(caller, PropertyAccess):
                if self.isConstantToValidate:
                    prefix = u''
                    postfix = u''
                else:
                    prefix = u'scope.'
                    postfix = u''
            ocode = self._codeOf('object', self)
            mcode = self._codeOf('key', self)
            return u'%s%s.%s%s' % (prefix, ocode, mcode, postfix)
        if not isinstance(caller, PropertyAccess):
            prefix = u'scope.getPropertySecure('
            postfix = u')'
        ocode = self._codeOf('object', self)
        if hasattr(self.key, 'makeCode'):
            mcode = self.key.makeCode(self)
        else:
            mcode = u"'" + self.key + u"'"
        return u'%s%s,%s%s' % (prefix, ocode, mcode, postfix)

    def _codeOf(self, propertyName, caller):
        attr = getattr(self, propertyName)
        if hasattr(attr, 'makeCode'):
            return attr.makeCode(caller)
        return attr

class BracketProperty(PropertyAccess):
    def __init__(self, object, key, isConstantExpression, isConstantToValidate):
        self.object = object
        self.key = key
        self.isConstantExpression = isConstantExpression
        self.isConstantToValidate = isConstantToValidate

    def makeCode(self, caller):
        prefix = u''
        postfix = u''
        if self.isConstantExpression:
            if not isinstance(caller, PropertyAccess):
                if self.isConstantToValidate:
                    prefix = u''
                else:
                    prefix = u'scope.'
            else:
                prefix = u''
            mcode = self._keyCode()
            return u'%s%s[%s]' % (
                prefix, self._getPropertyOrCall('object', 'makeCode'), mcode)
        if not isinstance(caller, PropertyAccess):
            prefix = u'scope.getPropertySecure('
            postfix = u')'
        mcode = self._keyCode()
        return u'%s%s,%s%s' % (
            prefix, self._getPropertyOrCall('object', 'makeCode'), mcode,
            postfix)

    def _keyCode(self):
        if hasattr(self.key, 'makeCode'):
            return self.key.makeCode(None)
        return self.key

class CallExpression(Node):
    def __init__(self, expression, arguments, isConstantExpression,
                 isConstantToValidate):
        self.expression = expression
        self.arguments = arguments
        self.isConstantExpression = isConstantExpression
        self.isConstantToValidate = isConstantToValidate

    def makeCode(self, caller):
        result = u'scope.callFunctionSecure(' + self.expression.makeCode(self)
        for s in self.arguments:
            result += u', '
            result += s.makeCode(self)
        return result + u')'

    def makePropSet(self, propsSet, rootPropsSet):
        self.expression.makePropSet(propsSet, rootPropsSet)
        for s in self.arguments:
            s.makePropSet(propsSet, rootPropsSet)

class NewExpression(Node):
    def __init__(self, expression, arguments):
        self.expression = expression
        self.arguments = arguments

class UnaryOperation(Node):
    def __init__(self, op, expression):
        self.op = op
        self.expression = expression

    def makeCode(self, caller):
        return (self._getPropertyOrCall('op', 'makeCode')
                + self._getPropertyOrCall('expression', 'makeCode'))

    def makePropSet(self, propsSet, rootPropsSet):
        self._propSetAdd(propsSet, rootPropsSet, 'expression')

class TypeofOperation(Node):
    def __init__(self, expression):
        self.expression = expression

class DeleteOperation(Node):
    def __init__(self, expression):
        self.expression = expression

class VoidOperation(Node):
    def __init__(self, expression):
        self.expression = expression

class PrefixCountOperation(Node):
    def __init__(self, op, expression):
        self.op = op
        self.expression = expression

class PostfixCountOperation(Node):
    def __init__(self, op, expression):
        self.op = op
        self.expression = expression

BOOLEAN_OPS = (u'&&', u'<', u'>', u'<=', u'>=')

class BinaryOperation(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

    def makeCode(self, caller):
        boolean = u''
        if self.op in BOOLEAN_OPS:
            boolean = u'Boolean'
        return (boolean + u'(' + self._getPropertyOrCall('left', 'makeCode')
                + u' ' + self._getPropertyOrCall('op', 'makeCode') + u' '
                + self._getPropertyOrCall('right', 'makeCode') + u')')

    def makePropSet(self, propsSet, rootPropsSet):
        self._propSetAdd(propsSet, rootPropsSet, 'left')
        self._propSetAdd(propsSet, rootPropsSet, 'right')

class CompareOperation(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

    def makeCode(self, caller):
        if self.op == u'in':
            return (u'scope.isInSecure('
                    + self._getPropertyOrCall('left', 'makeCode') + u' , '
                    + self._getPropertyOrCall('right', 'makeCode') + u')')
        return (u'Boolean(' + self._getPropertyOrCall('left', 'makeCode')
                + u' ' + self._getPropertyOrCall('op', 'makeCode') + u' '
                + self._getPropertyOrCall('right', 'makeCode') + u')')

    def makePropSet(self, propsSet, rootPropsSet):
        self._propSetAdd(propsSet, rootPropsSet, 'left')
        self._propSetAdd(propsSet, rootPropsSet, 'right')

class Conditional(Node):
    def __init__(self, condition, then_expression, else_expression):
        self.condition = condition
        self.then_expression = then_expression
        self.else_expression = else_expression

    def makeCode(self, caller):
        return (u'((' + self._getPropertyOrCall('condition', 'makeCode')
                + u') ? (' + self._getPropertyOrCall('then_expression',
                                                     'makeCode')
                + u') : (' + self._getPropertyOrCall('else_expression',
                                                     'makeCode') + u'))')

    def makePropSet(self, propsSet, rootPropsSet):
        self._propSetAdd(propsSet, rootPropsSet, 'condition')
        self._propSetAdd(propsSet, rootPropsSet, 'then_expression')
        self._propSetAdd(propsSet, rootPropsSet, 'else_expression')

class Assignment(Node):
    def __init__(self, op, target, value):
        self.op = op
        self.target = target
        self.value = value

class PropertyGetter(Node):
    def __init__(self, name, body):
        self.name = name
        self.body = body

class PropertySetter(Node):
    def __init__(self, name, parameter, body):
        self.name = name
        self.parameter = parameter
        self.body = body
