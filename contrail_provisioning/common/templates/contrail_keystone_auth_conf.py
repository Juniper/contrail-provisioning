import string

template = string.Template("""
[KEYSTONE]
auth_url=$__contrail_ks_auth_url__
auth_host=$__contrail_keystone_ip__
auth_protocol=$__contrail_ks_auth_protocol__
auth_port=$__contrail_ks_auth_port__
admin_user=$__contrail_admin_user__
admin_password=$__contrail_admin_password__
admin_tenant_name=$__contrail_admin_tenant_name__
insecure=$__keystone_insecure_flag__
$__contrail_memcached_opt__
#insecure=False
#certfile=/etc/contrail/ssl/certs/keystone.pem
#keyfile=/etc/contrail/ssl/private/keystone_key.pem
#cafile=/etc/contrail/ssl/certs/keystone_ca.pem
""")
