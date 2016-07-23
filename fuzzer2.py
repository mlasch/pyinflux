#!/usr/bin/env python3
"""
in 2016/07/23 18:37:37 InfluxDB starting, version 0.13.0, branch 0.13, commit e57fb88a051ee40fd9277094345fbd47bb4783ce
this fuzzer can generate write line-statements that are parsed differently than how they are meant
"""
import re
import functools
import random
from multiprocessing.pool import ThreadPool as Pool

from pyinflux.client import Line, InfluxDB

influxdb = InfluxDB('test', 'localhost')


class Generator:
    all = lambda x: bytes(chr(random.randint(0x00, 0xff)), 'latin-1')
    _printables = list(map(chr, list(range(0x20, 0x7E))))
    printable = lambda x: random.choice(Generator._printables)
    numericText = lambda x: chr(random.randint(ord("0"), ord("9")))
    text = lambda x: chr(random.choice(
        list(range(ord("a"), ord("z"))) +
        list(range(ord("A"), ord("Z")))))
    basicText = lambda x: chr(random.choice(
        [ord("\""), ord(" "), ord("\\")] +
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


usedKeys = set()


def test():
    # influxdb doesn't allow measurements starting with {
    noBrace = Filter.regex("^[^\\{]")
    noHash = Filter.regex("^[^#]")  # hash sign starts a comment
    # TODO: only allow valid escape sequences
    noEscape = Filter.regex("^[^\\\\]+$")
    noUsed = lambda term: term not in usedKeys

    def generateKey(min=3, max=6):
        return generate(min, max, lambda text: noUsed(text)
                                               and noEscape(text),  # for now, see anotherBug.py
                        Generator.basicText)

    def generateTags(min, max):
        def generateTagPairs():
            for i in range(random.randint(min, max)):
                yield (generateKey(), generateKey())

        return dict(tuple(generateTagPairs()))

    def generateFields(min, max):
        def generateFieldPairs():
            for i in range(random.randint(min, max)):
                yield (generateKey(), generate(3, 6, lambda text: True
                                               , Generator.basicText))

        return dict(tuple(generateFieldPairs()))

    w = Line(generateKey(8, 12),  # key
             generateTags(1, 4),  # tags
             generateFields(1, 4))  # fields
    usedKeys.add(w.key)
    try:
        text = influxdb.write([w])
    except Exception as e:
        print("Data\nline={}\nwrite={}".format(str(w), repr(w)))
        raise e

    measurement = Line.escape_value(w.key)
    query = """\
SELECT * 
FROM {measurement} 
WHERE time >= now() - 2s""".format(**locals())
    query_response = []
    try:
        query_response = influxdb.query(query).as_json()
    except Exception as e:
        print("Data\nline={}\nwrite={}".format(str(w), repr(w)))
        raise e
    DEBUGINFO = ("DEBUG:\nquery={query}\nwrite={w}\n" +
                 "query_response={query_response}").format(**locals())
    try:
        assert len(query_response) == 1, DEBUGINFO

        results = query_response['results']
        assert len(results) == 1

        result = results[0]
        series = result['series']
        for serie in series:
            assert serie['name'] == w.key
            assert len(serie['columns']) == len(w.tags) + len(w.fields) + 1, \
                "Length of colums: {} != {}".format(len(serie['columns']), len(w.tags) + len(w.fields))
    except:
        print("Data\nline={}\nwrite={}\nquery={}\nquery_response={}".format(str(w), repr(w), query, query_response))
        raise


print(influxdb.query('DROP DATABASE test').as_text())
print(influxdb.query('CREATE DATABASE test').as_text())

N_PROC = 2
with Pool(processes=N_PROC) as pool:
    try:
        for res in pool.imap_unordered(run, [None] * N_PROC):
            pool.terminate()
            print("Exit")
            raise SystemExit(0)
    except:
        pool.terminate()
        raise
