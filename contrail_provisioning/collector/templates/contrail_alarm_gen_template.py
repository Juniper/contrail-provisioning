import string

template = string.Template("""
[DEFAULTS]
#host_ip = 127.0.0.1
#collectors = 127.0.0.1:8086
#http_server_port = 5995
log_local = 1
log_level = SYS_INFO
#log_category =
log_file = /var/log/contrail/contrail-alarm-gen.log
kafka_broker_list = $__contrail_broker_list__

[DISCOVERY]
disc_server_ip = 127.0.0.1
disc_server_port = 5998

[REDIS]
#redis_server_port=6379

""")

