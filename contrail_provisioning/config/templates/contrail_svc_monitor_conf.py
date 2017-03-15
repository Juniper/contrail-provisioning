import string

template = string.Template("""
[DEFAULTS]
api_server_ip=$__contrail_api_server_ip__
api_server_port=$__contrail_api_server_port__
api_server_use_ssl=$__api_server_use_ssl__
zk_server_ip=$__contrail_zookeeper_server_ip__
log_file=$__contrail_log_file__
cassandra_server_list=$__contrail_cassandra_server_list__
collectors=$__contrail_collectors__
region_name=$__contrail_region_name__
log_local=1
log_level=SYS_NOTICE
rabbit_server=$__rabbit_server_ip__

[SECURITY]
use_certs=$__contrail_use_certs__
keyfile=$__contrail_keyfile_location__
certfile=$__contrail_certfile_location__
ca_certs=$__contrail_cacertfile_location__

[SCHEDULER]
analytics_server_list=$__contrail_analytics_server_list__
""")
