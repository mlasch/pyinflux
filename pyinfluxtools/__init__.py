#!/usr/bin/env python3
import re
import sys

from funcparserlib.lexer import make_tokenizer
from funcparserlib.parser import (some, maybe, many, finished, skip, NoParseError)


class WriteRequest(object):

    @staticmethod
    def parse(lines):
        """
        Parse multiple Write objects separeted by new-line character.

        >>> print(Write.parse("foo b=1"))
        foo b=1

        >>> lines = []
        >>> lines += ['cpu field=123']
        >>> lines += ['cpu,host=serverA,region=us-west field1=1,field2=2']
        >>> lines += ['cpu,host=serverA,region=us-west field1=1,field2=2 1234']
        >>> print("\\n".join(map(str, WriteRequest.parse("\\n".join(lines)))))
        cpu field=123
        cpu,host="serverA",region="us-west" field1=1,field2=2
        cpu,host="serverA",region="us-west" field1=1,field2=2 1234
        """
        writes = map(Write.parse, lines.split("\n"))
        return list(writes)


class Write(object):

    def __init__(self, key, tags, fields, timestamp=None):
        self.key = key
        self.tags = tags
        self.fields = fields
        self.timestamp = timestamp

        if isinstance(self.tags, dict):
            self.tags = self.tags.items()

        if isinstance(self.fields, dict):
            self.fields = self.fields.items()

    specs = [
        ('Comma', (r',',)),
        ('Space', (r' ',)),
        ('Equal', (r'=',)),
        ('Quote', (r'"',)),
        ('Escape', (r'\\',)),
        ('Int', (r'[0-9]+',)),
        ('Float', (r'-?(\.[0-9]+)|([0-9]+(\.[0-9]*)?)',)),
        ('Char', (r'.',)),
    ]

    @staticmethod
    def tokenize(line):
        tokenizer = make_tokenizer(Write.specs)
        return list(tokenizer(line))

    @staticmethod
    def parse(line):
        """
        Parse a line from the POST request into a Write object.

        >>> Write.parse('cpu a=1')
        <Write key=cpu tags=[] fields=[('a', 1)] timestamp=None>

        >>> print(Write.parse('cpu a=1'))
        cpu a=1

        >>> Write.parse('cpu,host=serverA,region=us-west foo=bar')
        <Write key=cpu tags=[('host', 'serverA'), ('region', 'us-west')] fields=[('foo', 'bar')] timestamp=None>

        >>> print(Write.parse('cpu host=serverA,region=us-west'))
        cpu host="serverA",region="us-west"

        >>> Write.parse('cpu\\,01 host=serverA,region=us-west')
        <Write key=cpu,01 tags=[] fields=[('host', 'serverA'), ('region', 'us-west')] timestamp=None>

        >>> print(Write.parse('cpu\,01 host=serverA,region=us-west'))
        cpu\,01 host="serverA",region="us-west"

        >>> Write.parse('cpu host=server\\ A,region=us\\ west')
        <Write key=cpu tags=[] fields=[('host', 'server A'), ('region', 'us west')] timestamp=None>

        >>> Write.parse('cpu ho\\=st=server\ A,region=us\ west')
        <Write key=cpu tags=[] fields=[('ho=st', 'server A'), ('region', 'us west')] timestamp=None>

        >>> print(Write.parse('cpu ho\=st=server\ A,region=us\ west'))
        cpu ho\=st="server A",region="us west"

        >>> print(Write.parse('cpu,ho\=st=server\ A field=123'))
        cpu,ho\=st="server A" field=123

        >>> print(Write.parse('cpu,foo=bar,foo=bar field=123,field=123')) # error: double name is accepted
        cpu,foo="bar",foo="bar" field=123,field=123

        >>> print(Write.parse('cpu field12=12'))
        cpu field12=12

        >>> print(Write.parse('cpu field12=12 123123123'))
        cpu field12=12 123123123

        >>> try:
        ...     print(Write.parse('cpu field12=12 1231abcdef123'))
        ... except NoParseError:
        ...     pass

        >>> print(Write.parse("cpu,x=3,y=4,z=6 field\ name=\\"HH \\\\\\"World\\",x=asdf\\\\ foo"))
        cpu,x=3,y=4,z=6 field\\ name="HH \\"World",x="asdf foo"

        >>> print(Write.parse("cpu,x=3 field\ name=\\"HH \\\\\\"World\\",x=asdf\\\\ foo"))
        cpu,x=3 field\\ name="HH \\"World",x="asdf foo"

        >>> print(Write.parse("cpu foo=bar 12345"))
        cpu foo="bar" 12345

        >>> print(Write.parse('"measurement\ with\ quotes",tag\ key\ with\ spaces=tag\,value\,with field_key\\\\\\="string field value, only \\\\" need be quoted"'))
        "measurement\ with\ quotes",tag\ key\ with\ spaces="tag,value,with" field_key\\\\="string field value, only \\" need be quoted"

        >>> Write.parse('"measurement\ with\ quotes",tag\ key\ with\ spaces=tag\,value\,with"commas" field_key\\\\\\\\="string field value, only \\\\" need be quoted"')
        <Write key="measurement with quotes" tags=[('tag key with spaces', 'tag,value,with"commas"')] fields=[('field_key\\\\', 'string field value, only " need be quoted')] timestamp=None>

        >>> Write.parse('disk_free value=442221834240,working\ directories="C:\My Documents\Stuff for examples,C:\My Documents"')
        <Write key=disk_free tags=[] fields=[('value', 442221834240), ('working directories', 'C:\\\\My Documents\\\\Stuff for examples,C:\\\\My Documents')] timestamp=None>

        >>> Write.parse('disk_free value=442221834240,working\ directories="C:\My Documents\Stuff for examples,C:\My Documents" 123')
        <Write key=disk_free tags=[] fields=[('value', 442221834240), ('working directories', 'C:\\\\My Documents\\\\Stuff for examples,C:\\\\My Documents')] timestamp=123>

        >>> print(Write.parse('foo,foo=2 field_key\\\\\\="string field"'))
        foo,foo=2 field_key\\\\="string field"

        >>> print(Write.parse('foo,foo=2 field_key="string\\\\" field"'))
        foo,foo=2 field_key="string\\" field"

        >>> print(Write.parse('foo field0=tag,field1=t,field2=true,field3=True,field4=TRUE'))
        foo field0="tag",field1=True,field2=True,field3=True,field4=True

        >>> print(Write.parse('foo field1=f,field2=false,field3=False,field4=FALSE,field5=fag'))
        foo field1=False,field2=False,field3=False,field4=False,field5="fag"

        >>> print(Write.parse('"measurement\ with\ quotes",tag\ key\ with\ spaces=tag\,value\,with"commas" field_key\\\\\\="string field value, only \\\\" need be quoted"'))
        "measurement\ with\ quotes",tag\ key\ with\ spaces="tag,value,with\\"commas\\"" field_key\\\\="string field value, only \\" need be quoted"

        >>> Write.parse('"measurement\ with\ quotes" foo=1')
        <Write key="measurement with quotes" tags=[] fields=[('foo', 1)] timestamp=None>
        """

        tokval = lambda t: t.value
        joinval = "".join
        someToken = lambda type: some(lambda t: t.type == type)
        true_values = ["t", "true", "True", "TRUE"]
        false_values = ["f", "false", "False", "FALSE"]

        char = someToken('Char') >> tokval
        space = someToken('Space') >> tokval
        comma = someToken('Comma') >> tokval
        quote = someToken('Quote') >> tokval
        escape = someToken('Escape') >> tokval
        equal = someToken('Equal') >> tokval

        escape_space = skip(escape) + space >> joinval
        escape_comma = skip(escape) + comma >> joinval
        escape_equal = skip(escape) + equal >> joinval
        escape_quote = skip(escape) + quote >> joinval
        escape_escape = skip(escape) + escape >> joinval

        plain_int_text = someToken('Int') >> tokval
        plain_int = plain_int_text >> (lambda v: int(v))
        plain_float_text = someToken('Float') >> tokval
        plain_float = plain_float_text >> (lambda v: float(v))

        identifier = many(char | escape_space | escape_comma |
                          escape_escape | plain_int_text | quote) >> joinval
        quoted_text_ = many(escape_quote | space | plain_int_text |
                            plain_float_text | char | comma |
                            escape) >> joinval
        quoted_text = skip(quote) + quoted_text_ + skip(quote)
        unquoted_text = many(escape_space | escape_comma |
                             escape_equal | escape_escape |
                             plain_int_text | char | quote) >> joinval
        string_value = quoted_text | unquoted_text >> \
            (lambda s: s in true_values and True
             or s in false_values and False
             or s not in false_values and s)

        kv_value = plain_int | plain_float | string_value
        kv = string_value + \
            skip(equal) + kv_value >> (lambda x: (x[0], x[1]))

        def setter(obj, propert):
            def r(val):
                setattr(obj, propert, val)
                return (propert, val)
            return r

        tags = many(skip(comma) + kv) >> (lambda x: x)
        fields = (kv + many(skip(comma) + kv)) >> \
                 (lambda x: [x[0]] + x[1])

        write = Write(None, None, None, None)
        toplevel = (identifier >> setter(write, "key")) + \
            maybe(tags >> setter(write, "tags")) + \
            (skip(space) + (fields >> setter(write, "fields"))) + \
            maybe(skip(space) + plain_int >> setter(write, "timestamp")) + \
            skip(finished) >> (lambda x: x)

        result = toplevel.parse(Write.tokenize(line))
        #pprint(result)
        return write

    def __repr__(self):
        return "<{} key={} tags={} fields={} timestamp={}>".format(
            self.__class__.__name__, self.key, self.tags, self.fields, self.timestamp)

    def __str__(self):
        def escape_key(string):
            return re.sub(r'([\\,= ])', '\\\\\\1', string)

        def escape_value(obj):
            if isinstance(obj, float) or isinstance(obj, int) or isinstance(obj, bool):
                return str(obj)
            else:
                obj = str(obj)
                return "\"" + obj.replace("\"", "\\\"") + "\""

        def escape_kv(kvlist):
            return ",".join(
                map(lambda kv: escape_key(kv[0]) + "=" + escape_value(kv[1]),
                    kvlist))

        result = escape_key(self.key)

        if self.tags:
            result += ","
            result += escape_kv(self.tags)

        if self.fields:
            result += " "
            result += escape_kv(self.fields)

        if self.timestamp:
            result += " "
            result += str(self.timestamp)

        return result


if __name__ == "__main__":
    import doctest
    doctest.testmod()
