#!/usr/bin/env python
# encoding=utf-8
from __future__ import print_function

import os
import sys

from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, "README.md")).read()

needs_pytest = set(["pytest", "test", "ptr"]).intersection(sys.argv)
pytest_runner = ["pytest-runner"] if needs_pytest else []

setup(
    name="aiomwclient",
    version="0.0.1",  # Use bumpversion to update
    description="Asynchronous MediaWiki API client",
    long_description=README,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    keywords="mediawiki wikipedia",
    author="Wadu436",
    url="https://github.com/Wadu436/aiomwclient",
    license="MIT",
    packages=["aiomwclient"],
    install_requires=["aiohttp"],
    zip_safe=True,
)
