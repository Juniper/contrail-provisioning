import string

template = string.Template("""
[DEFAULTS]
rabbit_server=$__rabbit_server_ip__
rabbit_port=$__rabbit_server_port__
api_server_ip=$__contrail_api_server_ip__
api_server_port=$__contrail_api_server_port__
zk_server_ip=$__contrail_zookeeper_server_ip__
log_file=$__contrail_log_file__
cassandra_server_list=$__contrail_cassandra_server_list__
disc_server_ip=$__contrail_disc_server_ip__
disc_server_port=$__contrail_disc_server_port__
log_local=1
log_level=SYS_NOTICE
""")
