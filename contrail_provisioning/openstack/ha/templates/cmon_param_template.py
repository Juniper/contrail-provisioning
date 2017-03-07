import string

template = string.Template("""
VIP="$__internal_vip__"
DIPS=($__haproxy_dips__)
DIPS_SIZE=${#DIPS[@]}
EVIP="$__external_vip__"
PERIODIC_RMQ_CHK_INTER=120
RABBITMQ_RESET=True
RABBITMQ_MNESIA_CLEAN=False
RMQ_CLIENTS=("nova-conductor" "nova-scheduler")
ZK_SERVER_IP="$__zooipports__"
OS_KS_USER="$__keystoneuser__"
OS_KS_PASS="$__keystonepass__"
CMON_USER="$__cmonuser__"
CMON_PASS="$__cmonpass__"
MONITOR_GALERA="$__monitorgalera__"
""")
