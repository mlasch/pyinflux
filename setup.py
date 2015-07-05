#!/usr/bin/env python

from distutils.core import setup

setup(name='pyinfluxtools',
    version='0.1',
    description='Python classes to work with influxdb',
    author='Yves Fischer',
    author_email='yvesf+github@xapek.org',
    license="MIT",
    packages = ['pyinfluxtools'],
#    url='https://github.com/',
#    scripts=[],
    install_requires=['funcparserlib==0.3.6'],
    classifiers = [
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ]
)

