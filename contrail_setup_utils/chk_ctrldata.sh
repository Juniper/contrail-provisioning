#!/bin/bash

# Purpose of the script is to check the control/data network
# Author - Sanju Abraham

source /etc/contrail/ha/cmon_param

MYIPS=$(ip a s|sed -ne '/127.0.0.1/!{s/^[ \t]*inet[ \t]*\([0-9.]\+\)\/.*$/\1/p}')
MYIP=0
ret=0
viponme=0

for y in $MYIPS
 do
  for (( i=0; i<${DIPS_SIZE}; i++ ))
   do
     if [ $y == ${DIPS[i]} ]; then
        MYIP=$y
     fi
     if [ $y == $VIP ]; then
       viponme=1
     fi
   done
 done

status[${DIPS_SIZE}]=0

for (( i=0; i<${DIPS_SIZE}; i++ ))
 do
   if [ $MYIP != ${DIPS[i]} ]; then
       status[i]=$(ping -c 1 -w 1 -W 1 -n ${DIPS[i]} | grep packet | awk '{print $6}' | cut -c1)
   fi
 done

for (( i=0; i<${#status[@]}; i++ ))
 do
  if [[ ${status[i]} == 0 ]]; then
    ret=0
    break
  else
    ret=1
  fi
 done


if [[ $ret == 0 ]]; then
 exit 0
else
 exit 1
fi
