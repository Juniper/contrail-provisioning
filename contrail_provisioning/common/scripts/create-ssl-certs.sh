#!/bin/bash
#
# Copyright (c) 2016 Juniper Networks, Inc. All rights reserved.
#
# Used for generating Self Signed Certificates
# Contributor - Sanju Abraham

set -x

setbins() {
if [ -f "/usr/bin/openssl" ] ; then
			OPENSSL="/usr/bin/openssl"
		else
			OPENSSL="/usr/local/ssl/bin/openssl"
fi

  PRINTF="/usr/bin/printf"
  MKDIR="/bin/mkdir"
  TOUCH="/bin/touch"
  RM="/bin/rm"
  CP="/bin/cp"
  ECHO="/bin/echo -e"
  CAT="/bin/cat"
  CHOWN="/bin/chown"
}

argc=$#
NODE_IP=$1
SSL_PATH=$2
CERT_FILE_PREFIX=$3
SAN=$4

SANS=$SAN,$NODE_IP
IFS=',' read -ra SAN_LIST <<< "$SANS"
for i in "${!SAN_LIST[@]}"; do
    SAN_IPS=$(echo "$SAN_IPS\nIP.$(($i+2)) = ${SAN_LIST[$i]}")
done


main() {
    if [ "$argc" -lt 3 ]; then
        echo "Usage: $0 NODE_IP SSL_PATH CERT_FILE_PREFIX";
        echo "Example: $0 10.1.1.100 /etc/contrail/ssl/ apiserver";
        exit 1;
    fi

	$MKDIR working
	cd working
	creatCFGFile
	$MKDIR key
#Generate Keys

	$OPENSSL genrsa -aes128  -out key/private.key -passout pass:changeit  1024

#Convert to PKCS8

	$OPENSSL pkcs8 -in key/private.key -topk8 -nocrypt -out key/privatep8.key -passin pass:changeit

#Create CA Certificate
	 
	 $MKDIR cacert
	 $OPENSSL req -config cfg/openssl.cfg -new -x509 -days 3650 -key key/privatep8.key -out cacert/ca.cer -batch
#Create CSR 

	 $MKDIR req
	 $OPENSSL req -new -key key/privatep8.key -out req/client.csr -config cfg/openssl.cfg -batch
	 $OPENSSL req -new -key key/privatep8.key -out req/server.csr -config cfg/openssl.cfg -batch

#Create CA signed cert from CSR

    $MKDIR certs
	$TOUCH database.txt database.txt.attr serial.txt
	$ECHO 01 > serial.txt
	$OPENSSL ca -policy policy_anything -config cfg/openssl.cfg -cert cacert/ca.cer -in req/client.csr -keyfile key/privatep8.key -days 3650 -extensions v3_req -out certs/client.crt -batch

	$RM -f database.*
	$TOUCH database.txt database.txt.attr 
    $OPENSSL ca -policy policy_anything -config cfg/openssl.cfg -cert cacert/ca.cer -in req/server.csr -keyfile key/privatep8.key -days 3650 -extensions v3_req -out certs/server.crt -batch
    $RM -f database.*
    $RM -f serial.txt 
#Convert from PEM to DER both Ca cert and Ca signed Cert

	$OPENSSL x509 -in certs/client.crt -inform PEM -outform DER -out client.der -extensions v3_req
		
	$OPENSSL x509 -in cacert/ca.cer -inform PEM -outform DER -out ca.der -extensions v3_req

#Create Root and server pem files 
	
   $CP -f cacert/ca.cer "$CERT_FILE_PREFIX"_ca.pem
   $TOUCH "$CERT_FILE_PREFIX".pem
   $TOUCH "$CERT_FILE_PREFIX".key
   $CAT key/privatep8.key > "$CERT_FILE_PREFIX".key
   $CAT key/privatep8.key > "$CERT_FILE_PREFIX".pem
   $CAT certs/server.crt >> "$CERT_FILE_PREFIX".pem
   cd ../
   mkdir -p $SSL_PATH/private/
   chmod 755 $SSL_PATH/private/
   mkdir -p $SSL_PATH/certs/
   chmod 755 $SSL_PATH/certs
   $CP working/"$CERT_FILE_PREFIX".key $SSL_PATH/private/
   $CP working/"$CERT_FILE_PREFIX".pem $SSL_PATH/certs/
   $CP working/"$CERT_FILE_PREFIX"_ca.pem $SSL_PATH/certs/
   $RM -rf working
   $CHOWN -R $CERT_FILE_PREFIX:$CERT_FILE_PREFIX $SSL_PATH
}

