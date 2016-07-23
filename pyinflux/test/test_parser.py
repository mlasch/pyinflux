from unittest import TestCase
from pyinflux.parser import LineTokenizer, LineParser, parse_lines
from pyinflux.client import Line
from funcparserlib.lexer import Token
from funcparserlib.parser import NoParseError


class TestTokenize(TestCase):
    def test_tokenize(self):
        self.assertEqual(LineTokenizer.tokenize("cpu,host=serverA,region=us-west field1=1,field2=2"),
                         [Token('Char', 'c'), Token('Char', 'p'), Token('Char', 'u'), Token('Comma', ','),
                          Token('Char', 'h'), Token('Char', 'o'), Token('Char', 's'), Token('Char', 't'),
                          Token('Equal', '='), Token('Char', 's'), Token('Char', 'e'), Token('Char', 'r'),
                          Token('Char', 'v'), Token('Char', 'e'), Token('Char', 'r'), Token('Char', 'A'),
                          Token('Comma', ','), Token('Char', 'r'), Token('Char', 'e'), Token('Char', 'g'),
                          Token('Char', 'i'), Token('Char', 'o'), Token('Char', 'n'), Token('Equal', '='),
                          Token('Char', 'u'), Token('Char', 's'), Token('Char', '-'), Token('Char', 'w'),
                          Token('Char', 'e'), Token('Char', 's'), Token('Char', 't'), Token('Space', ' '),
                          Token('Char', 'f'), Token('Char', 'i'), Token('Char', 'e'), Token('Char', 'l'),
                          Token('Char', 'd'), Token('Int', '1'), Token('Equal', '='), Token('Int', '1'),
                          Token('Comma', ','), Token('Char', 'f'), Token('Char', 'i'), Token('Char', 'e'),
                          Token('Char', 'l'), Token('Char', 'd'), Token('Int', '2'), Token('Equal', '='),
                          Token('Int', '2')])


class TestParseIdentifier(TestCase):
    def test_identifier(self):
        self.assertEqual(LineParser.parse_identifier('cpu a=1'), "cpu")
        self.assertEqual(LineParser.parse_identifier('yahoo.CHFGBP\\=X.ask,tag=foobar value=10.2'),
                         "yahoo.CHFGBP=X.ask")
        self.assertEqual(LineParser.parse_identifier('cpu,host=serverA,region=us-west foo="bar"'), "cpu")
        self.assertEqual(LineParser.parse_identifier(
            r'"measurement\ with\ quotes",tag\ key\ with\ spaces=tag\,value\,with"commas" field_key\\\="string field value, only \\" need be quoted"'),
            "\"measurement with quotes\"")

        try:
            LineParser.parse_identifier('')
            self.fail()
        except NoParseError:
            pass

        try:
            print(LineParser.parse_identifier(','))
            self.fail()
        except NoParseError:
            pass


