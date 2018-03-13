#!/bin/bash

# VARIABLES
STOREPASS=${storepass:-"c0ntrail123"}
KEYPASS=${keypass:-"c0ntrail123"}
NODES=${nodes:-""}
VALIDITY=${validity:-36500}
COUNTRY=${country:-"US"}
ORGANIZATION=${org:-"contrail"}
DISTINGUISHED_NAME=${dn:-"contrail"}
ORGANIZATIONALUNITNAME=${ou:-"TestCluster"}

CONF_DIR=${ca_conf_dir:-"/usr/local/lib/cassandra/conf"}
ROOT_CA_CONF_FILE=${CONF_DIR}/rootCa_cert.conf
ROOT_CA_KEY_FILE=${CONF_DIR}/rootCa.key
ROOT_CA_CERT_FILE=${CONF_DIR}/rootCa.crt
SERVER_STORE=${CONF_DIR}/truststore.jks
CASSANDRA_YAML=${cassandra_yaml:-"/etc/cassandra/cassandra.yaml"}
CREATE_KEYS=${create_keys:-False}
CLEANUP=${cleanup:-False}
UPDATE_CASSANDRA_CONFIGS=${update_cassandra_configs:-False}
PROTOCOL=${protocol:-"TLS"}
ALGORITHM=${algorithm:-"SunX509"}
STORE_TYPE=${store_type:-"JKS"}
CIPHER_SUITES=${cipher_suites:-"[TLS_RSA_WITH_AES_256_CBC_SHA]"}

exit_on_error () {
    echo "Executing Command:: $@"
    eval $@
    if [ $? != 0 ]; then
        echo "ERROR: ${cmd} FAILED"
        exit 1
    fi
}

create_conf_dir () {
    if ! [ -d ${CONF_DIR} ]; then
        mkdir -p ${CONF_DIR}
    fi
}

change_ownership () {
    chown -R cassandra:cassandra ${CONF_DIR}
}

# OPENSSL CONFIG
create_openssl_config () {
cat << EOF > ${ROOT_CA_CONF_FILE}
# generate rootCa_cert.conf
[ req ]
distinguished_name = ${DISTINGUISHED_NAME}
prompt = no
output_password = ${KEYPASS}
default_bits = 2048

[ contrail ]
C = ${COUNTRY}
O = ${ORGANIZATION}
OU = ${ORGANIZATIONALUNITNAME}
CN = rootCa
EOF
}

# Create CA Cert
create_ca_cert () {
    echo "Create CA Cert"
	exit_on_error openssl req -config ${ROOT_CA_CONF_FILE} \
		-new -x509 \
		-nodes \
		-keyout ${ROOT_CA_KEY_FILE} \
		-out ${ROOT_CA_CERT_FILE} \
		-days ${VALIDITY}
}

