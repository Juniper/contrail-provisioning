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
$__contrail_memcached_opt__
insecure=$__keystone_insecure_flag__
$__keystone_cert_file_opt__
$__keystone_key_file_opt__
$__keystone_ca_file_opt__
""")
