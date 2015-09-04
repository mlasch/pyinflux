#!/usr/bin/env python3
import functools
import random
from multiprocessing.pool import ThreadPool as Pool

import requests
from pyinfluxtools import *
from influxdb import InfluxDBClient

settings = {
    'host': 'localhost',
    'port': 8086,
    'username': 'root',
    'password': 'root',
    'database': 'test',
}

write_url = ("http://{host}:{port}/write?db={database}" +
             "&username={username}&password={password}"
             ).format(**settings)

client = InfluxDBClient(settings['host'], settings['port'],
                        settings['username'], settings['password'],
                        settings['database'])


class Generator:
    all = lambda x: bytes(chr(random.randint(0x00, 0xff)), 'latin-1')
    _printables = list(map(chr, list(range(0x20, 0x7E))))
    printable = lambda x: random.choice(Generator._printables)
    numericText = lambda x: chr(random.randint(ord("0"), ord("9")))
    text = lambda x: chr(random.choice(
        list(range(ord("a"), ord("z"))) +
        list(range(ord("A"), ord("Z")))))


class Filter:
    regex = lambda regex: re.compile(regex).match
    pass_all = lambda _: True


def generate(length_min, length_max, filter, generator):
    length = random.randint(length_min, length_max)
    while True:
        text = functools.reduce(
            lambda a, b: a + b, map(generator, range(length)))
        if filter(text):
            return text


def run(*a):
    while True:
        test()


def test():
    # influxdb doesn't allow measurements starting with {
    noBrace = Filter.regex("^[^\\{]")
    noHash = Filter.regex("^[^#]")  # hash sign starts a comment
    # TODO: only allow valid escape sequences
    noEscape = Filter.regex("^[^\\\\]+$")

    def generateKey(min=3,max=6):
        return generate(min, max, lambda text:
                        noBrace(text) and noHash(text) and noEscape(text),
                        Generator.printable)

    def generateTags(min, max):
        def generateTagPairs():
            for i in range(random.randint(min, max)):
                yield (generateKey(), generateKey())

        return dict(tuple(generateTagPairs()))

    def generateFields(min, max):
        def generateFieldPairs():
            for i in range(random.randint(min,max)):
                yield (generateKey(), generate(3, 6, lambda _: True, Generator.printable))
        return dict(tuple(generateFieldPairs()))

    w = Write(generateKey(8,12),  # key
              generateTags(1, 4),  # tags
              generateFields(1, 4))  # fields
    line = str(w)
    print(line)
    try:
        r = requests.post(write_url, line)
        INFO = ("Data:\nline={}\nwrite={}\nr.status_code={}\n" +
                "r.content={}").format(line, repr(w), r.status_code, r.text)
        assert r.status_code == 204, INFO
    except Exception as e:
        print(e)
        assert False, "Data\nline={}\nwrite={}".format(str(w), repr(w))

    measurement = Write.escape_value(w.key)
    query = """\
SELECT * 
FROM {measurement} 
WHERE time >= now() - 2s""".format(**locals())
    result = []
    try:
        result = list(client.query(query))
    except Exception as e:
        print(e)
    wrepr=repr(w)
    DEBUGINFO = ("DEBUG:\nquery={query}\nwrite={wrepr}\n" +
                 "result={result}\nline={line}").format(**locals())
    assert len(result) == 1, DEBUGINFO
    assert len(result[0][0]) == len(w.tags) + len(w.fields) + 1, DEBUGINFO # + time

    # assert fields
    for (key, value) in w.fields:
        assert key in result[0][0], DEBUGINFO
        assert result[0][0][key] == value, DEBUGINFO + \
            "\n"+ key +"=" + result[0][0][key] + "=" + value

    # assert tags
    for (tagKey, tagValue) in w.tags:
        assert tagKey in result[0][0], DEBUGINFO
        assert result[0][0][tagKey] == tagValue, DEBUGINFO


N_PROC = 4
with Pool(processes=N_PROC) as pool:
    try:
        for res in pool.imap_unordered(run, [None] * N_PROC):
            pool.terminate()
            print("Exit")
            raise SystemExit(0)
    except Exception as e:
        pool.terminate()
        raise e