# Create one keystore per node
create_key_stores () {
    for nodeip in $NODES; do
        node_store=${CONF_DIR}/${nodeip}.jks
		echo "Generate pub/private key and keystore for each node ($nodeip)"
		exit_on_error keytool -genkeypair \
			-keyalg RSA \
			-alias ${nodeip} \
			-keystore ${node_store} \
			-storepass ${STOREPASS} \
			-keypass ${KEYPASS} \
			-validity ${VALIDITY} \
			-keysize 2048 \
			-dname \
			'"CN=${nodeip},OU=${ORGANIZATIONALUNITNAME},O=${ORGANIZATION},C=${COUNTRY}"' 

		echo "Export singing request for node ($nodeip)"
		exit_on_error keytool -certreq \
			-keystore ${node_store} \
			-alias ${nodeip} \
			-file ${CONF_DIR}/${nodeip}.csr \
			-keypass ${KEYPASS} \
			-storepass ${STOREPASS} \
			-dname \
			"CN=${nodeip},OU=${ORGANIZATIONALUNITNAME},O=${ORGANIZATION},C=${COUNTRY}"  

		echo "Sign node cert with rootCa for node ($nodeip)"
		exit_on_error openssl x509 -req \
			-CA ${ROOT_CA_CERT_FILE} \
			-CAkey ${ROOT_CA_KEY_FILE} \
			-in ${CONF_DIR}/${nodeip}.csr \
			-out ${CONF_DIR}/${nodeip}.crt_signed \
			-days ${VALIDITY} \
			-CAcreateserial \
			-passin pass:${KEYPASS}

		echo "Verify singing for node ($nodeip)"
		exit_on_error openssl verify -CAfile ${ROOT_CA_CERT_FILE} ${CONF_DIR}/${nodeip}.crt_signed

		echo "Import rootCa cert to node ($nodeip) keystore"
		exit_on_error keytool -importcert \
			-keystore ${node_store} \
			-alias rootCa \
			-file ${ROOT_CA_CERT_FILE} \
			-noprompt \
			-keypass ${KEYPASS} \
			-storepass ${STOREPASS}  

		echo "Import node's signed cert into node ($nodeip) keystore"
		exit_on_error keytool -importcert \
			-keystore ${node_store} \
			-alias ${nodeip} \
			-file ${CONF_DIR}/${nodeip}.crt_signed \
			-noprompt \
			-keypass ${KEYPASS} \
			-storepass ${STOREPASS} 
	done
}

# Create Server Truststore
create_server_truststore () {
    echo "Create Server Truststore"
	exit_on_error keytool -importcert \
		-keystore ${SERVER_STORE} \
		-alias rootCa \
		-file ${ROOT_CA_CERT_FILE} \
		-noprompt \
		-keypass ${KEYPASS} \
		-storepass ${STOREPASS}
}

create_all_keys () {
    create_conf_dir
    create_openssl_config
    create_ca_cert
    create_key_stores
    create_server_truststore
    change_ownership
}

cleanup () {
    set -x
    rm -f ${CONF_DIR}/truststore.jks
    rm -f ${CONF_DIR}/rootCa.srl
    rm -f ${CONF_DIR}/rootCa.crt
    rm -f ${CONF_DIR}/rootCa.key
    rm -f ${CONF_DIR}/rootCa_cert.conf
    for node in ${NODES}; do
        rm -f ${CONF_DIR}/${node}.jks
        rm -f ${CONF_DIR}/${node}.crt_signed
        rm -f ${CONF_DIR}/${node}.csr
    done
    set +x
}

update_cassandra_config () {
    contrail-config --set ${CASSANDRA_YAML} \
        client_encryption_options \
        enabled true
    contrail-config --set ${CASSANDRA_YAML} \
        client_encryption_options \
        optional false
    contrail-config --set ${CASSANDRA_YAML} \
        client_encryption_options \
        keystore_password ${KEYPASS}
    contrail-config --set ${CASSANDRA_YAML} \
        client_encryption_options \
        require_client_auth true
    contrail-config --set ${CASSANDRA_YAML} \
        client_encryption_options \
        truststore ${SERVER_STORE}
    contrail-config --set ${CASSANDRA_YAML} \
        client_encryption_options \
        truststore_password ${STOREPASS}
    contrail-config --set ${CASSANDRA_YAML} \
        client_encryption_options \
        protocol ${PROTOCOL}
    contrail-config --set ${CASSANDRA_YAML} \
        client_encryption_options \
        algorithm ${ALGORITHM}
    contrail-config --set ${CASSANDRA_YAML} \
        client_encryption_options \
        store_type ${STORE_TYPE}
    contrail-config --set ${CASSANDRA_YAML} \
        client_encryption_options \
        cipher_suites ${CIPHER_SUITES}
    for node in ${NODES}; do
        contrail-config --set ${CASSANDRA_YAML} \
            client_encryption_options \
            keystore ${node}.jks
    done
}

if [[ ${CLEANUP,,} == "true" ]]; then
    cleanup
fi

if [[ ${CREATE_KEYS,,} == "true" ]]; then
    create_all_keys
fi

if [[ ${UPDATE_CASSANDRA_CONFIGS} == "true" ]]; then
    update_cassandra_config
fi
