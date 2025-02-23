import unittest
from parsec.core import string, regex, letters, digits, whitespace, lazy

class TestCombinatorialParsing(unittest.TestCase):

    def test_string_parser(self):
        parser = string("hello")
        ctx = parser.parse("hello world")
        self.assertEqual(ctx.position, 5)
        self.assertEqual(ctx.result, "hello")

        ctx = parser.parse("world hello")
        self.assertTrue(ctx.failed)

    def test_regex_parser(self):
        parser = regex(r"\d+")
        ctx = parser.parse("123 abc")
        self.assertEqual(ctx.position, 3)
        self.assertEqual(ctx.result, "123")

        ctx = parser.parse("abc 456")
        self.assertTrue(ctx.failed)

    def test_sequential_parser(self):
        parser = string("hello") & string("world")
        ctx = parser.parse("helloworld")
        self.assertEqual(ctx.position, 10)
        self.assertEqual(ctx.result, ["hello", "world"])

        ctx = parser.parse("hello")
        self.assertTrue(ctx.failed)

    def test_alternating_parser(self):
        parser = regex(r"\d+") | regex(r"[a-zA-Z]+")
        ctx = parser.parse("123")
        self.assertEqual(ctx.position, 3)
        self.assertEqual(ctx.result, "123")

        ctx = parser.parse("abc")
        self.assertEqual(ctx.position, 3)
        self.assertEqual(ctx.result, "abc")

    def test_mapping_parser(self):
        parser = regex(r"\d+").map(int)
        ctx = parser.parse("123")
        self.assertEqual(ctx.position, 3)
        self.assertEqual(ctx.result, 123)

    def test_error_mapping_parser(self):
        parser = regex(r"[a-zA-Z]+").map_err(lambda err, pos: f"Error at {pos}: {err}")
        ctx = parser.parse("123")
        self.assertTrue(ctx.failed)
        self.assertIn("Error at", ctx.error)

    def test_between(self):
        parser = digits().between(string("("), string(")"))
        ctx = parser.parse("(123)")
        self.assertEqual(ctx.position, 5)
        self.assertEqual(ctx.result, "123")

    def test_kleene_parser(self):
        parser = regex(r"\d{3}").many()
        ctx = parser.parse("123456789")
        self.assertEqual(ctx.position, 9)
        self.assertEqual(ctx.result, ["123", "456", "789"])

        parser = regex(r"\d{3}").at_least(2)
        ctx = parser.parse("123456")
        self.assertEqual(ctx.position, 6)
        self.assertEqual(ctx.result, ["123", "456"])

        ctx = parser.parse("123")
        self.assertTrue(ctx.failed)

    def test_letters_parser(self):
        parser = letters()

        ctx = parser.parse("abc")
        self.assertEqual(ctx.position, 3)
        self.assertEqual(ctx.result, "abc")

        ctx = parser.parse("123")
        self.assertTrue(ctx.failed)

    def test_digits_parser(self):
        parser = digits()

        ctx = parser.parse("123")
        self.assertEqual(ctx.position, 3)
        self.assertEqual(ctx.result, "123")

        ctx = parser.parse("abc")
        self.assertTrue(ctx.failed)

    def test_forwarding_parser(self):
        string_parser = letters().map(lambda x: {"type": "string", "value": x})
        ctx = string_parser.parse("hello")
        self.assertEqual(ctx.position, 5)
        self.assertEqual(ctx.result, {"type": "string", "value": "hello"})

        number_parser = digits().map(lambda x: {"type": "number", "value": int(x)})
        ctx = number_parser.parse("42")
        self.assertEqual(ctx.position, 2)
        self.assertEqual(ctx.result, {"type": "number", "value": 42})

        def roll(roll: str):
            values = roll.split("d")
            return (int(values[0]), int(values[1]))

        diceroll_parser = regex(r"\dd\d").map(lambda x: {"type": "diceroll", "value": roll(x)})
        ctx = diceroll_parser.parse("2d8")
        self.assertEqual(ctx.position, 3)
        self.assertEqual(ctx.result, {"type": "diceroll", "value": (2, 8)})

        def router(type: str):
            if type == "string":
                return string_parser
            elif type == "number":
                return number_parser
            elif type == "diceroll":
                return diceroll_parser
            else:
                raise RuntimeError(f"unexpected type '{type}'")
            
        tag_parser = (letters() & string(":")).map(lambda xs: xs[0])
        type_parser = tag_parser.forward(router)

        ctx = type_parser.parse("string:hello")
        self.assertEqual(ctx.position, 12)
        self.assertEqual(ctx.result, {"type": "string", "value": "hello"})

        ctx = type_parser.parse("number:42")
        self.assertEqual(ctx.position, 9)
        self.assertEqual(ctx.result, {"type": "number", "value": 42})

        ctx = type_parser.parse("diceroll:2d8")
        self.assertEqual(ctx.position, 12)
        self.assertEqual(ctx.result, {"type": "diceroll", "value": (2, 8)})

    def test_separated_by(self):
        content_parser = lazy(lambda: digits() | array_parser)
        array_parser = content_parser.separated_by(string(",")).between(string("["), string("]"))
        ctx = array_parser.parse("[1,2,3]")
        self.assertEqual(ctx.position, 7)
        self.assertEqual(ctx.result, ["1","2","3"])

        ctx = array_parser.parse("[1,[2,3],4]")
        self.assertEqual(ctx.position, 11)
        self.assertEqual(ctx.result, ["1",["2","3"],"4"])
        

if __name__ == '__main__':
    unittest.main()
