# Sample initial data for Keystone using python-keystoneclient
#
# This script is based on the original DevStack keystone_data.sh script.
#
# It demonstrates how to bootstrap Keystone with an administrative user
# using the SERVICE_TOKEN and SERVICE_ENDPOINT environment variables
# and the administrative API.  It will get the admin_token (SERVICE_TOKEN)
# and admin_port from keystone.conf if available.
#
# There are two environment variables to set passwords that should be set
# prior to running this script.  Warnings will appear if they are unset.
# * ADMIN_PASSWORD is used to set the password for the admin and demo accounts.
# * SERVICE_PASSWORD is used to set the password for the service accounts.
#
# Enable the Swift and Quantum accounts by setting ENABLE_SWIFT and/or
# ENABLE_QUANTUM environment variables.
#
# Enable creation of endpoints by setting ENABLE_ENDPOINTS environment variable.
# Works with Catalog SQL backend. Do not use with Catalog Templated backend
# (default).
#
#
# Tenant               User      Roles
# -------------------------------------------------------
# admin                admin     admin
# service              glance    admin
# service              nova      admin
# service              quantum   admin        # if enabled
# service              swift     admin        # if enabled
# demo                 admin     admin
# demo                 demo      Member,sysadmin,netadmin
# invisible_to_admin   demo      Member

source /opt/contrail/bin/contrail-lib.sh
set -x

if [ $AUTH_PROTOCOL == 'https' ]; then
    export INSECURE_FLAG='--insecure'
else
    export INSECURE_FLAG=''
fi  

ENABLE_ENDPOINTS=yes
#ENABLE_QUANTUM=yes
if [ -f /etc/redhat-release ]; then
    rpm -q contrail-heat > /dev/null && ENABLE_HEAT='yes'
    is_ubuntu=0
fi
if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release; then
    dpkg -l contrail-heat > /dev/null && ENABLE_HEAT='yes'
    is_ubuntu=1
    keystone_version=`dpkg -l keystone | grep 'ii' | grep -v python | awk '{print $3}'`
fi
CONTROLLER=${INTERNAL_VIP:-$CONTROLLER}

if [ -z $ADMIN_PASSWORD ]; then
    echo ADMIN_PASSWORD must be defined
    exit 1;
fi

if [ -z $SERVICE_PASSWORD ]; then
    echo SERVICE_PASSWORD must be defined
    exit 1;
fi

CONTROLLER=$1
if [ -z $CONTROLLER ]; then
    $CONTROLLER="localhost"
fi

function is_installed_rpm_greater() {
    package_name=$1
    read ref_epoch ref_version ref_release <<< $2
    rpm -q --qf '%{epochnum} %{V} %{R}\n' $package_name >> /dev/null
    if [ $? != 0 ]; then
        echo "ERROR: Seems $package_name is not installed"
        return 2
    fi
    read epoch version release <<< $(rpm -q --qf '%{epochnum} %{V} %{R}\n' $package_name)
    verdict=$(python -c "import sys,rpm; \
        print rpm.labelCompare(('$epoch', '$version', '$release'), ('$ref_epoch', '$ref_version', '$ref_release'))")
    if [[ $verdict -ge 0 ]]; then
        return 0
    else
        return 1
    fi
}

function get_id () {
    echo `"$@" | grep ' id ' | awk '{print $4}'`
}

