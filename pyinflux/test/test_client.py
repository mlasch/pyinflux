import json
import codecs
from unittest import TestCase
from pyinflux.client import Line, QueryResultOption
from io import BytesIO


class TestLine(TestCase):
    def test_line(self):
        self.assertEqual(str(Line('test', [('a', 'b')], [('value', 'asd\\\\')])),
                         r'test,a=b value="asd\\\\"')

        self.assertEqual(repr(Line('test', [('a', 'b')], [('value', 'asd\\\\')])),
                         r"<Line key=test tags=[('a', 'b')] fields=[('value', 'asd\\\\')] timestamp=None>")


class TestQueryResultOption(TestCase):
    def test_json(self):
        testobject = {'123': 456, '789': '456'}
        buf = BytesIO()
        json.dump(testobject, codecs.getwriter('utf-8')(buf))

        buf.seek(0)
        qro = QueryResultOption(lambda: buf)
        self.assertEqual(testobject, qro.as_json())
        self.assertEqual(testobject, qro.as_json())

    def test_text(self):
        testobject = {'123': 456, '789': '456'}
        buf = BytesIO()
        json.dump(testobject, codecs.getwriter('utf-8')(buf))

        buf.seek(0)
        qro = QueryResultOption(lambda: buf)
        self.assertEqual(json.dumps(testobject), qro.as_text())
        self.assertEqual(json.dumps(testobject), qro.as_text())
