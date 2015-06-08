#!/bin/bash

# Purpose of the script is to check the state of galera cluster
# Author - Sanju Abraham

source /etc/contrail/ha/cmon_param

LOGFILE=/var/log/contrail/ha/cmon-monitor.log
MYIPS=$(ip a s|sed -ne '/127.0.0.1/!{s/^[ \t]*inet[ \t]*\([0-9.]\+\)\/.*$/\1/p}')
MYIP=0
RUN_STATE="isrunning"
CMON_SVC_CHECK=$(pgrep -xf '/usr/local/cmon/sbin/cmon -r /var/run/cmon')
RUN_CMON="service cmon start"
STOP_CMON="service cmon stop"
RESTART_CMON="service cmon restart"
mysql_host=$VIP
mysql_port=33306
MYSQL_SVC_CHECK="service mysql status"
MYSQL_SVC_STOP="service mysql stop"
HAP_RESTART="service haproxy restart"
cmon_run=0
viponme=0
eviponme=0
haprestart=0
galerastate=0
recluster=false
RMQ_MONITOR="/opt/contrail/bin/contrail-rmq-monitor.sh"
RMQ_MONITOR_STOP="/opt/contrail/bin/contrail-rmq-monitor.sh STOP"
rstcnt="/tmp/ha-chk/rmq-rst-cnt"
numrst="/tmp/ha-chk/rmq-num-rst"
cleanuppending="/tmp/ha-chk/rmq_mnesia_cleanup_pending"
MYID="/etc/contrail/galeraid"
cmonerror="CmonCron could not initialize"
cmonlog="/var/log/cmon.log"

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
GTID_FILE="/tmp/galera/gtid"
GALERA_BOOT="/opt/contrail/bin/contrail-bootstrap-galera.sh DONOR"
MYSQL_USERNAME="cmon"
MYSQL_PASSWORD="cmon"
MYSQL_BIN="/usr/bin/mysql"
MYSQL_WSREP_STATE="show status like 'wsrep_local_state';"
MYSQL_CLUSTER_STATE="show status like 'wsrep_cluster_status';"
SYNCED=4
STATUS="Primary"
RMQ_SRVR_STATUS="supervisorctl -s unix:///tmp/supervisord_support_service.sock status rabbitmq-server"
RMQ_SRVR_RST="supervisorctl -s unix:///tmp/supervisord_support_service.sock restart rabbitmq-server"
RECLUSTER="/opt/contrail/bin/contrail-bootstrap-galera.sh"
ERROR2002="Can't connect to local MySQL server"
ERROR1205="Lock wait timeout exceeded"
STDERR="/tmp/galera-chk/stderr"
RECLUSTRUN="/tmp/galera/recluster"
RMQSTOP="/tmp/ha-chk/rmqstopped"
cmondisco="/etc/mysql/.cmondiscoinit"

