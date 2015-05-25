#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""RPC's related to rabbitmq."""

import re

from fabric.api import local

def get_rabbitmq_clustered_nodes():
    output = local("sudo rabbitmqctl cluster_status", capture=True)
    running_nodes = re.compile(r"running_nodes,\[([^\]]*)")
    match = running_nodes.search(output)
    clustered_nodes = []
    if match:
        clustered_nodes = match.group(1).split(',')
        clustered_nodes = [node.strip(' \n\r\'') for node in clustered_nodes]
    return clustered_nodes
