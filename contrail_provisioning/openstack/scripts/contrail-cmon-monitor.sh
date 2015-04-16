#!/bin/bash

# Purpose of the script is to check the state of galera cluster
# Author - Sanju Abraham

source /etc/contrail/ha/cmon_param

LOGFILE=/var/log/contrail/ha/cmon-monitor.log
MYIPS=$(ip a s|sed -ne '/127.0.0.1/!{s/^[ \t]*inet[ \t]*\([0-9.]\+\)\/.*$/\1/p}')
RUN_STATE="isrunning"
CMON_SVC_CHECK=$(pgrep -xf '/usr/local/cmon/sbin/cmon -r /var/run/cmon')
RUN_CMON="service cmon start"
STOP_CMON="service cmon stop"
mysql_host=$VIP
mysql_port=33306
MYSQL_SVC_CHECK="service mysql status"
HAP_RESTART="service haproxy restart"
cmon_run=0
viponme=0
eviponme=0
haprestart=0
RMQ_MONITOR="/opt/contrail/bin/contrail-rmq-monitor.sh"

NOVA_SCHED_CHK="supervisorctl -s unix:///tmp/supervisord_openstack.sock status nova-scheduler"
NOVA_CONS_CHK="supervisorctl -s unix:///tmp/supervisord_openstack.sock status nova-console"
NOVA_CONSAUTH_CHK="supervisorctl -s unix:///tmp/supervisord_openstack.sock status nova-consoleauth"
NOVA_COND_CHK="supervisorctl -s unix:///tmp/supervisord_openstack.sock status nova-conductor"
CIND_SCHED_CHK="supervisorctl -s unix:///tmp/supervisord_openstack.sock status cinder-scheduler"
NOVA_SCHED_RST="service nova-scheduler restart"
NOVA_CONS_RST="service nova-console restart"
NOVA_CONSAUTH_RST="service nova-consoleauth restart"
NOVA_COND_RST="service nova-conductor restart"
NOVA_COND_STOP="service nova-conductor stop"
NOVA_COND_START="service nova-conductor start"
NOVA_COND_STATUS="service nova-conductor status"
NOVA_SCHED_STOP="service nova-scheduler stop"
NOVA_SCHED_START="service nova-scheduler start"
NOVA_SCHED_STATUS="service nova-scheduler status"
CIND_SCHED_RST="service cinder-scheduler restart"
NOVA_RUN_STATE="RUNNING"
STATE_EXITED="EXITED"
STATE_FATAL="FATAL"
cmon_user_pass="cmon"

timestamp() {
    date +"%T"
}

log_error_msg() {
    msg=$1
    echo "$(timestamp): ERROR: $msg" >> $LOGFILE
}

log_warn_msg() {
    msg=$1
    echo "$(timestamp): WARNING: $msg" >> $LOGFILE
}

log_info_msg() {
    msg=$1
    echo "$(timestamp): INFO: $msg" >> $LOGFILE
}

for y in $MYIPS
 do
  if [ $y == $VIP ]; then
     viponme=1
     log_info_msg "VIP - $VIP is on this node"
  fi
  if [ $y == $EVIP ]; then
     eviponme=1
     log_info_msg "EVIP - $EVIP is on this node"
  fi
  if [ $viponme == 1 ] && [ $eviponme == 1 ]; then
     break
  fi
 done

# This is to prevent a bug in keepalived
# that does not remove VRRP IP on it being down
ka=$(pidof keepalived)
kps=$(wc -w <<< "$ka")
if [[ $kps == 0 ]]; then
   if [ $viponme == 1 ]; then
      intf=$(ip a | grep $VIP | awk '{print $6}')
      icmd="ip addr del $VIP dev $intf"
      log_info_msg "Deleting stale iVIP"
      (exec $icmd)&
   fi
   if [ $eviponme == 1 ]; then
      entf=$(ip a | grep $EVIP | awk '{print $6}')
      ecmd="ip addr del $EVIP dev $entf"
      log_info_msg "Deleting stale eVIP"
      (exec $ecmd)&
   fi
fi

verify_mysql() {
   mysqlsvc=$($MYSQL_SVC_CHECK | awk '{print $3 $4}') 
   mysqlpid=$(pidof mysqld)
   if [ $mysqlsvc == $RUN_STATE ] && [ -n "$mysqlpid" ]; then
      log_info_msg "MySQL is Running"
      echo "y"
      return 1
   else
      log_info_msg "MySQL is not Running"
      echo "n"
      return 0
   fi
   exit 1
}

verify_cmon() {
   cmon=$CMON_SVC_CHECK
   cmonpid=$(pidof cmon)
   if [ $cmon == $cmonpid ] && [ -n "$cmonpid" ]; then
      log_info_msg "CMON is Running"
      echo "y"
      return 1
   else
      log_info_msg "CMON is not Running"
      echo "n"
      return 0
   fi
}

