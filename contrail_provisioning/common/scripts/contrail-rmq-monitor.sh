#!/bin/bash

# Purpose of the script is to check the state of RMQ
# Author - Sanju Abraham

source /etc/contrail/ha/cmon_param

readonly PROGNAME=$(basename "$0")
readonly LOCKFILE_DIR=/tmp/ha-chk
readonly LOCK_FD=200

LOGFILE=/var/log/contrail/ha/rmq-monitor.log
RMQ_CLUSTER_OK="running_nodes"
RMQ_RESET="service rabbitmq-server restart"
RMQ_REST_INPROG="rabbitmq-reset"
file="/tmp/ha-chk/rmq-chnl-ok"
cluschk="/tmp/ha-chk/rmq-clst-ok"
rstinprog="/tmp/ha-chk/rmq-rst-prog"

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
 for (( i=0; i<${DIPS_HOST_SIZE}; i++ ))
  do
    substr=${DIPHOSTS[i]}
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
 part=$(rabbitmqctl cluster_status | grep partitions | grep ctrl | wc -l)
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
for (( i=0; i<${DIPS_HOST_SIZE}; i++ ))
 do
  substr=${DIPHOSTS[i]}
  hosts=$hosts$substr"\|"
 done
i=1
while [ $i -lt  12 ]
do
 (rabbitmqctl list_channels | grep $hosts | wc -l > "$file") & pid=$!
 (rabbitmqctl cluster_status | grep -A 1 running_nodes > "$cluschk") & pid1=$!
 log_info_msg "pidof pending rmq channel $pid and cluster check $pid1"
 sleep 10
 if [ -d "/proc/${pid}" ] || [ -d "/proc/${pid1}" ]; then
  (exec kill -9 $pid)&
  (exec kill -9 $pid1)&
  i=$[$i+1]
 else
  break
 fi
done
}

checkfor_rst()
{
cluststate_run=$(verify_cluststate)
chnlstate_run=$(verify_chnlstate)
part_state=$(check_partition)
rstinpprog_run=$(verify_rstinprog)
log_info_msg "cluster state $cluststate_run and channel state $chnlstate_run"

if [[ $chnlstate_run == "n" ]] || [[ $cluststate_run == "n" ]] || [[ $part_state == "y" ]] && [[ $RABBITMQ_RESET == "True" ]]; then
 if [[ $rstinpprog_run == "n" ]]; then
   (exec $RMQ_RESET)&
   (exec echo $RMQ_REST_INPROG > "$rstinprog")&
   log_info_msg "Resetting RMQ -- Done"
 fi
fi
(exec rm -rf "$file")&
(exec rm -rf "$cluschk")&
(exec rm -rf "$rstinprog")&
}

stalels=$(ps -ef | grep rabbitmqctl | grep list_channels | awk '{print $2}')
stalecs=$(ps -ef | grep rabbitmqctl | grep cluster_status | awk '{print $2}')
(exec kill -9 "$stalels")&
(exec kill -9 "$stalecs")&

main()
{
 lock $PROGNAME \
        || eexit "Only one instance of $PROGNAME can run at one time."

 periodic_check
 checkfor_rst
}
main

exit 0
