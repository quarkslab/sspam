#!/usr/bin/python

from setuptools import setup

setup(
    name='sspam',
    description='Symbolic Simplification with PAttern Matching',
    packages=["sspam", "sspam.tools"],
    entry_points={
        'console_scripts': [
            'sspam = sspam.__main__:main'
        ]
    },
)
