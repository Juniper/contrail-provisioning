#!/bin/bash

# Purpose of the script is to check the state of RMQ
# Author - Sanju Abraham

source /etc/contrail/ha/cmon_param

readonly PROGNAME=$(basename "$0")
readonly LOCKFILE_DIR=/tmp/ha-chk
readonly LOCK_FD=200

readonly command=$1

LOGFILE=/var/log/contrail/ha/rmq-monitor.log
RMQ_CLUSTER_OK="running_nodes"
RMQ_RESET="service rabbitmq-server restart"
RMQ_REST_INPROG="rabbitmq-reset"
file="/tmp/ha-chk/rmq-chnl-ok"
cluschk="/tmp/ha-chk/rmq-clst-ok"
cluspart="/tmp/ha-chk/rmq-clst-part"
rstinprog="/tmp/ha-chk/rmq-rst-prog"
rstcnt="/tmp/ha-chk/rmq-rst-cnt"
numrst="/tmp/ha-chk/rmq-num-rst"
rmqstop="service rabbitmq-server stop"
killbeam="pkill -9  beam"
killepmd="pkill -9 epmd"
rmmnesia="rm -rf /var/lib/rabbitmq/mnesia"
cleanuppending="/tmp/ha-chk/rmq_mnesia_cleanup_pending"
sethapolicy="rabbitmqctl set_policy HA-all \"\" {\"ha-mode\":\"all\",\"ha-sync-mode\":\"automatic\"}"
STOP="STOP"
MYIPS=$(ip a s|sed -ne '/127.0.0.1/!{s/^[ \t]*inet[ \t]*\([0-9.]\+\)\/.*$/\1/p}')
MYIP=0
MONITOR="MONITOR"
RMQ_CLNTS=${#RMQ_CLIENTS[@]}

get_my_ip() {
flag=false
for y in $MYIPS
 do
  for (( i=0; i<${DIPS_SIZE}; i++ ))
   do
     if [ $y == ${DIPS[i]} ]; then
        MYIP=$y
        flag=true
        break
     fi
   done
   if [[ "$flag" == true ]]; then
      break
   fi
done
}
 
if [ ! -f "$LOCKFILE_DIR" ] ; then
        mkdir -p $LOCKFILE_DIR 
fi

if [ ! -f "$file" ] ; then
         touch "$file"
fi

if [ ! -f "$cluschk" ] ; then
         touch "$cluschk"
fi

if [ ! -f "$rstinprog" ] ; then
         touch "$rstinprog"
fi

if [ ! -f "$cluspart" ] ; then
          touch $cluspart
fi

if [ ! -f "$rstcnt" ] ; then
        touch $rstcnt
fi

if [ ! -f "$numrst" ] ; then
        touch $numrst
fi

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

lock() {
    local prefix=$1
    local fd=${2:-$LOCK_FD}
    local lock_file=$LOCKFILE_DIR/$prefix.lock

    # create lock file
    eval "exec $fd>$lock_file"

    # acquier the lock
    flock -n $fd \
        && return 0 \
        || return 1
}

eexit() {
    local error_str="$@"

    echo $error_str
    exit 1
}

verify_chnlstate()
{
 chnlstate=`cat $file`
 if [[ $chnlstate -gt 0 ]]; then
   echo "y"
   return 1
 else
   echo "n"
   return 0
 fi
}

verify_cluststate()
{
 cluststate=`cat $cluschk`
 cnt=0
 for (( i=0; i<${DIPS_SIZE}; i++ ))
  do
    substr=${DIPS[i]}
    for s in $cluststate; do
      if case ${s} in *"${substr}"*) true;; *) false;; esac; then
        cnt=$[cnt+1]
      fi
    done
 done
 if [ $cnt -lt 2 ]; then
        echo "n"
        return 0
     else
        echo "y"
        return 1
 fi
}

check_partition()
{
 part=`cat $cluspart`
 if [[ $part -ne 0 ]]; then
        echo "y"
        return 1
     else
        echo "n"
        return 0
 fi
}

verify_rstinprog()
{
 rstinprog=`cat $rstinprog`
 if [[ $rstinprog == $RMQ_REST_INPROG ]]; then
   echo "y"
   return 1
 else
   echo "n"
   return 0
 fi
}

