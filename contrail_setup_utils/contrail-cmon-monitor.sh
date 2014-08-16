#!/bin/bash

# Purpose of the script is to check the state of galera cluster
# Author - Sanju Abraham

source /etc/contrail/ha/cmon_param

LOGFILE=/var/log/contrail/ha/cmon-monitor.log
MYIPS=$(ip a s|sed -ne '/127.0.0.1/!{s/^[ \t]*inet[ \t]*\([0-9.]\+\)\/.*$/\1/p}')
RUN_STATE="isrunning"
CMON_SVC_CHECK="service cmon status"
RUN_CMON="service cmon start"
STOP_CMON="service cmon stop"
MYSQL_SVC_CHECK="service mysql status"
HAP_RESTART="service haproxy restart"
ARP_CACHE_FLUSH="arp -d $VIP"
cmon_run=0
viponme=0
haprestart=0
RMQ_CONSUMERS="rabbitmqctl list_consumers"
NOVA_COMPUTE_RESTART="service nova-compute restart"

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
     break
  fi
 done

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
}

verify_cmon() {
   cmon=$($CMON_SVC_CHECK | awk '{print $2 $3}')
   cmonpid=$(pidof cmon)
   if [ $cmon == $RUN_STATE ] && [ -n "$cmonpid" ]; then
      log_info_msg "CMON is Running"
      echo "y"
      return 1
   else
      log_info_msg "CMON is not Running"
      echo "n"
      return 0
   fi
}

cmon_run=$(verify_cmon)
# Check for cmon and if its the VIP node let cmon run or start it
if [ $viponme -eq 1 ]; then
   if [ $cmon_run == "n" ]; then
      $RUN_CMON  
      log_info_msg "Started CMON on detecting VIP"

      for (( i=0; i<${COMPUTES_SIZE}; i++ ))
       do
        (exec ssh -o StrictHostKeyChecking=no "$COMPUTES_USER@${COMPUTES[i]}" "$ARP_CACHE_FLUSH")&
        log_info_msg "ARP clean up for VIP on ${COMPUTES[i]}"
       done

       for (( i=0; i<${DIPS_SIZE}; i++ ))
        do
         (exec ssh -o StrictHostKeyChecking=no "$COMPUTES_USER@${DIPS[i]}" "$ARP_CACHE_FLUSH")&
         log_info_msg "ARP clean up for VIP on ${DIPS[i]}"
        done
    fi

   for (( i=0; i<${COMPUTES_SIZE}; i++ ))
    do
      compconsumer=$($RMQ_CONSUMERS | grep compute.${COMPUTES[i]} | awk '{print $1}')
      if [[ -z "$compconsumer" ]]; then
        echo "'$COMPUTES_USER@${COMPUTES[i]}'"
        (exec ssh -o StrictHostKeyChecking=no "$COMPUTES_USER@${COMPUTES[i]}" "$NOVA_COMPUTE_RESTART")&
        log_info_msg "Nova compute consumer recovery on ${COMPUTES[i]}"
      fi
    done
else
   if [ $cmon_run == "y" ]; then
      $STOP_CMON
      log_info_msg "Stopped CMON on not finding VIP"
   fi

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

    if [ $haprestart -eq 1 ]; then
       $HAP_RESTART
       log_info_msg "Restarted HAP becuase of stale dips"
    fi
fi
      
exit 0
