#!/usr/bin/env python3
import re
import sys

from pprint import pprint
from funcparserlib.lexer import make_tokenizer, Token, LexerError
from funcparserlib.parser import (some, a, maybe, many, finished, skip)




class WriteRequest(object):
    @staticmethod
    def parse(lines):
        """
        Parse multiple Write objects separeted by new-line character.

        >> lines = []
        >> lines += ['cpu']
        >> lines += ['cpu,host=serverA,region=us-west']
        >> lines += ['cpu,host=serverA,region=us-west field1=1,field2=2']
        >> lines += ['cpu,host=serverA,region=us-west field1=1,field2=2 1234']
        >> print("\\n".join(map(str, WriteRequest.parse("\\n".join(lines)))))
        cpu
        cpu,host="serverA",region="us-west"
        cpu,host="serverA",region="us-west" field1=1,field2=2
        cpu,host="serverA",region="us-west" field1=1,field2=2 1234
        """
        writes = map(Write.parse, lines.split("\n"))
        return list(writes)

    @staticmethod
    def parseFile(file):
        for line in file.readlines():
            yield Write.parse(line)


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

    @staticmethod
    def tokenize(str):
        specs = [ 
            ('Comma', (r',',)),
            ('Space', (r' ',)),
            ('Equal', (r'=',)),
            ('Quote', (r'"',)),
            ('Escape', (r'\\',)),
            ('Int', (r'[0-9]+',)),
            ('Float', (r'-?(\.[0-9]+)|([0-9]+(\.[0-9]*)?)',)),
            ('Text', (r'[A-Za-z\200-\377_0-9-\.]+',)),
        ]   
        useless = [] #'Comma', 'NL', 'Space', 'Header', 'Footer']
        t = make_tokenizer(specs)
        return [x for x in t(str) if x.type not in useless]


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

        >>> Write.parse('cpu ho\=st=server\ A,region=us\ west')
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

        >> print(Write.parse('cpu field12=12 1231abcdef123'))
        Traceback (most recent call last):
        ...
        funcparserlib.parser.NoParseError: should have reached <EOF>: 1,20-1,28: Text 'abcdef123'

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

        #>>> Write.parse('disk_free value=442221834240,working\ directories="C:\My Documents\Stuff for examples,C:\My Documents"')
        #Fails....  this format is just crazy
        """

        tokval = lambda t: t.value
        toksval = lambda x: "".join(x)
        token = lambda type: some(lambda t: t.type == type)
   
        space = token('Space') >> tokval
        comma = token('Comma') >> tokval
        quote = token('Quote') >> tokval
        escape_space = token('Escape') + token('Space') >> (lambda x: " ")
        escape_comma = token('Escape') + token('Comma') >> (lambda x: ",")
        escape_equal = token('Escape') + token('Equal') >> (lambda x: "=")
        escape_quote = token('Escape') + token('Quote') >> (lambda x: "\"")
        escape_escape = token('Escape') + token('Escape') >> (lambda x: "\\")
        plain_int = token('Int') >> (lambda t: int(tokval(t)))
        plain_int_text =  token('Int') >> tokval
        plain_float = token('Float') >> (lambda t: float(tokval(t)))
        plain_float_text = token('Float') >> tokval
        plain_bool = some( lambda t: t.type == 'Text' and t.value.lower() in ["t", "true"]) >> (lambda t: True) | \
                     some( lambda t: t.type == 'Text' and t.value.lower() in ["f", "false"]) >> (lambda t: False)
        plain_text = token("Text") >> tokval

        identifier = many( plain_text | escape_space | escape_comma | escape_escape | plain_int_text | token('Quote') >> tokval ) >> toksval
        quoted_text = many( escape_escape | escape_quote | plain_text | space | comma | plain_int_text | plain_float_text) >> (lambda x: "".join(x))
        unquoted_text = many( escape_space | escape_comma | escape_equal | escape_escape | quote | plain_text |  plain_int_text ) >> toksval
        string_value = ( skip(token('Quote')) + quoted_text + skip(token('Quote')) ) | unquoted_text

        kv_value = plain_int | plain_float | plain_bool | string_value
        kv = string_value + skip(token('Equal')) + kv_value >> (lambda x: (x[0],x[1]))

        def setter(obj, propert):
            def r(val):
                setattr(obj, propert, val)
                return (propert, val)
            return r

        key = identifier
        tags = many( skip(token('Comma')) + kv) >> (lambda x: x) # (lambda x: [x[0]] + x[1])
        fields = ( kv + many( skip(token('Comma')) + kv ) ) >> (lambda x: [x[0]] + x[1])
        timestamp = plain_int

        write = Write(None, None, None, None)
        toplevel = (key >> setter(write, "key")) + \
                    maybe( tags >> setter(write, "tags") ) + \
                        ( skip(token('Space')) + (fields >> setter(write, "fields")) ) + \
                             maybe( skip(token('Space')) + timestamp >> setter(write, "timestamp") ) + \
                                skip(finished) >> (lambda x: x)
        try:
            result = toplevel.parse(Write.tokenize(line))
        except:
            pprint(line, stream=sys.stderr)
            pprint(write, stream=sys.stderr)
            pprint(Write.tokenize(line), stream=sys.stderr)
            raise
        #pprint({line : result}, stream=sys.stderr)
        return write

        def unescape(string):
            return re.sub(r'(?<!\\)([\\,=])', '', string)

        def unescape_value(string):
            if string.startswith("\"") and string.endswith("\""):
                string = re.sub(r'(?<!\\)(["])', '', string)
            else:
                string = unescape(string)
                if re.match("^[0-9]+$", string):
                    return int(string)
                elif re.match("^[0-9]*\.[0-9]*$", string):
                    return float(string)
                elif string.lower() in ["t", "true", "f", "false"]:
                    return string.lower in ["t", "true"]
                else:
                    return string

        args = re.split(r"(?<!\\) ", line)
        key, *tags = re.split(r"(?<!\\),", args[0])
        key = unescape(key)

        if tags:
            tags = map(lambda tag: re.split(r"(?<!\\)=", tag), tags)
            tags = map(lambda tag: (unescape(tag[0]), unescape_value(tag[1])), tags)
            tags = list(tags)
        else:
            tags = None

        if len(args) > 1:
            fields = re.split(r"(?<!\\),",  args[1])
            fields = map(lambda field: re.split(r"(?<!\\)=", field), fields)
            fields = map(lambda field: (unescape(field[0]), unescape_value(field[1])), fields)
            fields = list(fields)
        else:
            fields = None

        if len(args) > 2:
            timestamp = int(args[2])
        else:
            timestamp = None

        return Write(key, tags, fields, timestamp)

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
                return "\"" + obj.replace("\"","\\\"") + "\""


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

