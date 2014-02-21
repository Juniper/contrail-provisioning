#!/usr/bin/env bash

CONF_DIR=/etc/contrail
set -x

if [ -f /etc/redhat-release ]; then
   is_redhat=1
   is_ubuntu=0
   web_svc=httpd
   mysql_svc=mysqld
   keystone_svc=openstack-keystone
fi

if [ -f /etc/lsb-release ]; then
   is_ubuntu=1
   is_redhat=0
   web_svc=apache2
   mysql_svc=mysql
   keystone_svc=keystone
fi

function error_exit
{
    echo "${PROGNAME}: ${1:-''} ${2:-'Unknown Error'}" 1>&2
    exit ${3:-1}
}

chkconfig $mysql_svc 2>/dev/null
ret=$?
if [ $ret -ne 0 ]; then
    echo "MySQL is not enabled, enabling ..."
    chkconfig mysqld on 2>/dev/null
fi

mysql_status=`service $mysql_svc status 2>/dev/null`
if [[ $mysql_status != *running* ]]; then
    echo "MySQL is not active, starting ..."
    service $mysql_svc restart 2>/dev/null
fi

# Use MYSQL_ROOT_PW from the environment or generate a new password
if [ ! -f $CONF_DIR/mysql.token ]; then
    if [ -n "$MYSQL_ROOT_PW" ]; then
	MYSQL_TOKEN=$MYSQL_ROOT_PW
    else
	MYSQL_TOKEN=$(openssl rand -hex 10)
    fi
    echo $MYSQL_TOKEN > $CONF_DIR/mysql.token
    chmod 400 $CONF_DIR/mysql.token
    echo show databases |mysql -u root &> /dev/null
    if [ $? -eq 0 ] ; then
        mysqladmin password $MYSQL_TOKEN
    else
        error_exit ${LINENO} "MySQL root password unknown, reset and retry"
    fi
else
    MYSQL_TOKEN=$(cat $CONF_DIR/mysql.token)
fi

KEYSTONE_CONF=${KEYSTONE_CONF:-/etc/keystone/keystone.conf}

source /etc/contrail/ctrl-details

# Check if ADMIN/SERVICE Password has been set
ADMIN_PASSWORD=${ADMIN_TOKEN:-contrail123}
SERVICE_PASSWORD=${SERVICE_TOKEN:-$(/opt/contrail/contrail_installer/contrail_setup_utils/setup-service-token.sh; cat $CONF_DIR/service.token)}

openstack-config --set /etc/keystone/keystone.conf DEFAULT admin_token $SERVICE_PASSWORD

# Stop keystone if it is already running (to reload the new admin token)
service $keystone_svc status >/dev/null 2>&1 &&
service $keystone_svc stop

# Start and enable the Keystone service
service $keystone_svc restart
chkconfig $keystone_svc on

if [ ! -d /etc/keystone/ssl ]; then
    keystone-manage pki_setup
    chown -R keystone.keystone /etc/keystone/ssl
fi

# Set up a keystonerc file with admin password
export SERVICE_ENDPOINT=${SERVICE_ENDPOINT:-http://127.0.0.1:${CONFIG_ADMIN_PORT:-35357}/v2.0}

cat > $CONF_DIR/openstackrc <<EOF
export OS_USERNAME=admin
export OS_PASSWORD=$ADMIN_PASSWORD
export OS_TENANT_NAME=admin
export OS_AUTH_URL=http://127.0.0.1:5000/v2.0/
export OS_NO_CACHE=1
EOF

cat > $CONF_DIR/keystonerc <<EOF
export OS_USERNAME=admin
export SERVICE_TOKEN=$SERVICE_PASSWORD
export OS_SERVICE_ENDPOINT=$SERVICE_ENDPOINT
EOF

for APP in keystone; do
  openstack-db -y --init --service $APP --rootpw "$MYSQL_TOKEN"
done

# wait for the keystone service to start
tries=0
while [ $tries -lt 10 ]; do
    $(source $CONF_DIR/keystonerc; keystone user-list >/dev/null 2>&1)
    if [ $? -eq 0 ]; then break; fi;
    tries=$(($tries + 1))
    sleep 1
done

export ADMIN_PASSWORD
export SERVICE_PASSWORD

(source $CONF_DIR/keystonerc; bash contrail-keystone-setup.sh $CONTROLLER)

# Update all config files with service username and password
for svc in keystone; do
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_tenant_name service
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_user $svc
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_password $SERVICE_PASSWORD
    openstack-config --set /etc/$svc/$svc.conf DEFAULT log_file /var/log/keystone/keystone.log
    openstack-config --set /etc/$svc/$svc.conf sql connection mysql://keystone:keystone@localhost/keystone
    openstack-config --set /etc/$svc/$svc.conf catalog template_file /etc/keystone/default_catalog.templates
    openstack-config --set /etc/$svc/$svc.conf catalog driver keystone.catalog.backends.sql.Catalog
    openstack-config --set /etc/$svc/$svc.conf identity driver keystone.identity.backends.sql.Identity
    openstack-config --set /etc/$svc/$svc.conf token driver keystone.token.backends.memcache.Token
    openstack-config --set /etc/$svc/$svc.conf ec2 driver keystone.contrib.ec2.backends.sql.Ec2
    openstack-config --set /etc/$svc/$svc.conf DEFAULT onready keystone.common.systemd   
done

keystone-manage db_sync

# Create link /usr/bin/nodejs to /usr/bin/node
if [ ! -f /usr/bin/nodejs ]; then 
    ln -s /usr/bin/node /usr/bin/nodejs
fi

echo "======= Enabling the keystone services ======"

for svc in rabbitmq-server $web_svc memcached; do
    chkconfig $svc on
done

echo "======= Starting the services ======"

for svc in rabbitmq-server $web_svc memcached; do
    service $svc restart
done

service $keystone_svc restart