function is_keystone_up() {
    for i in {1..36} {
    do
       update_services "action=restart" mysql
       openstack $INSECURE_FLAG service list
       if [ $? == 0 ]; then
           return 0
       fi
       echo "Keystone is not up, retrying in 5 secs"
       sleep 5
    done
    return 1
}

# Projects
function get_project() {
    id=$(openstack $INSECURE_FLAG project list | grep ' '$1' ' | awk '{print $2;}')
    if [ -z "$id" ]; then
        id=$(openstack $INSECURE_FLAG project create $1 | grep ' id ' | awk '{print $4}')
    fi
    echo $id
}

is_keystone_up
if [ $? != 0 ]; then
    echo "Keystone is not up, Exiting..."
    exit 1
fi

ADMIN_PROJECT=$(get_project admin)
SERVICE_PROJECT=$(get_project service)
DEMO_PROJECT=$(get_project demo)
INVIS_PROJECT=$(get_project invisible_to_admin)

# Users
function get_user() {
    id=$(openstack $INSECURE_FLAG user list | grep $1 | awk '{print $2;}')
    EMAIL="@example.com"
    if [ -z $id ]; then
        id=$(openstack $INSECURE_FLAG user create --password "$ADMIN_PASSWORD" $1 \
                 --email $1$EMAIL | grep ' id ' | awk '{print $4;}')
    fi
    echo $id
}

ADMIN_USER=$(get_user admin)
DEMO_USER=$(get_user demo)

# Roles
function get_role() {
    id=$(openstack $INSECURE_FLAG role list | grep ' '$1' ' | awk '{print $2;}')
    if [ -z $id ]; then
        id=$(openstack $INSECURE_FLAG role create $1 | grep ' id ' | awk '{print $4;}')
    fi
    echo $id
}

ADMIN_ROLE=$(get_role admin)
MEMBER_ROLE=$(get_role Member)
KEYSTONEADMIN_ROLE=$(get_role KeystoneAdmin)
KEYSTONESERVICE_ROLE=$(get_role KeystoneServiceAdmin)
SYSADMIN_ROLE=$(get_role sysadmin)
NETADMIN_ROLE=$(get_role netadmin)

function user_role_lookup() {
    echo $(openstack $INSECURE_FLAG user role list $1 \
        | grep ' '$3' ' | awk '{print $4;}')
}

# Add Roles to Users in Projects
if [ -z $(user_role_lookup $ADMIN_USER $ADMIN_PROJECT admin) ]; then
openstack $INSECURE_FLAG role add --user $ADMIN_USER --project $ADMIN_PROJECT $ADMIN_ROLE
  if [ "$KEYSTONE_VERSION" == "v3" ]; then
      user_role_add_domain $ADMIN_USER  "default" $ADMIN_ROLE
  fi
fi

if [ -z $(user_role_lookup $ADMIN_USER --project $ADMIN_PROJECT $CLOUD_ADMIN_ROLE) ]; then
openstack $INSECURE_FLAG role add --user $ADMIN_USER --project $ADMIN_PROJECT $CLOUD_ADMIN_ROLE
  if [ "$KEYSTONE_VERSION" == "v3" ]; then
      user_role_add_domain $ADMIN_USER  "default" $CLOUD_ADMIN_ROLE
  fi
fi

if [ -z $(user_role_lookup $DEMO_USER --project $DEMO_PROJECT Member) ]; then
openstack $INSECURE_FLAG role add --user $DEMO_USER --project $DEMO_PROJECT $MEMBER_ROLE
fi

if [ -z $(user_role_lookup $DEMO_USER --project $DEMO_PROJECT sysadmin) ]; then
openstack $INSECURE_FLAG role add --user $DEMO_USER --project $DEMO_PROJECT $SYSADMIN_ROLE
fi

if [ -z $(user_role_lookup $DEMO_USER --project $DEMO_PROJECT netadmin) ]; then
openstack $INSECURE_FLAG role add --user $DEMO_USER --project $DEMO_PROJECT $NETADMIN_ROLE
fi

if [ -z $(user_role_lookup $DEMO_USER --project $INVIS_PROJECT Member) ]; then
openstack $INSECURE_FLAG role add --user $DEMO_USER --project $INVIS_PROJECT $MEMBER_ROLE
fi

if [ -z $(user_role_lookup $ADMIN_USER --project $DEMO_PROJECT admin) ]; then
openstack $INSECURE_FLAG role add --user $ADMIN_USER --project $DEMO_PROJECT $ADMIN_ROLE
fi

# TODO(termie): these two might be dubious
if [ -z $(user_role_lookup $ADMIN_USER --project $ADMIN_PROJECT KeystoneAdmin) ]; then
openstack $INSECURE_FLAG role add --user $ADMIN_USER --project $ADMIN_PROJECT $KEYSTONEADMIN_ROLE
fi
if [ -z $(user_role_lookup $ADMIN_USER --project $ADMIN_PROJECT KeystoneServiceAdmin) ]; then
openstack $INSECURE_FLAG role add --user $ADMIN_USER --project $ADMIN_PROJECT $KEYSTONESERVICE_ROLE
fi

# Services
function get_service() {
    id=$(openstack $INSECURE_FLAG service list | grep ' '$1' ' | awk '{print $2;}')
    if [ -z $id ]; then
        id=$(get_id openstack $INSECURE_FLAG service create --name=$1 \
                        --description=$2 $2)
    fi
    echo $id
}

function get_service_user() {
    id=$(openstack $INSECURE_FLAG user list | grep $1 | awk '{print $2;}')
    EMAIL="@example.com"
    if [ -z $id ]; then
        id=$(openstack $INSECURE_FLAG user create --password "$SERVICE_PASSWORD" $1 \
                 --email $1$EMAIL | grep ' id ' | awk '{print $4;}')
    fi
    echo $id
}

function endpoint_lookup() {
    echo $(openstack $INSECURE_FLAG --os-region-name $OS_REGION_NAME endpoint list | grep ' '$1' ' | awk '{print $2;}' )
}

source /etc/contrail/openstackrc

NOVA_SERVICE=$(get_service nova compute "Nova Compute Service")
NOVA_USER=$(get_service_user nova)

if [ -z $(user_role_lookup $NOVA_USER $SERVICE_PROJECT admin) ]; then
    openstack $INSECURE_FLAG role add \
                       --user $NOVA_USER \
                       --project $SERVICE_PROJECT \
                       $ADMIN_ROLE
fi

if [[ -n "$ENABLE_ENDPOINTS" ]]; then
    if [ -z $(endpoint_lookup nova) ]; then
        openstack $INSECURE_FLAG endpoint create --region $OS_REGION_NAME $NOVA_SERVICE \
            --publicurl 'http://'$CONTROLLER':8774/v2.1/$(tenant_id)s' \
            --adminurl 'http://localhost:8774/v2.1/$(tenant_id)s'  \
            --internalurl 'http://'$CONTROLLER':8774/v2.1/$(tenant_id)s'
    fi
fi

EC2_SERVICE=$(get_service ec2 ec2 "EC2 Compatibility Layer")
if [[ -n "$ENABLE_ENDPOINTS" ]]; then
    if [ -z $(endpoint_lookup ec2) ]; then
        openstack $INSECURE_FLAG endpoint create --region $OS_REGION_NAME $EC2_SERVICE \
           --publicurl http://localhost:8773/services/Cloud \
           --adminurl http://localhost:8773/services/Admin \
           --internalurl http://localhost:8773/services/Cloud
    fi
fi

GLANCE_SERVICE=$(get_service glance image "Glance Image Service")
GLANCE_USER=$(get_service_user glance)

if [ -z $(user_role_lookup $GLANCE_USER $SERVICE_PROJECT admin) ]; then
    openstack $INSECURE_FLAG role add \
                       --user $GLANCE_USER \
                       --project $SERVICE_PROJECT \
                       $ADMIN_ROLE
fi

if [[ -n "$ENABLE_ENDPOINTS" ]]; then
    if [ -z $(endpoint_lookup glance) ]; then
         openstack $INSECURE_FLAG endpoint create --region $OS_REGION_NAME $GLANCE_SERVICE \
            --publicurl http://$CONTROLLER:9292 \
            --adminurl http://localhost:9393 \
            --internalurl http://localhost:9393
    fi
fi

BARBICAN_SERVICE=$(get_service barbican key-manager "Barbican Service")
BARBICAN_USER=$(get_service_user barbican)

if [ -z $(user_role_lookup $BARBICAN_USER $SERVICE_PROJECT admin) ]; then
    openstack $INSECURE_FLAG role add \
                       --user $BARBICAN_USER \
                       --project $SERVICE_PROJECT \
                       $ADMIN_ROLE
fi

if [[ -n "$ENABLE_ENDPOINTS" ]]; then
     if [ -z $(endpoint_lookup barbican) ]; then
         openstack $INSECURE_FLAG endpoint create --region $OS_REGION_NAME $BARBICAN_SERVICE \
            --publicurl   http://$CONTROLLER:9311 \
            --adminurl    http://$CONTROLLER:9311 \
            --internalurl http://$CONTROLLER:9311
     fi
fi

KEYSTONE_SERVICE=$(get_service keystone identity "Keystone Identity Service")
if [[ -n "$ENABLE_ENDPOINTS" ]]; then
     if [ -z $(endpoint_lookup keystone) ]; then
         openstack $INSECURE_FLAG endpoint create --region $OS_REGION_NAME $KEYSTONE_SERVICE \
             --publicurl $AUTH_PROTOCOL'://'$CONTROLLER':5000/v2.0' \
             --adminurl $AUTH_PROTOCOL'://'$CONTROLLER':35357/v2.0' \
             --internalurl $AUTH_PROTOCOL'://'$CONTROLLER':35357/v2.0'
     fi
fi

CINDER_SERVICE=""
CINDER_USER=""
CINDER_SERVICE_TYPE=v2

# Create cinder service if not created in above steps
if [[ -z "$CINDER_SERVICE" ]]; then
    CINDER_SERVICE=$(get_service "cinderv2" volume "Cinder Service")
fi

# Create CINDER USER if not created in above steps
if [[ -z "$CINDER_USER" ]]; then
    CINDER_USER=$(get_service_user cinderv2)
fi

if [ -z $(user_role_lookup $CINDER_USER $SERVICE_PROJECT admin) ]; then
    openstack $INSECURE_FLAG role add \
                       --user $CINDER_USER \
                       --project $SERVICE_PROJECT \
                       $ADMIN_ROLE
fi

if [[ -n "$ENABLE_ENDPOINTS" ]]; then
     if [ -z $(endpoint_lookup cinderv2) ]; then
         openstack $INSECURE_FLAG endpoint create --region $OS_REGION_NAME $CINDER_SERVICE \
             --publicurl 'http://'$CONTROLLER':8776/'$CINDER_SERVICE_TYPE'/$(tenant_id)s' \
             --adminurl 'http://localhost:9776/'$CINDER_SERVICE_TYPE'/$(tenant_id)s' \
             --internalurl 'http://localhost:9776/'$CINDER_SERVICE_TYPE'/$(tenant_id)s'
     fi
fi

HORIZON_SERVICE=$(get_service "horizon" dashboard "OpenStack Dashboard")

if [[ -n "$ENABLE_SWIFT" ]]; then
    SWIFT_USER=$(get_service_user swift)
    SWIFT_SERVICE=$(get_service swift image "Swift Service")

    openstack $INSECURE_FLAG role add \
                           --user $SWIFT_USER \
                           --project $SERVICE_PROJECT \
                           $ADMIN_ROLE
    if [[ -n "$ENABLE_ENDPOINTS" ]]; then
         openstack $INSECURE_FLAG endpoint create --region $OS_REGION_NAME $SWIFT_SERVICE \
            --publicurl   'http://localhost:8080/v1/AUTH_$(tenant_id)s' \
            --adminurl    'http://localhost:8080/v1/AUTH_$(tenant_id)s' \
            --internalurl 'http://localhost:8080/v1/AUTH_$(tenant_id)s'
    fi
fi

if [[ -n "$ENABLE_QUANTUM" ]]; then
    QUANTUM_SERVICE=$(get_service quantum network "Quantum Service")
    QUANTUM_USER=$(get_service_user quantum)
    if [ -z $(user_role_lookup $QUANTUM_USER $SERVICE_PROJECT admin) ]; then
    openstack $INSECURE_FLAG role add \
                           --user $QUANTUM_USER \
                           --project $SERVICE_PROJECT \
                           $ADMIN_ROLE
    fi

    if [[ -n "$ENABLE_ENDPOINTS" ]]; then
         if [ -z $(endpoint_lookup quantum) ]; then
             openstack $INSECURE_FLAG endpoint create --region $OS_REGION_NAME $QUANTUM_SERVICE \
                --publicurl $AUTH_PROTOCOL://'$CONTROLLER':9696 \
                --adminurl $AUTH_PROTOCOL://'$CONTROLLER':9696 \
                --internalurl $AUTH_PROTOCOL://'$CONTROLLER':9696
	 fi
    fi
fi

if [[ -n "$ENABLE_HEAT" ]]; then
    get_role heat_stack_user
    get_role heat_stack_owner
    HEAT_SERVICE=$(get_service heat orchestration "Orchestration Service")
    HEAT_CFN_SERVICE=$(get_service heat-cfn cloudformation "Orchestration Service")
    HEAT_USER=$(get_service_user heat)
    if [ -z $(user_role_lookup $HEAT_USER $SERVICE_PROJECT admin) ]; then
    openstack $INSECURE_FLAG role add \
                           --user $HEAT_USER \
                           --project $SERVICE_PROJECT \
                           $ADMIN_ROLE
    fi

    if [[ -n "$ENABLE_ENDPOINTS" ]]; then
        if [ -z $(endpoint_lookup heat) ]; then
        openstack $INSECURE_FLAG endpoint create --region $OS_REGION_NAME $HEAT_SERVICE \
            --publicurl 'http://'$CONTROLLER':8004/v1/%(tenant_id)s' \
            --adminurl 'http://'$CONTROLLER:'8004/v1/%(tenant_id)s' \
            --internalurl 'http://'$CONTROLLER':8004/v1/%(tenant_id)s'
        fi
        if [ -z $(endpoint_lookup heat-cfn) ]; then
        openstack endpoint create --region $OS_REGION_NAME $HEAT_CFN_SERVICE \
            --publicurl 'http://'$CONTROLLER':8000/v1' \
            --adminurl 'http://'$CONTROLLER:'8000/v1' \
            --internalurl 'http://'$CONTROLLER':8000/v1'
        fi
    fi
fi

# A set of EC2-compatible credentials is created for both admin and demo
# users and placed in etc/ec2rc.
EC2RC=${EC2RC:-/etc/contrail/ec2rc}

# create ec2 creds and parse the secret and access key returned
RESULT=$(openstack $INSECURE_FLAG ec2 credentials create --user $ADMIN_USER)
ADMIN_ACCESS=`echo "$RESULT" | grep access | awk '{print $4}'`
ADMIN_SECRET=`echo "$RESULT" | grep secret | awk '{print $4}'`

RESULT=$(openstack $INSECURE_FLAG ec2 credentials create --user $DEMO_USER)
DEMO_ACCESS=`echo "$RESULT" | grep access | awk '{print $4}'`
DEMO_SECRET=`echo "$RESULT" | grep secret | awk '{print $4}'`

# write the secret and access to ec2rc
cat > $EC2RC <<EOF
ADMIN_ACCESS=$ADMIN_ACCESS
ADMIN_SECRET=$ADMIN_SECRET
DEMO_ACCESS=$DEMO_ACCESS
DEMO_SECRET=$DEMO_SECRET
EOF

