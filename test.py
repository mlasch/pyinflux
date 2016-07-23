#!/usr/bin/env python3
from doctest import testmod
from pyinflux import client, parser

if __name__ == '__main__':
    testmod(m=client)
    testmod(m=parser)
