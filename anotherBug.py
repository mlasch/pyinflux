#!/usr/bin/env python3
"""
another bug?
in 2016/07/23 18:37:37 InfluxDB starting, version 0.13.0, branch 0.13, commit e57fb88a051ee40fd9277094345fbd47bb4783ce
the escaping of the 'key' or 'name' is strange
"""
from pyinflux.client import Influx, Line

influxdb = Influx('localhost')

print(influxdb.execute('DROP DATABASE test').as_text())
print(influxdb.execute('CREATE DATABASE test').as_text())


def write(line):
    print(repr(line))
    print(str(line))
    return influxdb.write_db('test', [line])


print(write(Line('asd\\', {'tag1': ''}, {'field1': ''})))
print(write(Line('asd\\\\', {'tag1': ''}, {'field1': ''})))


def query(q):
    print(q)
    try:
        return influxdb.query_db('test', q).as_json()
    except Exception as e:
        return str(e)

# at least some of these query must return something...
print(query('SELECT * FROM asd'))
print(query('SELECT * FROM asd\\'))
print(query('SELECT * FROM asd\\\\'))
print(query('SELECT * FROM "asd"'))
print(query('SELECT * FROM "asd\\\\"'))
