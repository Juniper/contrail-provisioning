#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import glob
import inspect
from importlib import import_module
from SimpleXMLRPCServer import SimpleXMLRPCServer

NOT_RPC_MODULES = ('server', 'client')

def get_rpc_modules():
    # Assumes all the rpc modules are in the current directory
    rpc_files = glob.glob(os.path.dirname(__file__) + "/*.py")
    rpc_module_names = [os.path.basename(rpc_file)[:-3] for rpc_file in rpc_files]
    rpc_module_names = [rpc_module for rpc_module in rpc_module_names
                        if rpc_module not in NOT_RPC_MODULES]
    rpc_module_names = ['contrail_provisioning.rpc.%s' % rpc_module_name\
                        for rpc_module_name in rpc_module_names]

    return rpc_module_names

def main():
    server = SimpleXMLRPCServer(('', 9999), allow_none=True)

    # Find and import all the rpc modules
    rpc_module_names = get_rpc_modules()
    rpc_modules = map(import_module, rpc_module_names)

    # Dynamically register all the RPC
    for rpc_module in rpc_modules:
        all_functions = inspect.getmembers(rpc_module, inspect.isfunction)
        for function in all_functions:
            server.register_function(function[1], function[0])

    # Serve
    try:
        print 'Use Control-C to exit'
        server.serve_forever()
    except KeyboardInterrupt:
        print 'Exiting'

if __name__ == "__main__":
    main()