verify_nova_cond() {
  cond=$($NOVA_COND_STATUS | awk '{print $2}')
  if [ $cond == $NOVA_RUN_STATE ]; then
     echo "y"
     return 1
  else
     echo "n"
     return 0
  fi
}

verify_nova_sched() {
  sched=$($NOVA_SCHED_STATUS | awk '{print $2}')
  if [ $sched == $NOVA_RUN_STATE ]; then
     echo "y"
     return 1
  else
     echo "n"
     return 0
  fi
}

  # These checks will eventually be replaced when we have nodemgr plugged in
  # for openstack services
  # CHECK FOR NOVA SCHD
  state=$($NOVA_SCHED_CHK | awk '{print $2}')
  if [ "$state" == "$STATE_EXITED" ] || [ "$state" == "$STATE_FATAL" ]; then
     (exec $NOVA_SCHED_RST)&
     log_info_msg "Nova Scheduler restarted becuase of the state $state"
  fi

  # CHECK FOR NOVA CONS
  state=$($NOVA_CONS_CHK | awk '{print $2}')
  if [ "$state" == "$STATE_EXITED" ] || [ "$state" == "$STATE_FATAL" ]; then
     (exec $NOVA_CONS_RST)&
     log_info_msg "Nova Console restarted becuase of the state $state"
  fi

  # CHECK FOR NOVA CONSAUTH
  state=$($NOVA_CONSAUTH_CHK | awk '{print $2}')
  if [ "$state" == "$STATE_EXITED" ] || [ "$state" == "$STATE_FATAL" ]; then
     (exec $NOVA_CONSAUTH_RST)&
     log_info_msg "Nova ConsoleAuth restarted becuase of the state $state"
  fi

  # CHECK FOR NOVA COND
  state=$($NOVA_COND_CHK | awk '{print $2}')
  if [ "$state" == "$STATE_EXITED" ] || [ "$state" == "$STATE_FATAL" ]; then
     (exec $NOVA_COND_RST)&
     log_info_msg "Nova Conductor restarted becuase of the state $state"
  fi

  # CHECK FOR CINDER SCHD
  state=$($CIND_SCHED_CHK | awk '{print $2}')
  if [ "$state" == "$STATE_EXITED" ] || [ "$state" == "$STATE_FATAL" ]; then
     (exec $CIND_SCHED_RST)&
     log_info_msg "Cinder Scheduler restarted becuase of the state $state"
  fi

cmon_run=$(verify_cmon)
# Check for cmon and if its the VIP node let cmon run or start it
if [ $viponme -eq 1 ]; then
   if [ $cmon_run == "n" ]; then
      (exec $RUN_CMON)&
      log_info_msg "Started CMON on detecting VIP"
      (exec $RMQ_MONITOR)&
    fi
   # Check periodically for RMQ status
   if [[ -n "$PERIODIC_RMQ_CHK_INTER" ]]; then
      sleep $PERIODIC_RMQ_CHK_INTER
      (exec $RMQ_MONITOR)&
   fi
else
   if [ $cmon_run == "y" ]; then
      (exec $STOP_CMON)&
      log_info_msg "Stopped CMON on not finding VIP"

      #Check if the VIP was on this node and clear all session by restarting haproxy
      hapid=$(pidof haproxy)
      for (( i=0; i<${DIPS_SIZE}; i++ ))
      do
        dipsonnonvip=$(lsof -p $hapid | grep ${DIPS[i]} | awk '{print $9}')
        if [[ -n "$dipsonnonvip" ]]; then
         haprestart=1
         break
        fi
      done

      for (( i=0; i<${DIPS_HOST_SIZE}; i++ ))
      do
        dipsonnonvip=$(lsof -p $hapid | grep ${DIPHOSTS[i]} | awk '{print $9}')
        if [[ -n "$dipsonnonvip" ]]; then
         haprestart=1
         break
        fi
      done

      if [ $haprestart -eq 1 ]; then
       (exec $HAP_RESTART)&
       log_info_msg "Restarted HAP becuase of stale dips"
      fi
   fi
fi
      
#Cleanup if there exists sockets in CLOSE_WAIT
clssoc=$(netstat -natp | grep 33306 | grep CLOSE_WAIT | wc -l)
if [[ $clssoc -ne 0 ]]; then
   netstat -anp |\
   grep ':33306 ' |\
   grep CLOSE_WAIT |\
   awk '{print $7}' |\
   cut -d \/ -f1 |\
   grep -oE "[[:digit:]]{1,}" |\
   xargs kill -9
   log_info_msg "Cleaned connections to mysql that were in CLOSE_WAIT"
fi

exit 0
