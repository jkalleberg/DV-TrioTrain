#!/bin/python3
"""
description: 

example:
"""
from logging import Logger
from os import getcwd
from pathlib import Path
from sys import path
from typing import List, TextIO, Union

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.files import TestFile, WriteFiles
