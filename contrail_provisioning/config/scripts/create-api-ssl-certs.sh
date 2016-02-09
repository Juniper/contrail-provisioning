#!/bin/sh
#
# Copyright (c) 2016 Juniper Networks, Inc. All rights reserved.
#
# Script to generate Self Signed Certificates for Api server

argc=$#
API_VIP=$1
SSL_PATH=/etc/contrail/ssl/
CERT_FILE_PREFIX=contrail

if [ "$argc" -eq 0 ]; then
    echo "Usage: $0 API_VIP";
    echo "Example: $0 10.1.1.100";
    exit 1;
fi

#Generate Certs
create-ssl-certs.sh $API_VIP $SSL_PATH $CERT_FILE_PREFIX
