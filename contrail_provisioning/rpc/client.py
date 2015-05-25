#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Client library to connect to RPC server"""

import xmlrpclib

class RPCClientError(Exception):
    pass

def connect(host, port='9999'):
    return xmlrpclib.ServerProxy("http://%s:%s/" % (host, port))

def get_file(rpcserver, fname, retries=-1):
    while retries:
        try:
            return rpcserver.get_file_content(fname)
        except  Exception as e:
            print "WARN: %s" % e.faultString
        retries -= 1
    raise RPCClientError(e.faultString)
