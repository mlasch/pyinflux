#!/usr/bin/env python3
import unittest
from pyinflux import client, parser, test

if __name__ == '__main__':
    unittest.TextTestRunner().run(unittest.findTestCases(test))