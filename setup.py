#!/usr/bin/env python3
from distutils.core import setup

version = '0.1'

setup(name='pyinflux',
      version=version,
      description='Python classes to work with influxdb',
      author='Yves Fischer',
      author_email='yvesf+git@xapek.org',
      license="MIT",
      packages=['pyinflux.client', 'pyinflux.parser'],
      url='https://github.com/yvesf/pyinflux',
      install_requires=[],
      extras_require={'parser': ['funcparserlib==0.3.6']},
      classifiers=[
          "Programming Language :: Python",
          "Programming Language :: Python :: 3",
          "Development Status :: 3 - Alpha",
          "Intended Audience :: Developers",
          "Operating System :: OS Independent",
          "License :: OSI Approved :: MIT License",
      ])
