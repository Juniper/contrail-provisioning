#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Common RPC's."""

from fabric.api import local

def get_file_content(afile):
    with open(afile, 'r') as fd:
        return fd.read()
