from functools import reduce

try:
    from funcparserlib.lexer import make_tokenizer
    from funcparserlib.parser import (
        some, maybe, many, finished, skip, NoParseError)
except ImportError as e:
    print("Missing funcparserlib library. You need to install the 'parser' extra dependency set.")
    raise e

from pyinflux import client


def parse_lines(lines):
    """
    Parse multiple Write objects separeted by new-line character.

    >>> print(LineParser.parse("foo b=1"))
    foo b=1

    >>> lines = []
    >>> lines += ['cpu field=123']
    >>> lines += ['cpu,host=serverA,region=us-west field1=1,field2=2']
    >>> lines += ['cpu,host=serverA,region=us-west field1=1,field2=2 1234']
    >>> print("\\n".join(map(str, parse_lines("\\n".join(lines)))))
    cpu field=123
    cpu,host=serverA,region=us-west field1=1,field2=2
    cpu,host=serverA,region=us-west field1=1,field2=2 1234
    """
    writes = map(LineParser.parse, lines.split("\n"))
    return list(writes)


class LineParser(object):
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
    def tokenize(klass, line : str):
        tokenizer = make_tokenizer(klass.specs)
        return list(tokenizer(line))

    @staticmethod
    def parse(line):
        """
        Parse a line from the POST request into a Write object.

        >>> line='cpu a=1'; LineParser.parse(line); print(LineParser.parse(line))
        <Line key=cpu tags=[] fields=[('a', 1)] timestamp=None>
        cpu a=1

        >>> print(LineParser.parse('yahoo.CHFGBP\\=X.ask,tag=foobar value=10.2'))
        yahoo.CHFGBP\=X.ask,tag=foobar value=10.2

        >>> LineParser.parse('cpu,host=serverA,region=us-west foo="bar"')
        <Line key=cpu tags=[('host', 'serverA'), ('region', 'us-west')] fields=[('foo', 'bar')] timestamp=None>

        >>> print(LineParser.parse('cpu host="serverA",region="us-west"'))
        cpu host="serverA",region="us-west"

        >>> line='cpu\\,01 host="serverA",region="us-west"'; \\
        ... LineParser.parse(line); print(LineParser.parse(line))
        <Line key=cpu,01 tags=[] fields=[('host', 'serverA'), ('region', 'us-west')] timestamp=None>
        cpu\,01 host="serverA",region="us-west"

        >>> LineParser.parse('cpu host="server A",region="us west"')
        <Line key=cpu tags=[] fields=[('host', 'server A'), ('region', 'us west')] timestamp=None>

        >>> line='cpu ho\\=st="server A",region="us west"'; \\
        ... LineParser.parse(line); print(LineParser.parse(line))
        <Line key=cpu tags=[] fields=[('ho=st', 'server A'), ('region', 'us west')] timestamp=None>
        cpu ho\=st="server A",region="us west"

        >>> print(LineParser.parse('cpu,ho\=st=server\ A field=123'))
        cpu,ho\=st=server\ A field=123

        # error: double name is accepted
        >>> print(LineParser.parse('cpu,foo=bar,foo=bar field=123,field=123'))
        cpu,foo=bar,foo=bar field=123,field=123

        >>> print(LineParser.parse('cpu field12=12'))
        cpu field12=12

        >>> print(LineParser.parse('cpu field12=12 123123123'))
        cpu field12=12 123123123

        >>> try: print(LineParser.parse('cpu field12=12 1231abcdef123'))
        ... except NoParseError: pass

        >>> print(LineParser.parse('cpu,x=3,y=4,z=6 field\ name="HH \\\\\\"World",x="asdf foo"'))
        cpu,x=3,y=4,z=6 field\\ name="HH \\"World",x="asdf foo"

        >>> print(LineParser.parse("cpu,x=3 field\ name=\\"HH \\\\\\"World\\",x=\\"asdf foo\\""))
        cpu,x=3 field\\ name="HH \\"World",x="asdf foo"

        >>> print(LineParser.parse("cpu foo=\\"bar\\" 12345"))
        cpu foo="bar" 12345

        >>> line='"measurement\ with\ quotes",tag\ key\ with\ spaces=tag\,value\,with"commas" field_key\\\\\\="string field value, only \\\\" need be quoted"'; \\
        ... LineParser.parse(line); print(LineParser.parse(line))
        <Line key="measurement with quotes" tags=[('tag key with spaces', 'tag,value,with"commas"')] fields=[('field_key\\\\', 'string field value, only " need be quoted')] timestamp=None>
        "measurement\ with\ quotes",tag\ key\ with\ spaces=tag\,value\,with"commas" field_key\\\\="string field value, only \\\" need be quoted"

        >>> LineParser.parse('disk_free value=442221834240,working\ directories="C:\My Documents\Stuff for examples,C:\My Documents"')
        <Line key=disk_free tags=[] fields=[('value', 442221834240), ('working directories', 'C:\\\\My Documents\\\\Stuff for examples,C:\\\\My Documents')] timestamp=None>

        >>> LineParser.parse('disk_free value=442221834240,working\ directories="C:\My Documents\Stuff for examples,C:\My Documents" 123')
        <Line key=disk_free tags=[] fields=[('value', 442221834240), ('working directories', 'C:\\\\My Documents\\\\Stuff for examples,C:\\\\My Documents')] timestamp=123>

        >>> print(LineParser.parse('foo,foo=2 "field key with space"="string field"'))
        foo,foo=2 field\ key\ with\ space="string field"

        >>> print(LineParser.parse('foo,foo=2 field_key\\\\\\="string field"'))
        foo,foo=2 field_key\\\\="string field"

        >>> print(LineParser.parse('foo,foo=2 field_key="string\\\\" field"'))
        foo,foo=2 field_key="string\\" field"

        >>> line='foo field0="tag",field1=t,field2=true,field3=True,field4=TRUE'; \\
        ... LineParser.parse(line); print(LineParser.parse(line))
        <Line key=foo tags=[] fields=[('field0', 'tag'), ('field1', True), ('field2', True), ('field3', True), ('field4', True)] timestamp=None>
        foo field0="tag",field1=True,field2=True,field3=True,field4=True

        >>> line='foo field1=f,field2=false,field3=False,field4=FALSE,field5="fag"'; \\
        ... LineParser.parse(line); print(LineParser.parse(line))
        <Line key=foo tags=[] fields=[('field1', False), ('field2', False), ('field3', False), ('field4', False), ('field5', 'fag')] timestamp=None>
        foo field1=False,field2=False,field3=False,field4=False,field5="fag"

        >>> line='"measurement\ with\ quotes",tag\ key\ with\ spaces=tag\,value\,with"commas" field_key\\\\\\="string field value, only \\\\" need be quoted"'; \\
        ... LineParser.parse(line); print(LineParser.parse(line))
        <Line key="measurement with quotes" tags=[('tag key with spaces', 'tag,value,with"commas"')] fields=[('field_key\\\\', 'string field value, only " need be quoted')] timestamp=None>
        "measurement\ with\ quotes",tag\ key\ with\ spaces=tag\,value\,with"commas" field_key\\\\="string field value, only \\" need be quoted"

        >>> LineParser.parse('"measurement\ with\ quotes" foo=1')
        <Line key="measurement with quotes" tags=[] fields=[('foo', 1)] timestamp=None>

        >>> print(LineParser.parse('K.5S,Ccpvo="eSLyE" value="7F\\\\\\\\\\\\""'))
        K.5S,Ccpvo="eSLyE" value="7F\\\\\\\\\\\""

        >>> print(LineParser.parse('K.5S,Ccpvo=a\\ b value=1'))
        K.5S,Ccpvo=a\\ b value=1
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
        quoted_text_ = many(escape_quote | space | plain_int_text |
                            plain_float_text | char | comma |
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

        def setter(obj, propert):
            def r(val):
                setattr(obj, propert, val)
                return (propert, val)

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

        result = toplevel.parse(LineParser.tokenize(line))
        # pprint(result)
        return write
