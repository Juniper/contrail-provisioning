import string

template = string.Template("""
REDIS_SERVER_PORT=$__contrail_redis_server_port__
REDIS_QUERY_PORT=$__contrail_redis_query_port__
HOST_IP=$__contrail_host_ip__
COLLECTOR=$__contrail_collector__
COLLECTOR_PORT=$__contrail_collector_port__
HTTP_SERVER_PORT=$__contrail_http_server_port__
REST_API_PORT=$__contrail_rest_api_port__
LOG_FILE=$__contrail_log_file__
LOG_LOCAL=$__contrail_log_local__
LOG_LEVEL=$__contrail_log_level__
DISCOVERY=$__contrail_discovery_ip__
""")
