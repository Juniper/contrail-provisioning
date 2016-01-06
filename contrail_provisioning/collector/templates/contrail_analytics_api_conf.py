import string

template = string.Template("""
[DEFAULTS]
host_ip = $__contrail_host_ip__
cassandra_server_list=$__contrail_cassandra_server_list__
#collectors = 127.0.0.1:8086
http_server_port = $__contrail_http_server_port__
rest_api_port = $__contrail_rest_api_port__
rest_api_ip = 0.0.0.0 
log_local = $__contrail_log_local__
log_level = $__contrail_log_level__
log_category = $__contrail_log_category__
log_file = $__contrail_log_file__

# Time-to-live in hours of the various data stored by collector into
# cassandra
# analytics_config_audit_ttl, if not set (or set to -1), defaults to analytics_data_ttl
# analytics_statistics_ttl, if not set (or set to -1), defaults to analytics_data_ttl
# analytics_flow_ttl, if not set (or set to -1), defaults to analytics_statsdata_ttl
analytics_data_ttl=$__contrail_analytics_data_ttl__
analytics_config_audit_ttl=$__contrail_config_audit_ttl__
analytics_statistics_ttl=$__contrail_statistics_ttl__
analytics_flow_ttl=$__contrail_flow_ttl__

[DISCOVERY]
disc_server_ip = $__contrail_discovery_ip__
disc_server_port = $__contrail_discovery_port__

[REDIS]
redis_server_port = $__contrail_redis_server_port__
redis_query_port = $__contrail_redis_query_port__
$__contrail_redis_password__
""")
