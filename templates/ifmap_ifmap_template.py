import string

template = string.Template("""
#Sun May 27 15:36:23 PDT 2012
irond.comm.basicauth.port=$__contrail_ifmap_basicauth_port__
irond.comm.certauth.port=8444
irond.comm.rawlog=false
irond.ifmap.casesensitive.sipUri=true
irond.auth.cert.truststore.pass=mapserver
irond.proc.event.forwarders=2
irond.ifmap.casesensitive.telUri=true
irond.ifmap.restrict.purgepublisher=true
irond.proc.event.workers=4
irond.ifmap.casesensitive.hipHit=true
irond.ifmap.casesensitive.administrativedomain=true
irond.proc.action.workers=1
irond.xml.schema.0=schema/soap12.xsd
irond.xml.validate=true
irond.ifmap.casesensitive.trustedPlatformModule=true
irond.proc.action.forwarders=1
irond.ifmap.casesensitive.userName=true
irond.ifmap.casesensitive.aikName=true
irond.ifmap.session.timeout=180
irond.ifmap.default.maxpollresultsize=5000000
irond.auth.basic.users.file=/etc/ifmap-server/basicauthusers.properties
irond.ifmap.default.searchresultsize=100000
irond.auth.cert.keystore.file=/etc/ifmap-server/keystore/irond.jks
irond.ifmap.casesensitive.emailAddress=true
irond.ifmap.casesensitive.distinguishedName=true
irond.ifmap.casesensitive.dnsName=true
irond.auth.cert.keystore.pass=mapserver
irond.ifmap.casesensitive.other=true
irond.ifmap.casesensitive.kerberosPrincipal=true
irond.ifmap.default.sanitychecks=false
irond.ifmap.publishers.file=publisher.properties
irond.ifmap.authorization.file=authorization.properties
irond.ifmap.publishers.file=/etc/ifmap-server/publisher.properties
irond.ifmap.authorization.file=/etc/ifmap-server/authorization.properties
irond.auth.cert.truststore.file=/etc/ifmap-server/keystore/irond.jks
# Limit the size of a search result
irond.ifmap.default.maxperpollresultsize=8192
irond.ifmap.default.splitinitialsearchresult=true
irond.ifmap.default.droponresultstoobig=false

""")