class TestParseLine(TestCase):
    def do_test(self, string: str, verify_line: Line):
        line = LineParser.parse(string)
        self.assertEqual(line.key, verify_line.key)
        self.assertEqualLine(line, verify_line)
        self.assertEqual(str(line), string)

    def assertEqualLine(self, line1, line2):
        self.assertEqual(dict(line1.tags), dict(line2.tags))
        self.assertEqual(dict(line1.fields), dict(line2.fields))
        self.assertEqual(line1.timestamp, line2.timestamp)

    def test_parse_lines(self):
        self.assertEqual("".join(map(str, parse_lines("foo b=1"))), 'foo b=1')

        text = """\
cpu field=123
cpu,host=serverA,region=us-west field1=1,field2=2
cpu,host=serverA,region=us-west field1=1,field2=2 1234"""
        writes = parse_lines(text)
        self.assertEqual("\n".join(map(str, writes)), text)

    def test_parse(self):
        self.do_test("cpu a=1", Line("cpu", {}, {'a': 1}, None))
        self.do_test('yahoo.CHFGBP\\=X.ask,tag=foobar value=10.2',
                     Line('yahoo.CHFGBP=X.ask', {'tag': 'foobar'}, {'value': 10.2}))

        self.assertEqual(repr(LineParser.parse('cpu,host=serverA,region=us-west foo="bar"')),
                         '''<Line key=cpu tags=[('host', 'serverA'), ('region', 'us-west')] fields=[('foo', 'bar')] timestamp=None>''')

        self.assertEqual(str(LineParser.parse('cpu host="serverA",region="us-west"')),
                         'cpu host="serverA",region="us-west"')

        self.do_test('cpu\\,01 host="serverA",region="us-west"',
                     Line('cpu,01', {}, {'host': 'serverA', 'region': 'us-west'}, None))

        self.do_test('cpu host="server A",region="us west"',
                     Line('cpu', {}, dict([('host', 'server A'), ('region', 'us west')]), None))

        self.do_test('cpu ho\\=st="server A",region="us west"',
                     Line('cpu', {}, dict([('ho=st', 'server A'), ('region', 'us west')]), None))

        self.assertEqual(str(LineParser.parse('cpu,ho\=st=server\ A field=123')),
                         'cpu,ho\=st=server\ A field=123')

        # error: double name is accepted
        self.assertEqual(str(LineParser.parse('cpu,foo=bar,foo=bar field=123,field=123')),
                         'cpu,foo=bar,foo=bar field=123,field=123')

        self.assertEqual(str(LineParser.parse('cpu field12=12')), 'cpu field12=12')
        self.assertEqual(str(LineParser.parse('cpu field12=12 123123123')), 'cpu field12=12 123123123')

        try:
            LineParser.parse('cpu field12=12 1231abcdef123')
            self.fail()
        except NoParseError:
            pass

        self.assertEqual(str(LineParser.parse('cpu,x=3,y=4,z=6 field\\ name="HH \\\"World",x="asdf foo"')),
                         'cpu,x=3,y=4,z=6 field\\ name="HH \\"World",x="asdf foo"')

        self.assertEqual(str(LineParser.parse('cpu,x=3 field\\ name="HH \\"World",x="asdf foo"')),
                         'cpu,x=3 field\\ name="HH \\"World",x="asdf foo"')

        self.do_test('cpu foo="bar" 12345', Line('cpu', {}, {'foo': 'bar'}, 12345))

        self.do_test(r'"measurement\ with\ quotes" foo=1',
                     Line('"measurement with quotes"', {}, {'foo': 1}, None))

        self.do_test(r'a$b,cp="asdf" value="fo \\ o\""',
                     Line("a$b", {'cp': '"asdf"'}, {'value': r'fo \ o"'}))
        self.assertEqualLine(LineParser.parse(r'a$b,cp="asdf" value="fo \ o\""'),
                             Line("a$b", {'cp': '"asdf"'}, {'value': r'fo \ o"'}))
        self.assertEqual(str(Line("a$b", {'cp': '"asdf"'}, {'value': r'fo \ o"'})),
                         r'a$b,cp="asdf" value="fo \\ o\""')

        self.assertEqualLine(LineParser.parse(r'test value="7\\\""'),
                             Line('test', {}, {'value': r'7\"'}, None))

        self.do_test('K.5S,Ccpvo=a\\ b value=1', Line('K.5S', {'Ccpvo': 'a b'}, {'value': 1}))

        self.assertEqualLine(LineParser.parse('foo field1=f,field2=false,field3=False,field4=FALSE,field5="fag"'),
                             Line('foo', {},
                                  {'field4': False, 'field3': False, 'field2': False, 'field1': False, 'field5': 'fag'},
                                  None))

        self.assertEqualLine(LineParser.parse('foo field0="tag",field1=t,field2=true,field3=True,field4=TRUE'),
                             Line('foo', {},
                                  {'field4': True, 'field0': 'tag', 'field3': True, 'field2': True, 'field1': True},
                                  None))
        self.assertEqual(str(LineParser.parse('foo field0="tag",field1=t,field2=true,field3=True,field4=TRUE')),
                         'foo field0="tag",field1=True,field2=True,field3=True,field4=True')

        self.assertEqual(str(LineParser.parse('foo,foo=2 field_key="string\\" field"')),
                         'foo,foo=2 field_key="string\\" field"')

        self.assertEqual(str(LineParser.parse('foo,foo=2 field_key\\\\="string field"')),
                         'foo,foo=2 field_key\\\\="string field"')

        self.assertEqual(str(LineParser.parse('foo,foo=2 "field key with space"="string field"')),
                         'foo,foo=2 field\ key\ with\ space="string field"')

        self.assertEqualLine(LineParser.parse(
            r'disk_free value=442221834240,working\ directories="C:\My Documents\Stuff for examples,C:\My Documents" 123'),
            Line('disk_free', {}, {'value': 442221834240,
                                   'working directories': r'C:\My Documents\Stuff for examples,C:\My Documents'}, 123))

        self.assertEqualLine(LineParser.parse(
            r'disk_free value=442221834240,working\ directories="C:\My Documents\Stuff for examples,C:\My Documents"'),
            Line('disk_free', {}, {'value': 442221834240,
                                   'working directories': r'C:\My Documents\Stuff for examples,C:\My Documents'},
                 None))

        self.assertEqualLine(LineParser.parse(
            r'"measurement\ with\ quotes",tag\ key\ with\ spaces=tag\,value\,with"commas" field_key\\="string field value, only \" need be quoted"'),
            Line("measurement with quotes",
                 {'tag key with spaces': 'tag,value,with"commas"'},
                 {'field_key\\': 'string field value, only " need be quoted'}, None))
        self.assertEqual(str(Line("measurement with quotes", {'tag key with spaces': 'tag,value,with"commas"'},
                                  {'field_key\\': 'string field value, only " need be quoted'}, None)),
                         r'measurement\ with\ quotes,tag\ key\ with\ spaces=tag\,value\,with"commas" field_key\\="string field value, only \" need be quoted"')
