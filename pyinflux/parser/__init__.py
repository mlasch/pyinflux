from functools import reduce

try:
    from funcparserlib.lexer import make_tokenizer
    from funcparserlib.parser import (
        some, maybe, many, finished, skip, NoParseError)
except ImportError as e:
    print("Missing funcparserlib library. You need to install the 'parser' extra dependency set.")
    raise e

from pyinflux import client


def parse_lines(lines: str):
    """
    Parse multiple Write objects separeted by new-line character.
    """
    writes = map(LineParser.parse, lines.split("\n"))
    return list(writes)


class LineTokenizer:
    specs = [
        ('Comma', (r',',)),
        ('Space', (r' ',)),
        ('Equal', (r'=',)),
        ('Quote', (r'"',)),
        ('Escape', (r'\\',)),
        ('Int', (r'[0-9]+(?![0-9\.])',)),
        ('Float', (r'-?(\.[0-9]+)|([0-9]+(\.[0-9]*)?)',)),
        ('Char', (r'.',)),
    ]

    @classmethod
    def tokenize(klass, line: str):
        tokenizer = make_tokenizer(klass.specs)
        return list(tokenizer(line))


class LineParser:
    @staticmethod
    def parse_identifier(line: str):
        """Parses just the identifer (first element) of the write"""
        tokval = lambda t: t.value
        joinval = "".join
        someToken = lambda type: some(lambda t: t.type == type)

        char = someToken('Char') >> tokval
        space = someToken('Space') >> tokval
        comma = someToken('Comma') >> tokval
        quote = someToken('Quote') >> tokval
        escape = someToken('Escape') >> tokval
        equal = someToken('Equal') >> tokval

        escape_space = skip(escape) + space >> joinval
        escape_comma = skip(escape) + comma >> joinval
        escape_equal = skip(escape) + equal >> joinval
        escape_escape = skip(escape) + escape >> joinval

        plain_int_text = someToken('Int') >> tokval
        plain_float_text = someToken('Float') >> tokval

        identifier = many(char | plain_float_text | plain_int_text |
                          escape_space | escape_comma | escape_equal |
                          escape_escape | plain_int_text | quote) >> joinval

        toplevel = identifier >> (lambda x: x)
        parsed =  toplevel.parse(LineTokenizer.tokenize(line))
        if len(parsed) == 0:
            raise NoParseError('parsed nothing')
        else:
            return parsed

    @staticmethod
    def parse(line: str):
        """
        Parse a line from the POST request into a Write object.
        """
        tokval = lambda t: t.value
        joinval = "".join
        someToken = lambda type: some(lambda t: t.type == type)
        someCharValue = lambda string: \
            reduce(lambda a, b: a + b,
                   map(lambda char:
                       some(lambda t: t.value == char) >> tokval,
                       string)) >> joinval

        char = someToken('Char') >> tokval
        space = someToken('Space') >> tokval
        comma = someToken('Comma') >> tokval
        quote = someToken('Quote') >> tokval
        escape = someToken('Escape') >> tokval
        equal = someToken('Equal') >> tokval
        true_value = (someCharValue("true") | someCharValue("t") |
                      someCharValue("True") | someCharValue("TRUE") | someCharValue("T"))
        false_value = (someCharValue("false") | someCharValue("f") |
                       someCharValue("False") | someCharValue("FALSE") | someCharValue("F"))

        escape_space = skip(escape) + space >> joinval
        escape_comma = skip(escape) + comma >> joinval
        escape_equal = skip(escape) + equal >> joinval
        escape_quote = skip(escape) + quote >> joinval
        escape_escape = skip(escape) + escape >> joinval

        plain_int_text = someToken('Int') >> tokval
        plain_int = plain_int_text >> (lambda v: int(v))
        plain_float_text = someToken('Float') >> tokval
        plain_float = plain_float_text >> (lambda v: float(v))

        identifier = many(char | plain_float_text | plain_int_text |
                          escape_space | escape_comma | escape_equal |
                          escape_escape | plain_int_text | quote) >> joinval
        quoted_text_ = many(escape_escape | escape_quote | space |
                            plain_int_text | plain_float_text | char | comma |
                            escape) >> joinval
        quoted_text = skip(quote) + quoted_text_ + skip(quote)
        unquoted_text = many(escape_space | escape_comma |
                             escape_equal | escape_escape |
                             plain_int_text | char | quote) >> joinval
        boolean_value = (true_value >> (lambda s: True)
                         | false_value >> (lambda s: False))

        kv_value = plain_int | plain_float | quoted_text | boolean_value
        kv = (quoted_text | unquoted_text) + skip(equal) + kv_value >> \
             (lambda x: (x[0], x[1]))

        tag = identifier + skip(equal) + identifier >> (lambda x: (x[0], x[1]))

        def setter(obj, property):
            def r(val):
                setattr(obj, property, val)
                return (property, val)

            return r

        tags = many(skip(comma) + tag) >> (lambda x: x)
        fields = (kv + many(skip(comma) + kv)) >> \
                 (lambda x: [x[0]] + x[1])

        write = client.Line(None, None, None, None)
        toplevel = (identifier >> setter(write, "key")) + \
                   maybe(tags >> setter(write, "tags")) + \
                   (skip(space) + (fields >> setter(write, "fields"))) + \
                   maybe(skip(space) + plain_int >> setter(write, "timestamp")) + \
                   skip(finished) >> (lambda x: x)

        result = toplevel.parse(LineTokenizer.tokenize(line))
        # pprint(result)
        return write
