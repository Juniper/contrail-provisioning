import string

template = string.Template("""
# stackrc
#
CONTRAIL_USERNAME='tedghose:contrailsystemsWelc0me5Efckb0j!'

# Find the other rc files
RC_DIR=$(cd $(dirname "$BASH_SOURCE") && pwd)

# Destination path for installation
DEST=/opt/stack

# Specify which services to launch.  These generally correspond to
# screen tabs. To change the default list, use the ``enable_service`` and
# ``disable_service`` functions in ``localrc``.
# For example, to enable Swift add this to ``localrc``:
# enable_service swift
#
# And to disable Cinder and use Nova Volumes instead:
# disable_service c-api c-sch c-vol cinder
# enable_service n-vol
ENABLED_SERVICES=g-api,g-reg,key,n-api,n-crt,n-obj,n-cpu,n-net,cinder,c-sch,c-api,c-vol,n-sch,n-novnc,n-xvnc,n-cauth,horizon,mysql,cass,zk,ifmap,apiSrv,schma,rabbit

# Set the default Nova APIs to enable
NOVA_ENABLED_APIS=ec2,osapi_compute,osapi_volume,metadata

# Repositories
# ------------

# Base GIT Repo URL
# Another option is http://review.openstack.org/p
GIT_BASE=https://github.com

# metering service
CEILOMETER_REPO=https://github.com/stackforge/ceilometer.git
CEILOMETER_BRANCH=master

# volume service
CINDER_REPO=${GIT_BASE}/openstack/cinder
CINDER_BRANCH=master

# volume client
CINDERCLIENT_REPO=${GIT_BASE}/openstack/python-cinderclient
CINDERCLIENT_BRANCH=master

# compute service
NOVA_REPO=https://${CONTRAIL_USERNAME}@bitbucket.org/contrail_admin/nova.git
NOVA_BRANCH=master

# storage service
SWIFT_REPO=${GIT_BASE}/openstack/swift.git
SWIFT_BRANCH=master
SWIFT3_REPO=https://github.com/fujita/swift3.git
SWIFT3_BRANCH=master

# python swift client library
SWIFTCLIENT_REPO=${GIT_BASE}/openstack/python-swiftclient
SWIFTCLIENT_BRANCH=master

# image catalog service
GLANCE_REPO=${GIT_BASE}/openstack/glance.git
GLANCE_BRANCH=master

# python glance client library
GLANCECLIENT_REPO=${GIT_BASE}/openstack/python-glanceclient
GLANCECLIENT_BRANCH=master

# unified auth system (manages accounts/tokens)
KEYSTONE_REPO=https://${CONTRAIL_USERNAME}@bitbucket.org/contrail_admin/keystone.git
KEYSTONE_BRANCH=master

# a websockets/html5 or flash powered VNC console for vm instances
NOVNC_REPO=https://${CONTRAIL_USERNAME}@bitbucket.org/contrail_admin/noVNC.git
NOVNC_BRANCH=master

# django powered web control panel for openstack
HORIZON_REPO=https://${CONTRAIL_USERNAME}@bitbucket.org/contrail_admin/horizon.git
HORIZON_BRANCH=master

# python client library to nova that horizon (and others) use
NOVACLIENT_REPO=${GIT_BASE}/openstack/python-novaclient.git
NOVACLIENT_BRANCH=master

# consolidated openstack python client
OPENSTACKCLIENT_REPO=${GIT_BASE}/openstack/python-openstackclient.git
OPENSTACKCLIENT_BRANCH=master

# python keystone client library to nova that horizon uses
KEYSTONECLIENT_REPO=${GIT_BASE}/openstack/python-keystoneclient
KEYSTONECLIENT_BRANCH=master

# quantum service
QUANTUM_REPO=https://${CONTRAIL_USERNAME}@bitbucket.org/contrail_admin/quantum.git
QUANTUM_BRANCH=master

# quantum client
QUANTUM_CLIENT_REPO=https://${CONTRAIL_USERNAME}@bitbucket.org/contrail_admin/python-quantumclient.git
QUANTUM_CLIENT_BRANCH=master

# Tempest test suite
TEMPEST_REPO=${GIT_BASE}/openstack/tempest.git
TEMPEST_BRANCH=master

# heat service
HEAT_REPO=${GIT_BASE}/heat-api/heat.git
HEAT_BRANCH=master

# ryu service
RYU_REPO=https://github.com/osrg/ryu.git
RYU_BRANCH=master

# Nova hypervisor configuration.  We default to libvirt with **kvm** but will
# drop back to **qemu** if we are unable to load the kvm module.  ``stack.sh`` can
# also install an **LXC** or **OpenVZ** based system.
VIRT_DRIVER=${VIRT_DRIVER:-libvirt}
LIBVIRT_TYPE=${LIBVIRT_TYPE:-kvm}

# allow local overrides of env variables
if [ -f $RC_DIR/localrc ]; then
    source $RC_DIR/localrc
fi

# Specify a comma-separated list of UEC images to download and install into glance.
# supported urls here are:
#  * "uec-style" images:
#     If the file ends in .tar.gz, uncompress the tarball and and select the first
#     .img file inside it as the image.  If present, use "*-vmlinuz*" as the kernel
#     and "*-initrd*" as the ramdisk
#     example: http://cloud-images.ubuntu.com/releases/oneiric/release/ubuntu-11.10-server-cloudimg-amd64.tar.gz
#  * disk image (*.img,*.img.gz)
#    if file ends in .img, then it will be uploaded and registered as a to
#    glance as a disk image.  If it ends in .gz, it is uncompressed first.
#    example:
#      http://cloud-images.ubuntu.com/releases/oneiric/release/ubuntu-11.10-server-cloudimg-armel-disk1.img
#      http://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-x86_64-rootfs.img.gz
#  * OpenVZ image:
#    OpenVZ uses its own format of image, and does not support UEC style images

#IMAGE_URLS="http://smoser.brickies.net/ubuntu/ttylinux-uec/ttylinux-uec-amd64-11.2_2.6.35-15_1.tar.gz" # old ttylinux-uec image
#IMAGE_URLS="http://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-x86_64-disk.img" # cirros full disk image

# Set default image based on ``VIRT_DRIVER`` and ``LIBVIRT_TYPE``, either of
# which may be set in ``localrc``.  Also allow ``DEFAULT_IMAGE_NAME`` and 
# ``IMAGE_URLS`` to be set directly in ``localrc``.
case "$VIRT_DRIVER" in
    openvz) 
        DEFAULT_IMAGE_NAME=${DEFAULT_IMAGE_NAME:-ubuntu-11.10-x86_64}
        IMAGE_URLS=${IMAGE_URLS:-"http://download.openvz.org/template/precreated/ubuntu-11.10-x86_64.tar.gz"};;
    libvirt)
        case "$LIBVIRT_TYPE" in
            lxc) # the cirros root disk in the uec tarball is empty, so it will not work for lxc
                DEFAULT_IMAGE_NAME=${DEFAULT_IMAGE_NAME:-cirros-0.3.0-x86_64-rootfs}
                IMAGE_URLS=${IMAGE_URLS:-"http://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-x86_64-rootfs.img.gz"};;
            *) # otherwise, use the uec style image (with kernel, ramdisk, disk)
                DEFAULT_IMAGE_NAME=${DEFAULT_IMAGE_NAME:-cirros-0.3.0-x86_64-uec}
                IMAGE_URLS=${IMAGE_URLS:-"http://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-x86_64-uec.tar.gz"};;
        esac
        ;;
    *) # otherwise, use the uec style image (with kernel, ramdisk, disk)
        DEFAULT_IMAGE_NAME=${DEFAULT_IMAGE_NAME:-cirros-0.3.0-x86_64-uec}
        IMAGE_URLS=${IMAGE_URLS:-"http://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-x86_64-uec.tar.gz"};;
esac

# 5Gb default volume backing file size
VOLUME_BACKING_FILE_SIZE=${VOLUME_BACKING_FILE_SIZE:-5130M}

# contrail 
#
CONTRAIL_DIR=/opt/contrail
CONTRAIL_CASS_DIR=/opt/cassandra
CONTRAIL_ZOO_DIR=/opt/zookeeper
API_SERVER_IP=$__contrail_api_server_ip__
API_SERVER_PORT=$__contrail_api_server_port__

""")
