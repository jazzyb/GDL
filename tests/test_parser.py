import unittest
from gdl import Parser, ParseError


class MockToken(object):
    def __init__(self, filename, line, lineno, col, token):
        self.token = token
        self.filename = filename
        self.line = line
        self.lineno = lineno,
        self.column = col

    def is_open(self):
        return self.token == '('

    def is_close(self):
        return self.token == ')'

    def is_variable(self):
        return self.token[0] == '?'

    def is_constant(self):
        return self.token[0] not in ('?', '(', ')')


class TestParser(unittest.TestCase):
    def test_parse_tokens(self):
        tokens = ['(', '<=', '(', 'ancestor', '?a', '?c', ')', '(', 'parent', '?a', '?b', ')', '(', 'ancestor', '?b', '?c', ')', ')']
        self.tokens = [MockToken(None, None, None, None, t) for t in tokens]
        ast_head = Parser().parse(self.tokens)
        self.assertEqual('<=', ast_head.children[0].token.token)
        self.assertEqual(1, len(ast_head.children))
        tokens = [c.token.token for c in ast_head.children[0].children]
        self.assertEqual(['ancestor', 'parent', 'ancestor'], tokens)
        tokens = [c.token.token for c in ast_head.children[0].children[0].children]
        self.assertEqual(['?a', '?c'], tokens)
        tokens = [c.token.token for c in ast_head.children[0].children[1].children]
        self.assertEqual(['?a', '?b'], tokens)
        tokens = [c.token.token for c in ast_head.children[0].children[2].children]
        self.assertEqual(['?b', '?c'], tokens)

    def test_constant_expected_parse_error(self):
        errmsg = '''A constant was expected.
22: (f a ?x (g ( (h c ?y) e)))
                 ^'''
        line = '(f a ?x (g ( (h c ?y) e)))'
        tokens = [('(', 1),
                  ('f', 2),
                  ('a', 4),
                  ('?x', 6),
                  ('(', 9),
                  ('g', 10),
                  ('(', 12),
                  ('(', 14)]
        bad_tokens = [MockToken('test.gdl', line, 22, y, x) for x, y in tokens]
        with self.assertRaises(ParseError) as cm:
            Parser().parse(bad_tokens)
        self.assertEqual(str(cm.exception), errmsg)

    def test_unexpected_closed_parse_error(self):
        errmsg = '''Unexpected closed parenthesis.
22: (f a ?x))
            ^'''
        line = '(f a ?x))'
        tokens = [('(', 1),
                  ('f', 2),
                  ('a', 4),
                  ('?x', 6),
                  (')', 8),
                  (')', 9)]
        bad_tokens = [MockToken('test.gdl', line, 22, y, x) for x, y in tokens]
        with self.assertRaises(ParseError) as cm:
            Parser().parse(bad_tokens)
        self.assertEqual(str(cm.exception), errmsg)
