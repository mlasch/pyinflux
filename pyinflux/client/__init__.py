import typing
import io
import re
from urllib.request import urlopen
from urllib.parse import quote as urlquote, urlencode
import json
import codecs


class Line(object):
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
    def escape_identifier(string):
        return re.sub(r'([\\,= ])', '\\\\\\1', string)

    @staticmethod
    def escape_tags(taglist):
        return ",".join(map(lambda kv:
                            (Line.escape_identifier(kv[0]) + "=" + Line.escape_identifier(kv[1])),
                            taglist))

    @staticmethod
    def escape_value(obj):
        if (isinstance(obj, float) or
                isinstance(obj, int) or
                isinstance(obj, bool)):
            return str(obj)
        else:
            obj = str(obj)
            return "\"" + obj.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

    @staticmethod
    def escape_fields(kvlist):
        def escape_key(string):
            return re.sub(r'(["\\,= ])', '\\\\\\1', string)

        return ",".join(
            map(lambda kv: escape_key(kv[0]) + "=" + Line.escape_value(kv[1]),
                kvlist))

    def __repr__(self):
        """
        >>> print(repr(Line('test', [('a','b')], [('value','asd\\\\')])))
        <Line key=test tags=[('a', 'b')] fields=[('value', 'asd\\\\')] timestamp=None>
        """
        return "<{} key={} tags={} fields={} timestamp={}>".format(
            self.__class__.__name__, self.key, self.tags, self.fields, self.timestamp)

    def __str__(self):
        """
        >>> print(Line('test', [('a','b')], [('value','asd\\\\')]))
        test,a=b value="asd\\\\"
        """
        result = self.escape_identifier(self.key)

        if self.tags:
            result += ","
            result += self.escape_tags(self.tags)

        if self.fields:
            result += " "
            result += self.escape_fields(self.fields)

        if self.timestamp:
            result += " "
            result += str(self.timestamp)

        return result


class QueryResultOption:
    CODEC = codecs.getreader('utf-8')

    def __init__(self, exec_func: typing.Callable[[], io.IOBase]):
        self.exec_func = exec_func
        self._json = None
        self._text = None

    def as_json(self):
        if self._json is None:
            fh = self.CODEC(self.exec_func())
            self._json = json.load(fh)
            fh.close()
        return self._json

    def as_text(self):
        if self._text is None:
            fh = self.CODEC(self.exec_func())
            self._text = fh.read()
            fh.close()
        return self._text


class Influx:
    def __init__(self, host: str, port: int = 8086, username: str = None, password: str = None):
        """
        :param username: username and password:
        :param password: if set both must be set
        """
        self._write_url = "http://{host}:{port}/write?".format(**locals())
        self._query_url_get = "http://{host}:{port}/query?".format(**locals())
        self._query_url_post = "http://{host}:{port}/query".format(**locals())
        if username and password:
            self._write_url += 'username=' + username + '&password' + password + '&'
            self._query_url_get += 'username=' + username + '&password' + password + '&'
            self._query_url_post += '?username=' + username + '&password' + password

    def write_db(self, db: str, lines: [Line]):
        url = self._write_url + "db=" + urlquote(db)
        request_data = "\n".join(map(str, lines)).encode('utf-8')
        with urlopen(url, request_data) as fh:
            response = fh.read()
            return response.decode('utf-8')

    def query_db(self, db: str, query: str) -> QueryResultOption:
        def get_fh() -> io.IOBase:
            url = self._query_url_get + 'db=' + urlquote(db) + '&q=' + urlquote(query)
            return urlopen(url)

        return QueryResultOption(get_fh)

    def execute(self, query: str) -> QueryResultOption:
        def get_fh() -> io.IOBase:
            return urlopen(self._query_url_post, urlencode({'q': query}).encode('utf-8'))

        return QueryResultOption(get_fh)


class InfluxDB(Influx):
    def __init__(self, db: str, host: str, port: int = 8086, username: str = None, password: str = None):
        super().__init__(host, port, username, password)
        self._db = db

    def write(self, lines: [Line]):
        return self.write_db(self._db, lines)

    def query(self, query: str):
        return self.query_db(self._db, query)
