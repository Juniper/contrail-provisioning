import string

template = string.Template("""
IFMAP_SERVER=$__contrail_ifmap_srv_ip__
IFMAP_PORT=$__contrail_ifmap_srv_port__
IFMAP_USER=$__contrail_ifmap_usr__
IFMAP_PASWD=$__contrail_ifmap_paswd__
COLLECTOR=$__contrail_collector__
COLLECTOR_PORT=$__contrail_collector_port__
DISCOVERY=$__contrail_discovery_ip__
HOSTIP=$__contrail_host_ip__
CERT_OPTS=$__contrail_cert_ops__
LOGFILE=$__contrail_logfile__
LOG_LOCAL=$__contrail_log_local__
""")
