#!/usr/bin/env bash
set -x

function check_db_connectivity () {
    exit_on_error=true
    db_cmd=mysql
    eval $1
    if [[ -z $db_root_pw ]]; then
        echo "ERROR: One or more required params are missing"
        echo "ERROR: Required Args: db_root_pw($db_root_pw)"
        exit 2
    fi
    echo "SELECT 1;" | $db_cmd -u root -p$db_root_pw > /dev/null
    if [ $? != 0 ] && [[ $(echo $exit_on_error | tr '[:upper:]' '[:lower:]') == "true" ]]; then
        echo "ERROR: DB Connectivity with db_root_pw($db_root_pw) Failed"
        exit 1
    fi

}

function is_user_db_exists () {
    exit_on_error=true
    db_cmd=mysql
    eval $1
    if [[ -z $db_user ]] || [[ -z $db_root_pw ]]; then
        echo "ERROR: One or more required params are missing"
        echo "ERROR: Required Args: db_user($db_user) db_root_pw($db_root_pw)"
        exit 2
    fi
    db_count=$(echo "SELECT COUNT(*) FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='$db_user';" |
               $db_cmd -u root -p$db_root_pw | tail -n+2)
    if [ $? != 0 ] && [[ $(echo $exit_on_error | tr '[:upper:]' '[:lower:]') == "true" ]]; then
        echo "ERROR: Check User DB exists with db_root_pw($db_root_pw) Failed"
        exit 1
    fi

    if [ "$db_count" != 0 ]; then
        return 0
    else
        return 1
    fi
}

function is_db_user_exists () {
    exit_on_error=true
    db_cmd=mysql
    eval $1
    if [[ -z $db_user ]] || [[ -z $db_root_pw ]]; then
        echo "ERROR: One or more required params are missing"
        echo "ERROR: Required Args: db_user($db_user) db_root_pw($db_root_pw)"
        exit 2
    fi
    user_count=$(echo "SELECT COUNT(*) FROM $db_cmd.user WHERE User = '$db_user';" |
                 $db_cmd -u root -p$db_root_pw | tail -n+2)
    if [ $? != 0 ] && [[ $(echo $exit_on_error | tr '[:upper:]' '[:lower:]') == "true" ]]; then
        echo "ERROR: DB Connectivity with db_root_pw($db_root_pw) Failed"
        exit 1
    fi

    if [ "$user_count" != 0 ]; then
        return 0
    else
        return 1
    fi
}

#
#
#
function create_user_db () {
    exit_on_error=true
    db_cmd=mysql
    eval $1
    # Default to db_user
    if [[ -z $db_username ]]; then
        db_username=$db_user
    fi
    if [[ -z $db_user ]] || [[ -z $db_username ]] || [[ -z $db_user_pw ]] || [[ -z $db_root_pw ]] ; then
        echo "ERROR: One or more required params are missing"
        echo "ERROR: db_user($db_user) db_username($db_username) db_user_pw($db_user_pw) db_root_pw($db_root_pw)"
        exit 2
    fi
cat << EOF
CREATE DATABASE $db_user;
GRANT ALL PRIVILEGES ON $db_user.* TO '$db_username'@'localhost' IDENTIFIED BY '$db_user_pw';
GRANT ALL PRIVILEGES ON $db_user.* TO '$db_username'@'%' IDENTIFIED BY '$db_user_pw';
EOF
cat << EOF | $db_cmd -u root -p$db_root_pw
CREATE DATABASE $db_user;
GRANT ALL PRIVILEGES ON $db_user.* TO '$db_username'@'localhost' IDENTIFIED BY '$db_user_pw';
GRANT ALL PRIVILEGES ON $db_user.* TO '$db_username'@'%' IDENTIFIED BY '$db_user_pw';
EOF
    if [ $? != 0 ] && [[ $(echo $exit_on_error | tr '[:upper:]' '[:lower:]') == "true" ]]; then
        echo "ERROR: Create DB with db_user($db_user) db_user_pw($db_user_pw) db_root_pw($db_root_pw) FAILED"
        exit 1
    fi
}

function create_db_user () {
    exit_on_error=true
    db_cmd=mysql
    eval $1
    # set user name as default pw if passwd for user is not given
    if [[ -z $db_user_pw ]]; then
        db_user_pw=$db_user
    fi

    if [[ -z $db_user ]] || [[ -z $db_user_pw ]] || [[ -z $db_root_pw ]]; then
        echo "ERROR: One or more required params are missing"
        echo "ERROR: Required Args: db_user($db_user) db_user_pw($db_user_pw) db_root_pw($db_root_pw)"
        echo exit 2
    fi
cat << EOF
CREATE USER '$db_user'@'localhost' IDENTIFIED BY '$db_user_pw';
CREATE USER '$db_user'@'%' IDENTIFIED BY '$db_user_pw';
EOF
cat << EOF | $db_cmd -u root -p$db_root_pw
CREATE USER '$db_user'@'localhost' IDENTIFIED BY '$db_user_pw';
CREATE USER '$db_user'@'%' IDENTIFIED BY '$db_user_pw';
EOF
    if [ $? != 0 ] && [[ $(echo $exit_on_error | tr '[:upper:]' '[:lower:]') == "true" ]]; then
        echo "ERROR: Create User with db_user($db_user) db_user_pw($db_user_pw) db_root_pw($db_root_pw) Failed"
        exit 1
    fi
}

