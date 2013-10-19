import string

template = string.Template("""
[DEFAULTS]
zk_server_ip=127.0.0.1
zk_server_port=$__contrail_zk_server_port__
listen_ip_addr=$__contrail_listen_ip_addr__
listen_port=$__contrail_listen_port__
log_local=$__contrail_log_local__
log_file=$__contrail_log_file__

# minimim time to allow client to cache service information (seconds)
ttl_min=300

# maximum time to allow client to cache service information (seconds)
ttl_max=1800

# maximum hearbeats to miss before server will declare publisher out of
# service. 
hc_max_miss=3

# use short TTL for agressive rescheduling if all services are not up
ttl_short=1

######################################################################
# Other service specific knobs ...
 
# use short TTL for agressive rescheduling if all services are not up
# ttl_short=1
 
# specify policy to use when assigning services
# policy = [load-balance | round-robin | fixed]
######################################################################
""")
