import string

template = string.Template("""
CASSANDRA_SERVER_LIST=$__contrail_cassandra_server_list__
REDIS_SERVER=$__contrail_redis_server__
REDIS_SERVER_PORT=$__contrail_redis_server_port__
HTTP_SERVER_PORT=$__contrail_http_server_port__
LOG_FILE=$__contrail_log_file__
LOG_LOCAL=$__contrail_log_local__
COLLECTOR=$__contrail_collector__
COLLECTOR_PORT=$__contrail_collector_port__
""")
