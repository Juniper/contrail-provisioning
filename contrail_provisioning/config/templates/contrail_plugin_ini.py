import string

template = string.Template("""
[APISERVER]
api_server_ip = $__contrail_api_server_ip__
api_server_port = $__contrail_api_server_port__
multi_tenancy = $__contrail_multi_tenancy__
#use_ssl = False
#insecure = False
#certfile=$__contrail_api_server_cert_file__
#keyfile=$__contrail_api_server_key_file__
#cafile=$__contrail_api_server_ca_file__
$__contrail_cloud_admin_role__
$__contrail_aaa_mode__
contrail_extensions = ipam:neutron_plugin_contrail.plugins.opencontrail.contrail_plugin_ipam.NeutronPluginContrailIpam,policy:neutron_plugin_contrail.plugins.opencontrail.contrail_plugin_policy.NeutronPluginContrailPolicy,route-table:neutron_plugin_contrail.plugins.opencontrail.contrail_plugin_vpc.NeutronPluginContrailVpc,contrail:None,service-interface:None,vf-binding:None

[COLLECTOR]
analytics_api_ip = $__contrail_analytics_server_ip__
analytics_api_port = $__contrail_analytics_server_port__

[KEYSTONE]
auth_url = $__contrail_ks_auth_protocol__://$__contrail_keystone_ip__:$__contrail_ks_auth_port__/v2.0
admin_user=$__contrail_admin_user__
admin_password=$__contrail_admin_password__
admin_tenant_name=$__contrail_admin_tenant_name__
""")