function user_db_sync () {
    exit_on_error=true
    eval $1
    if [[ -z $db_username ]]; then
        db_username=$db_name
    fi
    if [[ -z $db_name ]] || [[ -z $db_username ]]; then
        echo "ERROR: One or more required params are missing"
        echo "ERROR: db_name($db_name) db_username($db_username)"
        echo exit 2
    fi
    su -s /bin/sh -c "nova-manage $db_name sync" $db_username
    if [ $? != 0 ] && [[ $(echo $exit_on_error | tr '[:upper:]' '[:lower:]') == "true" ]]; then
        echo "ERROR: nova-manage with db_name($db_name)"
        exit 1
    fi
}

function create_endpoint () {
    exit_on_error=true
    region="RegionOne"
    admin_user="admin"
    eval $1
    if  [[ -z $service_user ]] || [[ -z $region ]] || \
        [[ -z $service_name ]] || [[ -z $url ]] || \
        [[ -z $admin_user ]] ; then
        echo "ERROR: One or more required params are missing"
        echo "ERROR: region($region) service_name($service_name) url($url)"
        echo "ERROR: service_user($service_user) admin_user($admin_user)"
        exit 2
    fi
    openstack user create --domain default --password-prompt $service_user
    openstack role add --project $service_name --user $service_user admin
    openstack service create --name $service_user --description "$service_name" $service_name
    openstack endpoint create --region $region $service_name public $url
    openstack endpoint create --region $region $service_name internal $url
    openstack endpoint create --region $region $service_name admin $url
}

function drop_user_db () {
    exit_on_error=true
    db_cmd=mysql
    eval $1
    if [[ -z $db_name ]] || [[ -z $db_cmd ]] || [[ -z $db_root_pw ]]; then
        echo "ERROR: One or more required params are missing"
        echo "ERROR: db_name($db_name) db_cmd($db_cmd) db_root_pw($db_root_pw)"
        exit 2
    fi
    echo "DROP DATABASE IF EXISTS $db_name;" | $db_cmd -u root -p$db_root_pw
    if [ $? != 0 ] && [[ $(echo $exit_on_error | tr '[:upper:]' '[:lower:]') == "true" ]]; then
        echo "ERROR: Drop DB ($db_name) with db_name($db_name) db_root_pw($db_root_pw) Failed"
        exit 1
    fi
}

function drop_db_user () {
    exit_on_error=true
    db_cmd=mysql
    eval $1
    if [[ -z $db_user ]] || [[ -z $db_root_pw ]]; then
        echo "ERROR: One or more required params are missing"
        echo "ERROR: Required Args: db_user($db_user) db_root_pw($db_root_pw)"
        exit 2
    fi
    echo "SELECT User,Host FROM $db_cmd.user WHERE User = '$db_user';" |
    $db_cmd -u root -p$db_root_pw |
    sed -n "s/\($db_user\)[\t ]*\(.*\)/DROP USER '\1'@'\2';/p" |
    $db_cmd -u root -p$db_root_pw
    if [ $? != 0 ] && [[ $(echo $exit_on_error | tr '[:upper:]' '[:lower:]') == "true" ]]; then
        echo "ERROR: Drop User ($db_user) with db_user($db_user) db_root_pw($db_root_pw) Failed"
        exit 1
    fi
}

function contrail_openstack_db () {
    exit_on_error=true
    eval $1
    # Verify DB Connectivity
    check_db_connectivity "db_root_pw=$db_root_pw;"

    # Create User. Skip if exists already
    is_db_user_exists "db_user=$db_user;db_root_pw=$db_root_pw;"
    if [[ $? -eq 1 ]]; then
        create_db_user "db_user=$db_user;db_username=$db_username;db_user_pw=$db_user_pw;db_root_pw=$db_root_pw;"
    fi

    # Create User DB. Skip if exists already
    is_user_db_exists "db_user=$db_user;db_root_pw=$db_root_pw;"
    if [[ $? -eq 1 ]]; then
        create_user_db "db_user=$db_user;db_username=$db_username;db_user_pw=$db_user_pw;db_root_pw=$db_root_pw;"
    fi
    echo "User DB for DB User ($db_user) created succesfully"

    user_db_sync "db_name=$db_name;db_username=$db_username"
    echo "User DB for DB User ($db_user) is Synced successfully"
}