periodic_check()
{
hosts=""
for (( i=0; i<${DIPS_SIZE}; i++ ))
 do
  substr=${DIPS[i]}
  hosts=$hosts$substr"\|"
 done
i=0
while [ $i -lt  5 ]
do
 (rabbitmqctl list_channels | grep $hosts | wc -l > "$file") & pid=$!
 (rabbitmqctl cluster_status | grep -A 1 running_nodes > "$cluschk") & pid1=$!
 (rabbitmqctl cluster_status | grep partitions | grep ctrl | wc -l > "$cluspart") & pid2=$!
 log_info_msg "Checking for stable state of rmq channel (monitored by pid $pid) and cluster (monitored by pid $pid1)"
 sleep 10
 if [ -d "/proc/${pid}" ]; then
  (exec pkill -TERM -P $pid)&
 fi
 if [ -d "/proc/${pid1}" ]; then
  (exec pkill -TERM -P $pid1)&
 fi
 if [ -d "/proc/${pid2}" ]; then
  (exec pkill -TERM -P $pid2)&
 fi
  i=$[$i+1]
done
}

check_total_limit()
{
  total_limit=$(rabbitmqctl status | grep total_limit | cut -d',' -f2  | cut -d'}' -f1)
  if [ "$total_limit" != 65000 ]; then
     ok=$(rabbitmqctl eval 'file_handle_cache:set_limit(65000).')
  fi
  if [ "$ok" != "ok" ]; then
     log_error_msg "Error in setting the total limit of file descriptors for rabbitmq-server"
  fi
}

cleanup()
{
 dst=$1
 if [[ $dst != '' ]]; then
   out=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 $dst "date")
   if [[ $out != '' ]]; then
     (ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 $dst "$rmqstop")
     (ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 $dst "pkill -9 beam")
     (ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 $dst "pkill -9 epmd")
     (ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 $dst "$rmmnesia")
     (ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 $dst "$RMQ_RESET")
     log_info_msg "Cleaned up mnesia and reset RMQ on $dst -- Done"
     echo "y"
   else
     echo "n"
     log_info_msg "Cleanup mnesia and reset RMQ on $dst -- PENDING"
   fi
 fi
}

rmqclientsstop()
{
  for (( i=0; i<${DIPS_SIZE}; i++ ))
   do
    for (( j=0; j<${RMQ_CLNTS}; j++ ))
     do
      (ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 ${DIPS[i]} "service ${RMQ_CLIENTS[j]} stop")
      log_info_msg "${RMQ_CLIENTS[j]} stopped on ${DIPS[i]}"
     done
   done
}

rmqclientsrestart()
{
  for (( i=0; i<${DIPS_SIZE}; i++ ))
   do
    for (( j=0; j<${RMQ_CLNTS}; j++ ))
     do
      (ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 ${DIPS[i]} "service ${RMQ_CLIENTS[j]} restart")
      log_info_msg "${RMQ_CLIENTS[j]} started on ${DIPS[i]}"
     done
   done
}

