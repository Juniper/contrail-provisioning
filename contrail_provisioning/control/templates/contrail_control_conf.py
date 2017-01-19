import string

template = string.Template("""#
# Copyright (c) 2014 Juniper Networks, Inc. All rights reserved.
#
# Control-node configuration options
#

[DEFAULT]
# bgp_config_file=bgp_config.xml
# bgp_end_of_rib_timeout=30
# bgp_port=179
# collectors= # List of collectors in ip:port format 
collectors=$__contrail_collectors__
# gr_helper_bgp_disable=0
# gr_helper_xmpp_disable=0
hostip=$__contrail_host_ip__ # Resolved IP of `hostname`
hostname=$__contrail_hostname__ # Retrieved as `hostname`
# http_server_port=8083
# log_category=
# log_disable=0
log_file=/var/log/contrail/contrail-control.log
# log_files_count=10
# log_file_size=10485760 # 10MB
log_level=SYS_NOTICE
log_local=1
# test_mode=0
# xmpp_auth_enable=0
# xmpp_server_cert=/etc/contrail/ssl/certs/server.pem
# xmpp_server_key=/etc/contrail/ssl/private/server-privkey.pem
# xmpp_ca_cert=/etc/contrail/ssl/certs/ca-cert.pem
# xmpp_end_of_rib_timeout=30
# xmpp_server_port=5269

# Sandesh send rate limit can be used to throttle system logs transmitted per
# second. System logs are dropped if the sending rate is exceeded
# sandesh_send_rate_limit=100

[IFMAP]
certs_store=$__contrail_cert_ops__
password=$__contrail_ifmap_paswd__
# server_url= # Provided by discovery server, e.g. https://127.0.0.1:8443
server_url=$__contrail_ifmap_server_url__
user=$__contrail_ifmap_usr__
# stale_entries_cleanup_timeout=300 # in seconds
# end_of_rib_timeout=10 # in seconds
# peer_response_wait_time=60 # in seconds

""")
