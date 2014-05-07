#!/usr/bin/env bash

# set livemigration configurations in nova and libvirtd
openstack-config --set /etc/nova/nova.conf DEFAULT live_migration VIR_MIGRATE_UNDEFINE_SOURCE,VIR_MIGRATE_PEER2PEER,VIR_MIGRATE_LIVE
openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_listen 0.0.0.0
cat /etc/libvirt/libvirtd.conf | sed s/"#listen_tls = 0"/"listen_tls = 0"/ | sed s/"#listen_tcp = 1"/"listen_tcp = 1"/ | sed s/"#auth_tcp = \"sasl\""/"auth_tcp = \"none\""/ > /tmp/libvirtd.conf
cp -f /tmp/libvirtd.conf /etc/libvirt/libvirtd.conf
cat /etc/sysconfig/libvirtd | sed s/"#LIBVIRTD_ARGS=\"--listen\""/"LIBVIRTD_ARGS=\"--listen\""/ > /tmp/libvirtd
cp -f /tmp/libvirtd /etc/sysconfig/libvirtd

for svc in openstack-nova-compute; do
    service $svc restart
done

for svc in libvirtd; do
    service $svc restart
done