cleanpending() {
if [ -f "$cleanuppending" ] && [ -s "$cleanuppending" ] && [[ $RABBITMQ_MNESIA_CLEAN == "True" ]]; then
  readarray ips < $cleanuppending
  ipsz=${#ips[@]}
  for (( i=0; i<${ipsz}; i++ ))
   do
    status=$(ping -c 1 -w 1 -W 1 -n ${ips[i]} | grep packet | awk '{print $6}' | cut -c1)
    if [[ $status == 0 ]]; then
      rmqclientsstop
      isClean=$(cleanup "${ips[i]}")
      if [[ $isClean == "y" ]];  then
        var=$(grep -F -ve "${ips[i]}" $cleanuppending)
        echo $var > $cleanuppending
        sed -i '/^$/d' $cleanuppending
      fi
    fi
   done
else
  if [ -f "$cleanuppending" ] && [ ! -s "$cleanuppending" ]; then
    pol=$($sethapolicy)
    log_info_msg "HA Policy set - $pol"
    rmqclientsrestart
    (exec rm -rf "$cleanuppending")&
  fi
fi
}

checkNrst()
{
cluststate_run=$(verify_cluststate)
chnlstate_run=$(verify_chnlstate)
part_state=$(check_partition)
rstinpprog_run=$(verify_rstinprog)
log_info_msg "cluster state $cluststate_run and channel state $chnlstate_run"

if [[ $chnlstate_run == "n" ]] || [[ $cluststate_run == "n" ]] || [[ $part_state == "y" ]] && [[ $RABBITMQ_RESET == "True" ]]; then
 if [[ $rstinpprog_run == "n" ]]; then
   (exec echo $RMQ_REST_INPROG > "$rstinprog")&
   cnt=$(cat $rstcnt)
   if [[ $cnt == '' ]]; then
      cnt=0
   fi
   totalrst=$(cat $numrst)
   if [[ $totalrst == '' ]]; then
       totalrst=0
   fi
   if [ $totalrst == 2 ] && [[ $RABBITMQ_MNESIA_CLEAN == "True" ]]; then
    rmqclientsstop
    cleanup "$MYIP"
    for (( i=0; i<${DIPS_SIZE}; i++ ))
     do
       flag=true
       if [ $MYIP != ${DIPS[i]} ]; then
         status=$(ping -c 1 -w 1 -W 1 -n ${DIPS[i]} | grep packet | awk '{print $6}' | cut -c1)
         if [[ $status == 0 ]]; then
           isClean=$(cleanup "${DIPS[i]}")
           if [[ $isClean == "n" ]]; then
              flag=false
           fi
         else
              flag=false
         fi
         if [ "$flag" == false ]; then
           out=$(cat $cleanuppending | grep ${DIPS[i]})
           if [[ $out == '' ]]; then
             (exec echo ${DIPS[i]} >> "$cleanuppending")&
           fi
         fi
       fi
     done
     pol=$($sethapolicy)
     log_info_msg "HA Policy set - $pol"
     rmqclientsrestart
     (exec rm -rf "$numrst")&
   else
    if [ $cnt == 3 ]; then
     for (( i=0; i<${DIPS_SIZE}; i++ ))
     do
       status=$(ping -c 1 -w 1 -W 1 -n ${DIPS[i]} | grep packet | awk '{print $6}' | cut -c1)
       if [[ $status == 0 ]]; then
           (ssh -o StrictHostKeyChecking=no ${DIPS[i]} "$RMQ_RESET")
       fi
     done
     totalrst=$(($totalrst + 1))
     (exec echo $totalrst > "$numrst")&
     log_info_msg "Tried resetting all available and connected RMQ -- Done"
     (exec rm -rf "$rstcnt")&
    else
     (exec $RMQ_RESET)&
     cnt=$(($cnt + 1))
     (exec echo $cnt > "$rstcnt")&
     log_info_msg "Resetting RMQ -- Done"
    fi
   fi
 fi
fi
(exec rm -rf "$file")&
(exec rm -rf "$cluschk")&
(exec rm -rf "$cluspart")&
(exec rm -rf "$rstinprog")&
log_info_msg "check complete"
}

killstale()
{
stalels=$(ps -ef | grep rabbitmqctl | grep list_channels | awk '{print $2}')
stalecs=$(ps -ef | grep rabbitmqctl | grep cluster_status | awk '{print $2}')
if [[ $stalels != '' ]]; then
  for lpid in $stalels
   do
    (exec pkill -TERM -P $lpid)&
   done
fi
if [[ $stalecs != '' ]]; then
  for cpid in $stalecs
   do
    (exec pkill -TERM -P $cpid)&
   done
fi
}

function run_rmq_monitor()
{
 check_total_limit
 periodic_check
 cleanpending
 checkNrst
 killstale
}

function run_onzk_lock_acquire {
ZK_IPPORTS="$ZK_SERVER_IP" python - <<END
import os
import socket
import subprocess
import sys, getopt
from kazoo.client import KazooClient
zk_ip_ports=os.environ['ZK_IPPORTS']
zk=KazooClient(zk_ip_ports)
zk.start()
lock=zk.Lock('/rmq-monitor','%s-%d' % (socket.gethostname(),os.getpid()))
with lock:
   subprocess.call("/opt/contrail/bin/contrail-rmq-monitor.sh MONITOR", shell=True)
   lock.release()
END
}

main()
{
 if [[ $command == $MONITOR ]]; then
    run_rmq_monitor
 else
  lock $PROGNAME \
        || eexit "Only one instance of $PROGNAME can run at one time."
  if [[ $command == $STOP ]]; then
    $rmqstop
    $killbeam
    $killepmd
  else
    run_onzk_lock_acquire
  fi
 fi
 exit 0
}

main
