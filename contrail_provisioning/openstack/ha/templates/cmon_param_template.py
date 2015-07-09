import string

template = string.Template("""
VIP="$__internal_vip__"
DIPS=($__haproxy_dips__)
DIPS_SIZE=${#DIPS[@]}
EVIP="$__external_vip__"
PERIODIC_RMQ_CHK_INTER=60
RABBITMQ_RESET=True
RAMMBITMQ_MNESIA_CLEAN=False
RMQ_CLIENTS=("nova-conductor" "nova-scheduler")
ZK_SERVER_IP="$__zooipports__"
""")
