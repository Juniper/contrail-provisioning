import string

template = string.Template("""
[KEYSTONE]
auth_host=$__contrail_keystone_ip__
auth_protocol=$__contrail_ks_auth_protocol__
auth_port=$__contrail_ks_auth_port__
admin_user=$__contrail_admin_user__
admin_password=$__contrail_admin_password__
admin_token=$__contrail_admin_token__
admin_tenant_name=$__contrail_admin_tenant_name__
insecure=$__keystone_insecure_flag__
$__contrail_memcached_opt__
""")
