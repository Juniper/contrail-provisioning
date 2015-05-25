import string

template = string.Template("""
#contrail-config-marker-start

global
        tune.maxrewrite 1024

listen contrail-config-stats :5937
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

frontend quantum-server *:9696
    default_backend    quantum-server-backend

frontend  contrail-api *:8082
    default_backend    contrail-api-backend
    timeout client 3m

frontend  contrail-discovery *:5998
    default_backend    contrail-discovery-backend

backend quantum-server-backend
    option nolinger
    balance     roundrobin
$__contrail_quantum_servers__
    #server  10.84.14.2 10.84.14.2:9697 check

backend contrail-api-backend
    option nolinger
    timeout server 3m
    balance     roundrobin

$__contrail_api_backend_servers__
    #server  10.84.14.2 10.84.14.2:9100 check
    #server  10.84.14.2 10.84.14.2:9101 check

backend contrail-discovery-backend
    option nolinger
    balance     roundrobin
$__contrail_disc_backend_servers__
    #server  10.84.14.2 10.84.14.2:9110 check
    #server  10.84.14.2 10.84.14.2:9111 check

$__tor_agent_ha_config__

$__rabbitmq_config__
#contrail-config-marker-end
""")
