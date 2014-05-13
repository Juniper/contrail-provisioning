#!/usr/bin/python

import argparse
import ConfigParser

import os
import sys
import time
import netaddr
import subprocess
from pprint import pformat

import tempfile
from fabric.api import local, env, run
from fabric.operations import get, put
from fabric.context_managers import lcd, settings
sys.path.insert(0, os.getcwd())

class SetupNFSLivem(object):

    def __init__(self, args_str = None):
        print sys.argv[1:]
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self._parse_args(args_str)
        vm_running = 0

        nfs_livem_image = self._args.nfs_livem_image[0]
        nfs_livem_subnet = self._args.nfs_livem_subnet[0]
        nfs_livem_cidr = str (netaddr.IPNetwork('%s' %(nfs_livem_subnet)).cidr)

        #check for vm image if already present, otherwise add it
        livemnfs=local('source /etc/contrail/openstackrc && /usr/bin/glance image-list | grep livemnfs|wc -l', capture=True, shell='/bin/bash')
        if livemnfs == '1':
            print 'NFS Live migration is already configured'
        else:
            print 'NFS Live migration is yet to be configured'
            local('source /etc/contrail/openstackrc && /usr/bin/glance image-create --name livemnfs --disk-format qcow2 --container-format ovf --file %s --is-public True' %(nfs_livem_image) , capture=True, shell='/bin/bash')
            livemnfs=local('source /etc/contrail/openstackrc && /usr/bin/glance image-list | grep livemnfs|wc -l', capture=True, shell='/bin/bash')
            if livemnfs == '1':
                print 'image add success'
            else:
                return 
        
        #check for neutron network if already present, otherwise add it
        neutronnet=local('source /etc/contrail/openstackrc && neutron net-list | grep livemnfs|wc -l', capture=True, shell='/bin/bash')
        if neutronnet == '0':
            local('source /etc/contrail/openstackrc && neutron net-create livemnfs', shell='/bin/bash')

        #check for neutron subnet if already present, otherwise add it
        neutronsubnet=local('source /etc/contrail/openstackrc && neutron subnet-list | grep %s |wc -l' %(nfs_livem_cidr), capture=True, shell='/bin/bash')
        if neutronsubnet == '0':
            local('source /etc/contrail/openstackrc && neutron subnet-create --name livemnfs livemnfs %s' %(nfs_livem_cidr), shell='/bin/bash')
        net_id = livemnfs=local('source /etc/contrail/openstackrc && neutron net-list |grep livemnfs| awk \'{print $2}\'', capture=True, shell='/bin/bash')

        #check for vm if already running, otherwise start it
        vm_running=local('source /etc/contrail/openstackrc && nova list | grep livemnfs |wc -l' , capture=True, shell='/bin/bash')
        if vm_running == '0':
            local('source /etc/contrail/openstackrc && nova boot --image livemnfs --flavor 2 --nic net-id=%s livemnfs --meta storage_scope=local' %(net_id), shell='/bin/bash')
            wait_loop = 10
            while True:
                vm_running=local('source /etc/contrail/openstackrc && nova list | grep livemnfs |grep ACTIVE |wc -l' , capture=True, shell='/bin/bash')
                if vm_running == '1':
                   break
                wait_loop -= 1
                if wait_loop <= 0:
                   break
	        time.sleep(10)

        #copy nova,libvirt,kvm entries
        novapassentry = ''
        libqpassentry = ''
        libdpassentry = ''
        libgroupentry = ''
        novgroupentry = ''
        kvmgroupentry = ''

        #following are vgw configurations
        if vm_running == '1':
            vmhost = local('source /etc/contrail/openstackrc && nova show livemnfs |grep hypervisor_hostname|awk \'{print $4}\'', capture=True, shell='/bin/bash')
            vmip = local('source /etc/contrail/openstackrc && nova show livemnfs |grep \"livemnfs network\"|awk \'{print $5}\'', capture=True, shell='/bin/bash')

            for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
               if hostname == vmhost:
                   with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        #check for vgw interface
                        vgwifrunning=run('ifconfig|grep livemnfsvgw|wc -l')
                        if vgwifrunning == '0':
                            run('vif --create livemnfsvgw --mac 00:01:5e:00:00')
                            run('ifconfig livemnfsvgw up')
                        #check and add auto start of vgw interface
                        vgwifconfig=run('cat /etc/network/interfaces | grep livemnfsvgw|wc -l')
                        if vgwifconfig == '0':
                            run('echo \"\" >> /etc/network/interfaces');
                            run('echo \"auto livemnfsvgw\" >> /etc/network/interfaces');
                            run('echo \"iface livemnfsvgw inet static\" >> /etc/network/interfaces');
                            run('echo \"    pre-up vif --create livemnfsvgw --mac 00:01:5e:00:00\" >> /etc/network/interfaces');

                        #check for agent.conf
                        agentconfdone=run('cat /etc/contrail/agent.conf|grep %s|wc -l' %(nfs_livem_cidr), shell='/bin/bash') 
                        if agentconfdone == '0':
                            run('cat /etc/contrail/agent.conf  | sed \'s/<\/agent>/\\n    <gateway virtual-network="default-domain:admin:livemnfs:livemnfs"><interface>livemnfsvgw<\/interface><subnet>%s\/%s<\/subnet><\/gateway>\\n    &/g\' > /tmp/agent.conf' %(netaddr.IPNetwork(nfs_livem_cidr).ip, netaddr.IPNetwork(nfs_livem_cidr).prefixlen) , shell='/bin/bash')
                            run('cp /tmp/agent.conf /etc/contrail/agent.conf' , shell='/bin/bash')
                            run('service contrail-vrouter restart' , shell='/bin/bash')
                        #check for dynamic route on the vm host
                        dynroutedone=run('netstat -rn |grep %s|wc -l' %(netaddr.IPNetwork(nfs_livem_subnet).ip), shell='/bin/bash') 
                        if dynroutedone == '0':
                             dynroutedone=run('route add -host %s/32 dev livemnfsvgw' %(netaddr.IPNetwork(nfs_livem_subnet).ip), shell='/bin/bash') 

                        #check and add static route on the vm host
                        staroutedone=run('cat /etc/network/interfaces |grep %s|wc -l' %(netaddr.IPNetwork(nfs_livem_subnet).ip), shell='/bin/bash') 
                        if staroutedone == '0':
                             run('echo \"\" >> /etc/network/interfaces');
                             run('echo \"up route add -host %s/32 dev livemnfsvgw\" >> /etc/network/interfaces' %(netaddr.IPNetwork(nfs_livem_subnet).ip));

                        # Copy nova,libvirt,kvm entries
                        novapassentry=run('cat /etc/passwd |grep ^nova')
                        libqpassentry=run('cat /etc/passwd |grep ^libvirt-qemu')
                        libdpassentry=run('cat /etc/passwd |grep ^libvirt-dnsmasq')
                        novgroupentry=run('cat /etc/group |grep ^nova')
                        libgroupentry=run('cat /etc/group |grep ^kvm')
                        kvmgroupentry=run('cat /etc/group |grep ^libvirtd')

               #add route on other compute nodes
               elif entries != self._args.storage_master:
                   with settings(host_string = 'root@%s' %(entries), password = entry_token):
                       #check for dynamic route on the vm host
                       dynroutedone=run('netstat -rn |grep %s|wc -l' %(netaddr.IPNetwork(nfs_livem_subnet).ip), shell='/bin/bash') 
                       if dynroutedone == '0':
                           dynroutedone=run('route add %s dev vhost0' %(netaddr.IPNetwork(nfs_livem_subnet).ip), shell='/bin/bash') 
                       #check and static route on other compute
                       staroutedone=run('cat /etc/network/interfaces |grep %s|wc -l' %(netaddr.IPNetwork(nfs_livem_subnet).ip), shell='/bin/bash') 
                       if staroutedone == '0':
                             run('echo \"\" >> /etc/network/interfaces');
                             run('echo \"up route add %s dev vhost0\" >> /etc/network/interfaces' %(netaddr.IPNetwork(nfs_livem_subnet).ip));
 
               #add route on master node
               elif entries == self._args.storage_master:
                   gwentry = ''
                   for gwhostname, gwentries, sentry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                      if gwhostname == vmhost:
                          gwentry = gwentries 
                   with settings(host_string = 'root@%s' %(entries), password = entry_token):
                       #check for dynamic route on the vm host
                       dynroutedone=run('netstat -rn |grep %s|wc -l' %(netaddr.IPNetwork(nfs_livem_subnet).ip), shell='/bin/bash') 
                       if dynroutedone == '0':
                           dynroutedone=run('route add %s gw %s' %(netaddr.IPNetwork(nfs_livem_subnet).ip, gwentry), shell='/bin/bash') 
                       #check and add static route on master
                       staroutedone=run('cat /etc/network/interfaces |grep %s|wc -l' %(netaddr.IPNetwork(nfs_livem_subnet).ip), shell='/bin/bash') 
                       if staroutedone == '0':
                             run('echo \"\" >> /etc/network/interfaces');
                             run('echo \"up route add %s gw %s\" >> /etc/network/interfaces' %(netaddr.IPNetwork(nfs_livem_subnet).ip, gwentry));
             
            #cinder volume creation and attaching to VM
            avail=local('rados df | grep avail | awk  \'{ print $3 }\'', capture = True)
            # use 30% of the available space for the instances for now.
            # TODO need to check if this needs to be configurable
            avail_gb = int(avail)/1024/1024/2/3
            print avail_gb 
            if avail_gb > 1000:
                avail_gb = 1000
           
            cindervolavail=local('source /etc/contrail/openstackrc && cinder list | grep livemnfsvol |wc -l' , capture=True, shell='/bin/bash')
            if cindervolavail == '0':
                #TODO might need to add a loop similar to vm start
                local('source /etc/contrail/openstackrc && cinder create --display-name livemnfsvol --volume-type ocs-block-disk %s' %(avail_gb) , shell='/bin/bash')
                time.sleep(5)
         
                cindervolavail=local('source /etc/contrail/openstackrc && cinder list | grep livemnfsvol | grep available | wc -l' , capture=True, shell='/bin/bash')

            nova_id=local('source /etc/contrail/openstackrc &&  nova list |grep livemnfs | awk \'{print $2}\'' , capture=True, shell='/bin/bash')
            cinder_id=local('source /etc/contrail/openstackrc &&  cinder list |grep livemnfsvol | awk \'{print $2}\'' , capture=True, shell='/bin/bash')
            # Check if volume is attached to the right VM
            volvmattached=local('source /etc/contrail/openstackrc && cinder list | grep livemnfsvol | grep %s | wc -l' %(nova_id) , capture=True, shell='/bin/bash')
            if volvmattached == '0':
                # Attach volume if not yet attached
                if cindervolavail == '1':
                    local('source /etc/contrail/openstackrc && nova volume-attach %s %s /dev/vdb' %(nova_id, cinder_id) , capture=True, shell='/bin/bash')
                while True:
                    print 'Waiting for volume to be attached to VM'
                    time.sleep(5)
                    volvmattached=local('source /etc/contrail/openstackrc && cinder list | grep livemnfsvol | grep %s | wc -l' %(nova_id) , capture=True, shell='/bin/bash')
                    if volvmattached == '1':
                        break
            if volvmattached == '0':
                return

            vmavail=local('ping -c 1 %s | grep \" 0%% packet loss\" |wc -l' %(netaddr.IPNetwork(nfs_livem_subnet).ip) , capture=True, shell='/bin/bash')
            if vmavail == '1':
                print 'VM available'
            with settings(host_string = 'livemnfs@%s' %(netaddr.IPNetwork(nfs_livem_subnet).ip), password = 'livemnfs'):
                mounted=run('sudo cat /proc/mounts|grep livemnfs|wc -l')
                if mounted == '0':
                    while True:
                        vdbavail=run('sudo fdisk -l /dev/vdb |grep vdb|wc -l')
                        if vdbavail == '0':
                            print 'Disk not available yet. Need to reboot VM'
                            vdbavail=run('sudo reboot')
                            time.sleep(10)
                            while True:
                                print 'Waiting for VM to come up'
                                time.sleep(10)
                                vmavail=local('ping -c 1 %s | grep \" 0%% packet loss\" |wc -l' %(netaddr.IPNetwork(nfs_livem_subnet).ip) , capture=True, shell='/bin/bash')
                                if vmavail == '1':
                                    time.sleep(10)
                                    break
                        else:
                            break
                    vdbavail=run('sudo fdisk -l /dev/vdb 2>&1 |grep /dev/vdb|grep \"contain a valid\"|wc -l')
                    if vdbavail == '1':
                        run('sudo mkfs.xfs -f /dev/vdb')
                    run('sudo rm -rf /livemnfsvol')
                    run('sudo mkdir /livemnfsvol')
                    run('sudo mount /dev/vdb /livemnfsvol')
                    #Add to /etc/fstab for automount
                    vdbuuid=run('ls -l /dev/disk/by-uuid/ |grep vdb|awk \'{print $9}\'')
                    vdbfstab=run('cat /etc/fstab | grep %s| wc -l' %(vdbuuid))
                    if vdbfstab == '0':
                        run('sudo cp /etc/fstab /tmp/fstab')
                        run('sudo chmod  666 /tmp/fstab')
                        run('echo \"# /livemnfsvol on /dev/vdb\" >> /tmp/fstab')
                        run('echo \"UUID=%s /livemnfsvol xfs rw,noatime,attr2,delaylog,nobarrier,logbsize=256k,sunit=256,swidth=256,noquota 0 0\" >> /tmp/fstab' %(vdbuuid))
                        run('sudo chmod  644 /tmp/fstab')
                        run('sudo mv /tmp/fstab /etc/fstab')

                novaentry=run('sudo cat /etc/passwd|grep ^nova|wc -l')
                if novaentry == '0':
                    run('sudo cp /etc/passwd /tmp/passwd')
                    run('sudo chmod  666 /tmp/passwd')
                    run('sudo echo \"%s\" >> /tmp/passwd' %(novapassentry))
                    run('sudo echo \"%s\" >> /tmp/passwd' %(libqpassentry))
                    run('sudo echo \"%s\" >> /tmp/passwd' %(libdpassentry))
                    run('sudo chmod  644 /tmp/passwd')
                    run('sudo mv -f /tmp/passwd /etc/passwd')
                    run('sudo cp /etc/group /tmp/group')
                    run('sudo chmod  666 /tmp/group')
                    run('sudo echo \"%s\" >> /tmp/group' %(novgroupentry))
                    run('sudo echo \"%s\" >> /tmp/group' %(libgroupentry))
                    run('sudo echo \"%s\" >> /tmp/group' %(kvmgroupentry))
                    run('sudo chmod  644 /tmp/group')
                    run('sudo mv -f /tmp/group /etc/group')
                    run('sudo chown -R nova:nova /livemnfsvol')
                nfsexports=run('sudo cat /etc/exports |grep livemnfsvol|wc -l')
                if nfsexports == '0':
                    run('sudo cp /etc/exports /tmp/exports')
                    run('sudo chmod  666 /tmp/exports')
                    run('sudo echo \"/livemnfsvol *(rw,async,no_subtree_check,no_root_squash)\" >> /tmp/exports')
                    run('sudo chmod  644 /tmp/exports')
                    run('sudo mv -f /tmp/exports /etc/exports')
                    run('sync')
                    # restarting the vm for now. - need to check this out.
                    # need to do this only if the mounts are not done in the hosts
                    run('sudo  service nfs-kernel-server restart > /tmp/nfssrv.out', shell='/bin/bash')
                    time.sleep(2)
                    vdbavail=run('sudo reboot')
                    time.sleep(10)
                    while True:
                        print 'Waiting for VM to come up'
                        time.sleep(10)
                        vmavail=local('ping -c 1 %s | grep \" 0%% packet loss\" |wc -l' %(netaddr.IPNetwork(nfs_livem_subnet).ip) , capture=True, shell='/bin/bash')
                        if vmavail == '1':
                            time.sleep(10)
                            break

            for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
               # Not sure if mount in master is required
               # if entries != self._args.storage_master:
               with settings(host_string = 'root@%s' %(entries), password = entry_token):
                   mounted=run('cat /proc/mounts | grep livemnfsvol|wc -l')
                   if mounted == '0':
                       print mounted
                       run('ping -c 2 %s' %(netaddr.IPNetwork(nfs_livem_subnet).ip))
                       run('rm -rf /var/lib/nova/instances/global')
                       run('mkdir /var/lib/nova/instances/global')
                       run('chown nova:nova /var/lib/nova/instances/global')
                       run('mount %s:/livemnfsvol /var/lib/nova/instances/global' %(netaddr.IPNetwork(nfs_livem_subnet).ip))
                   else:
                       run('ping -c 2 %s' %(netaddr.IPNetwork(nfs_livem_subnet).ip))
                       stalenfs=run('ls /var/lib/nova/instances/global 2>&1 | grep Stale|wc -l')
                       if stalenfs == '1':
                           run('umount /var/lib/nova/instances/global')
                           run('mount %s:/livemnfsvol /var/lib/nova/instances/global' %(netaddr.IPNetwork(nfs_livem_subnet).ip))
                       
    #end __init__

    def _parse_args(self, args_str):
        '''
        Eg. python nfslivem-ceph-setup.py --storage-master 10.157.43.171 --storage-hostnames cmbu-dt05 cmbu-ixs6-2 --storage-hosts 10.157.43.171 10.157.42.166 --storage-host-tokens n1keenA n1keenA --storage-disk-config 10.157.43.171:sde 10.157.43.171:sdf 10.157.43.171:sdg --storage-directory-config 10.157.42.166:/mnt/osd0 --live-migration enabled --nfs-livem-subnet 192.168.10.0/24 --nfs-livem-image /opt/contrail/contrail_installer/livemnfs.qcow2
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help = False)

        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str.split())

        global_defaults = {
        }

        if args.conf_file:
            config = ConfigParser.SafeConfigParser()
            config.read([args.conf_file])
            global_defaults.update(dict(config.items("GLOBAL")))

        # Override with CLI options
        # Don't surpress add_help here so it will handle -h
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
            )

        all_defaults = {'global': global_defaults}
        parser.set_defaults(**all_defaults)

        parser.add_argument("--storage-master", help = "IP Address of storage master node")
        parser.add_argument("--storage-hostnames", help = "Host names of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-hosts", help = "IP Addresses of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-host-tokens", help = "Passwords of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-disk-config", help = "Disk list to be used for distrubuted storage", nargs="+", type=str)
        parser.add_argument("--storage-directory-config", help = "Directories to be sued for distributed storage", nargs="+", type=str)
        parser.add_argument("--nfs-livem-subnet", help = "subnet for nfs live migration vm", nargs="+", type=str)
        parser.add_argument("--nfs-livem-image", help = "image for nfs live migration vm", nargs="+", type=str)

        self._args = parser.parse_args(remaining_argv)

    #end _parse_args

#end class SetupCeph

def main(args_str = None):
    SetupNFSLivem(args_str)
#end main

if __name__ == "__main__":
    main() 
