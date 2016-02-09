import string

template = string.Template("""
[global]
;WEB_SERVER = 127.0.0.1
;WEB_PORT = 9696  ; connection through quantum plugin

WEB_SERVER = $__contrail_apiserver_ip__
WEB_PORT = 8082 ; connection to api-server directly
BASE_URL = /
;BASE_URL = /tenants/infra ; common-prefix for all URLs
#insecure=False
#certfile=/etc/contrail/ssl/certs/apiserver.pem
#keyfile=/etc/contrail/ssl/private/apiserver_key.pem
#cafile=/etc/contrail/ssl/certs/apiserver_ca.pem

; Authentication settings (optional)
[auth]
AUTHN_TYPE = keystone
AUTHN_PROTOCOL = http
AUTHN_SERVER=$__contrail_keystone_ip__
AUTHN_PORT = 35357
AUTHN_URL = $__contrail_authn_url__
#insecure=False
#certfile=/etc/contrail/ssl/certs/keystone.pem
#keyfile=/etc/contrail/ssl/private/keystone_key.pem
#cafile=/etc/contrail/ssl/certs/keystone_ca.pem
""")

