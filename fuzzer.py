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
    regex = lambda r: re.compile(r).match
    alpha = re.compile("^[a-z]+$").match
    pass_all = lambda _: True
    @staticmethod
    def except_chars(chars):
        regex = re.compile("^[^"+chars+"]*$")
        return regex.match
            


def generate(length_min, length_max, filter, generator):
    length = random.randint(length_min, length_max)
    while True:
        text = functools.reduce(lambda a,b: a+b,map(generator, range(length)))
        if filter(text):
            return text


def run(*a):
    while True:
        test1 = generate(3, 6, 
                Filter.regex("^[^\{\"]"), # influxdb doesn't allow measurements starting with { or "
                Generator.printable)
        test2 = generate(3, 6, Filter.pass_all, Generator.printable)
        test3 = generate(3, 6, Filter.pass_all, Generator.printable)
        test4 = generate(3, 6, Filter.pass_all, Generator.printable)
        w = Write(test1,  # key
                  {test2: test3},  # tags
                  {"value": test4})  # values
        line = str(w)
        print(line)
        try:
            r = requests.post(write_url, line)
            assert r.status_code == 204, \
                "Data:\nline={}\nwrite={}\nr.status_code={}\nr.content={}".format(
                    line, repr(w), r.status_code, r.text)
        except Exception as e:
            print(e)
            assert False, "Data\nline={}\nwrite={}".format(str(w), repr(w))

        measurement = Write.escape_value(w.key)
        query = "SELECT * FROM {measurement} WHERE time >= now() - 1s".format(**locals())
        result = list(client.query(query))
        DEBUGINFO = "DEBUG:\nquery={query}\nresult={result}\nline={line}".format(**locals())
        assert len(result) == 1, DEBUGINFO
        assert result[0][0]['value'] == test4, DEBUGINFO + "\nvalue=" + result[0][0]['value'] + "\ntest4=" + test4


N_PROC = 1
with Pool(processes=N_PROC) as pool:
    try:
        for res in pool.imap_unordered(run, [None] * N_PROC):
            pool.terminate()
            print("Exit")
            raise SystemExit(0)
    except Exception as e:
        pool.terminate()
        raise e
