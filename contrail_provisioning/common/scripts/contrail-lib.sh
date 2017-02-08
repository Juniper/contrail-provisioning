#!/usr/bin/env bash

#
# checks if the target node is ubuntu based system
# Verdict: echo True if the target node is ubuntu based system 
#
function is_ubuntu () {
    [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release && echo True || echo False
}

#
# Starts supervisor-openstack services but all its child
# Arguments:
#
function listen_on_supervisor_openstack_port () {
    # centos/rhel based target nodes runs systemd initsytem and
    # and supervisor-openstack is no longer supported on them
    if [ $(is_ubuntu) == "True" ]; then
        # Listen at supervisor-openstack port
        status=$(service supervisor-openstack status | grep -s -i running >/dev/null 2>&1  && echo "running" || echo "stopped")
        if [ $status == 'stopped' ]; then
            service supervisor-openstack start
            sleep 5
            if [ -e /tmp/supervisord_openstack.sock ]; then
                supervisorctl -s unix:///tmp/supervisord_openstack.sock stop all
            else
                supervisorctl -s unix:///var/run/supervisord_openstack.sock stop all
            fi
        fi
    fi
}

#
# Update services for the given action with sytemctl or service
# command based on its initsystem
# Keyword Arguments:
#     action - action to be applied to the service
#              eg: enable, start, stop, restart...
#     exit_on_error - exits the function in case of failure
#                     Default: true
# Arguments:
#     services - one or list of services to be acted on
#
# Eg:
# update_services "action=enable;exit_on_error=false" keystone
#     systemd: will run "systemctl enable keystone" and ignores systemctl exit status
#     sysv:    will run "chkconfig keystone on" and ignores systemctl exit status
#
function update_services () {
    exit_on_error=false
    eval $1
    if [[ -z $action ]] || [[ -z $exit_on_error ]]; then
        echo "ERROR: One or more required params are missing"
        echo "ERROR: Required Args: action($action) exit_on_error($exit_on_error)"
        exit 1
    fi
    exit_on_error=$(echo $exit_on_error | tr '[:upper:]' '[:lower:]')
    for service_name in "${@:2}"; do
        if [ $(is_ubuntu) == "True" ]; then
            if (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
                systemctl $action "$service_name"
            else
                if [ "$action" == "enable" ]; then
                    chkconfig $service_name on
                else
                    service $service_name $action
                fi
            fi
        else
            systemctl $action "$service_name"
        fi

        if [ $? != 0 ] && [ "$exit_on_error" != "false" ] ; then
            echo "ERROR: "$action" service ( $service_name ) failed!"
            exit 1
        fi
    done
}

#
# Check if version of given rpm package is higher than
# the reference version
# Arguments:
#     package_name: Name of the installed rpm package
#     reference_version: Reference version to be compared
#                        Format: '<epoch-number> <version> <release>'
# Returns:
# 0 - if the version of rpm package higher or equal to reference version
# 1 - if the version of rpm package is lower than the reference version
#
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

#
# Function to retrieve mysql service name
# Centos7/Rhel7 are using mariadb instead of mysqld
# 
function get_mysql_service_name () {
    [ -e /usr/lib/systemd/system/mariadb.service ] && echo mariadb || echo mysqld
}

# print error message and exit
function error_exit
{   
    echo "${PROGNAME}: ${1:-''} ${2:-'Unknown Error'}" 1>&2
    exit ${3:-1}
}