creatCFGFile(){
	$MKDIR cfg
	$TOUCH cfg/openssl.cfg
	$ECHO "[ new_oids ]
			[ ca ]
default_ca              = CA_default
# The default ca section
[ CA_default ]

certs           = certs                 # Where the issued certs are kept
crl_dir         = crl                   # Where the issued crl are kept
database        = database.txt          # database index file.
new_certs_dir   = certs                 # default place for new certs.

certificate     = cacert.pem            # The CA certificate
serial          = serial.txt            # The current serial number

default_days    = 365                   # how long to certify for
default_crl_days= 30                    # how long before next CRL
default_md      = sha1                  # which md to use.
preserve        = no                    # keep passed DN ordering

# A few difference way of specifying how similar the request should look
# For type CA, the listed attributes must be the same, and the optional
# and supplied fields are just that :-)
policy          = policy_match

# For the CA policy
[ policy_match ]
countryName                     = match
stateOrProvinceName             = match
organizationName                = match
organizationalUnitName          = optional
commonName                      = supplied
emailAddress                    = optional

# For the 'anything' policy
# At this point in time, you must list all acceptable 'object'
# types.
[ policy_anything ]
countryName                     = optional
stateOrProvinceName             = optional
localityName                    = optional
organizationName                = optional
organizationalUnitName          = optional
commonName                      = supplied
emailAddress                    = optional

####################################################################
[ req ]
default_bits                    = 1024
default_keyfile                 = privkey.pem
distinguished_name              = req_distinguished_name
attributes                      = req_attributes
x509_extensions = v3_ca # The extentions to add to the self signed cert
req_extensions = v3_req
[ req_distinguished_name ]
countryName                             = Country Name (2 letter code)
countryName_min                         = 2
countryName_max                         = 2
stateOrProvinceName                     = State or Province Name (full name)
localityName                            = Locality Name (eg, city)
0.organizationName                      = Organization Name (eg, company)
commonName                              = Common Name (eg, YOUR name)

#Default certificate generation filelds
organizationalUnitName_default          = Juniper Contrail
0.organizationName_default              = OpenContrail
stateOrProvinceName_default             = California
localityName_default                    = Sunnyvale
countryName_default                     = US
commonName_default                      = $NODE_IP
commonName_max                          = 64
emailAddress                            = Email Address
emailAddress_default                    = admin@juniper.com
emailAddress_max                        = 40

[ v3_req ]
# Extensions to add to a certificate request
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
$SAN_IPS

# SET-ex3                               = SET extension number 3
[ req_attributes ]
challengePassword                       = A challenge password
challengePassword_min                   = 4
challengePassword_max                   = 20
unstructuredName                        = An optional company name
[ usr_cert ]
basicConstraints=CA:FALSE
nsComment                       = "OpenSSL Generated Certificate"
# PKIX recommendations harmless if included in all certificates.
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer:always
[ v3_ca]
# Extensions for a typical CA
# PKIX recommendation.
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid:always,issuer:always
basicConstraints = CA:true
[ crl_ext ]
authorityKeyIdentifier=keyid:always,issuer:always
" > cfg/openssl.cfg
	
}
setbins

main
