#!/usr/bin/env python3
import re


class WriteRequest(object):
    @staticmethod
    def parse(lines):
        """
        Parse multiple Write objects separeted by new-line character.

        >>> lines = []
        >>> lines += ['cpu']
        >>> lines += ['cpu,host=serverA,region=us-west']
        >>> lines += ['cpu,host=serverA,region=us-west field1=1,field2=2']
        >>> lines += ['cpu,host=serverA,region=us-west field1=1,field2=2 1234']
        >>> print("\\n".join(map(str, WriteRequest.parse("\\n".join(lines)))))
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
    def parse(line):
        """
        Parse a line from the POST request into a Write object.

        >>> Write.parse('cpu')
        <Write key=cpu tags=None fields=None timestamp=None>
        >>> print(Write.parse('cpu'))
        cpu

        >>> Write.parse('cpu,host=serverA,region=us-west')
        <Write key=cpu tags=[('host', 'serverA'), ('region', 'us-west')] fields=None timestamp=None>
        >>> print(Write.parse('cpu,host=serverA,region=us-west'))
        cpu,host="serverA",region="us-west"

        >>> Write.parse('cpu\\,01,host=serverA,region=us-west')
        <Write key=cpu,01 tags=[('host', 'serverA'), ('region', 'us-west')] fields=None timestamp=None>
        >>> print(Write.parse('cpu\,01,host=serverA,region=us-west'))
        cpu\,01,host="serverA",region="us-west"

        >>> Write.parse('cpu,host=server\\ A,region=us\\ west')
        <Write key=cpu tags=[('host', 'server A'), ('region', 'us west')] fields=None timestamp=None>
        >>> print(Write.parse('cpu,host=server\\ A,region=us\\ west'))
        cpu,host="server A",region="us west"

        >>> Write.parse('cpu,ho\=st=server\ A,region=us\ west')
        <Write key=cpu tags=[('ho=st', 'server A'), ('region', 'us west')] fields=None timestamp=None>
        >>> print(Write.parse('cpu,ho\=st=server\ A,region=us\ west'))
        cpu,ho\=st="server A",region="us west"

        >>> print(Write.parse('cpu,ho\=st=server\ A field=123'))
        cpu,ho\=st="server A" field=123
        >>> print(Write.parse('cpu,foo=bar,foo=bar field=123,field=123')) # error: double name is accepted
        cpu,foo="bar",foo="bar" field=123,field=123
        >>> print(Write.parse('cpu field12=12'))
        cpu field12=12
        >>> print(Write.parse('cpu field12=12 123123123'))
        cpu field12=12 123123123
        >>> print(Write.parse('cpu field12=12 1231abcdef123'))
        Traceback (most recent call last):
        ...
        ValueError: invalid literal for int() with base 10: '1231abcdef123'
        >>> print(Write.parse('cpu field="hello World"'))
        null
        """
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