timestamp() {
    date
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

#Failure supported
cSize=$((${DIPS_SIZE} - 1))
nFailures=$(($cSize / 2))

vip_info() {
for y in $MYIPS
 do
  for (( i=0; i<${DIPS_SIZE}; i++ ))
   do
     if [ $y == ${DIPS[i]} ]; then
        MYIP=$y
     fi
   done
done

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
}

ka_vip_del() {
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
}

galera_check()
{
  for (( i=0; i<${DIPS_SIZE}; i++ ))
   do
       wval=$($MYSQL_BIN --connect_timeout 10 -u $MYSQL_USERNAME -p${MYSQL_PASSWORD} -h ${DIPS[i]} -e "$MYSQL_WSREP_STATE" | awk '{print $2}' | sed '1d')
       cval=$($MYSQL_BIN --connect_timeout 10 -u $MYSQL_USERNAME -p${MYSQL_PASSWORD} -h ${DIPS[i]} -e "$MYSQL_CLUSTER_STATE" | awk '{print $2}' | sed '1d')
     if [[ $wval == $SYNCED ]] & [[ $cval == $STATUS ]]; then
        ret="y"
        break
     else
        ret="n"
     fi
   done
   echo $ret
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

procs_check() {
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

  # CHECK FOR RMQ STATUS
  state=$($RMQ_SRVR_STATUS | awk '{print $2}')
  if [ "$state" == "$STATE_EXITED" ] || [ "$state" == "$STATE_FATAL" ]; then
     (exec $RMQ_SRVR_RST)&
     log_info_msg "RabbitMQ restarted becuase of the state $state"
  fi
}

bootstrap() {
# Check for the state of mysql and remove any
# stale gtid files
galerastate=$(galera_check)
if [ $galerastate == "y" ]; then
     if [ -f $GTID_FILE ]; then
      (exec rm -rf $GTID_FILE)&
      log_info_msg "Removed GTID file"
     fi
     if [ -f $RECLUSTRUN ]; then
       (exec rm -rf $RECLUSTRUN)&
       log_info_msg "Removed recluster file"
     fi
else
  if [ ! -f $GTID_FILE ] && [ -z "$mypid" ]; then
      recluster=true
  fi
fi

if [ -f $GTID_FILE ]; then
   for (( i=0; i<${DIPS_SIZE}; i++ ))
   do
        gtidfile=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 ${DIPS[i]} "ls $GTID_FILE | cut -d "/" -f 4")
        if [[ $gtidfile != "" ]]; then
          gtid[i]=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 ${DIPS[i]} "cat $GTID_FILE")
        fi
   done

 gtids=${#gtid[@]}
 if [ $gtids -gt $nFailures ]; then
    flag=true;
 else
    flag=false;
    log_info_msg "Insufficient GTID information to bootstrap"
 fi

 if [[ "$flag" == true ]]; then
   big=${gtid[0]} pos=0
   for i in "${!gtid[@]}"; do
	(( ${gtid[i]} > big )) && big=${gtid[i]} pos=$i
   done

   if [ $MYIP == ${DIPS[$pos]} ]; then
      log_info_msg "Bootstrapping Galera node - $MYIP with GTID - ${gtid[$pos]}"
      (exec $GALERA_BOOT)&
   fi
 fi
fi
}

chkNRun_cluster_mon() {
cmon_run=$(verify_cmon)
# Check for cmon and if its the VIP node let cmon run or start it
if [ $viponme -eq 1 ]; then
   if [ $cmon_run == "n" ]; then
      (exec $RUN_CMON)&
      log_info_msg "Started CMON on detecting VIP"
    fi
   # Check periodically for RMQ status
   if [[ -n "$PERIODIC_RMQ_CHK_INTER" ]]; then
      sleep $PERIODIC_RMQ_CHK_INTER
      (exec $RMQ_MONITOR)&
   fi
   cerr=$(grep "$cmonerror" "$cmonlog" | wc -l)
   if [[ $cerr != 0 ]]; then
     (exec rm -rf "$cmonlog")&
     (exec $RESTART_CMON)&
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
   if [ -f $cleanuppending ]; then
     (exec rm -rf $cleanuppending)&
   fi
   if [ -f $rstcnt]; then
     (exec rm -rf $rstcnt)&
   fi
   if [ -f $numrst]; then
     (exec rm -rf $numrst)&
   fi
fi
}
      
cleanup() {
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
}

reCluster() {
# RE-CLUSTER
noconn=0
for (( i=0; i<${DIPS_SIZE}; i++ ))
 do
   status[i]=$(ping -c 1 -w 1 -W 1 -n ${DIPS[i]} | grep packet | awk '{print $6}' | cut -c1)
 done

for (( i=0; i<${#status[@]}; i++ ))
 do
  if [[ ${status[i]} == 1 ]]; then
    ((noconn++))
  fi
 done

mypid=$(pidof mysqld)
if [ -n "$mypid" ] && [ $galerastate == "n" ]; then
   $MYSQL_BIN --connect_timeout 5 -u $MYSQL_USERNAME -p${MYSQL_PASSWORD} -e "$MYSQL_WSREP_STATE" 2> >( cat <() > $STDERR)
   err1=$(cat $STDERR | grep "$ERROR2002" | awk '{print $2}')
   err2=$(cat $STDERR | grep "$ERROR1205" | awk '{print $2}')
   if [[ $err1 == 2002 ]] || [[ $err2 == 1205 ]]; then
      recluster=true
   fi
   (exec rm -rf "$STDERR")&
fi

if [ ! -f $RECLUSTRUN ]; then
  if [ $noconn -ge $cSize ] || [[ "$recluster" == true ]]; then
    log_info_msg "Connectivity lost with $noconn peers"
    log_info_msg "Mysql Galera Error $err1 $err2 requires reclustering"
    log_info_msg "Reclustering MySql Galera"
    (exec $RECLUSTER)&
    touch $RECLUSTRUN
  fi
fi

epmd=$(pidof epmd)
if [ $noconn -ge $cSize ] && [ -n "$epmd" ]; then
   log_info_msg "Stop RMQ"
   (exec $RMQ_MONITOR_STOP)&
   touch $RMQSTOP
else
   if [ -f $RMQSTOP ]; then
     (exec $RMQ_SRVR_RST)&
     (exec rm -rf $RMQSTOP)&
   fi
fi
}

cmonFailDomainDiscovery() {
if [ -f $MYID ]; then
    myid=$(cat $MYID)
fi
if [[ $myid == 1 ]] && [ $galerastate == "y" ]; then
 if [ ! -f $cmondisco ]; then
   for (( i=0; i<${DIPS_SIZE}; i++ ))
     do
      if [ $MYIP != ${DIPS[i]} ]; then
         (ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 ${DIPS[i]} "$MYSQL_SVC_STOP")
      fi
     done
   touch "$cmondisco"
 fi
fi
}

main()
{
  vip_info
  bootstrap
  chkNRun_cluster_mon
  ka_vip_del
  procs_check
  cleanup
  reCluster
  cmonFailDomainDiscovery
  exit 0
}
main

