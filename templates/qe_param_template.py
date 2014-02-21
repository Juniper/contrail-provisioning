import string

template = string.Template("""#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
# Query-engine daemon configuration options
#

[DEFAULTS]
analytics-data-ttl=0
cassandra-server=$__contrail_cassandra_server_list__
collector-server= # Provided by discovery server
http-server-port=8091

[DISCOVERY]
port=5998
server= # discovery-server IP address

[LOG]
category=
file=/var/log/contrail/qe.log
level=SYS_DEBUG
local=1

[REDIS]
ip=127.0.0.1
port=6380
""")
