import string

template = string.Template("""
[APISERVER]
api_server_ip = $__contrail_api_server_ip__
api_server_port = $__contrail_api_server_port__
contrail_extensions = $__contrail_extensions__
multi_tenancy = $__contrail_multi_tenancy__

[KEYSTONE]
;auth_url = http://$__contrail_keystone_ip__:35357/v2.0
;admin_token = $__contrail_admin_token__
admin_user=$__contrail_admin_user__
admin_password=$__contrail_admin_password__
admin_tenant_name=$__contrail_admin_tenant_name__
""")
