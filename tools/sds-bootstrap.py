#!/usr/bin/env python

# @EXE_PREFIX@-bootstrap.py, a script initating a local configuration of OpenIO SDS.
# Copyright (C) 2015 OpenIO, original work as part of OpenIO Software Defined Storage
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from string import Template
import os, errno

template_flask_gridinit = """
[service.${NS}-flask]
group=${NS},localhost,flask
on_die=respawn
enabled=true
start_at_boot=true
command=/usr/bin/gunicorn --preload -w 2 -b ${IP}:${PORT} oio.sds.admin-flask:app
env.PATH=${PATH}
env.LD_LIBRARY_PATH=${HOME}/.local/lib:${LIBDIR}
"""

template_nginx_gridinit = """

[service.${NS}-endpoint]
group=${NS},localhost,endpoint
on_die=respawn
enabled=true
start_at_boot=true
command=/usr/sbin/nginx -p ${CFGDIR} -c ${NS}-endpoint.conf
env.PATH=${PATH}
env.LD_LIBRARY_PATH=${HOME}/.local/lib:${LIBDIR}
"""

template_nginx_endpoint = """
working_directory ${TMPDIR};
error_log ${LOGDIR}/endpoint.log debug;
worker_processes 1;
pid ${RUNDIR}/endpoint.pid;
daemon off;

events {
}

http {
	default_type application/octet-stream;

	client_body_temp_path ${TMPDIR} 1;
	proxy_temp_path       ${TMPDIR} 1;
	fastcgi_temp_path     ${TMPDIR} 1;
	uwsgi_temp_path       ${TMPDIR} 1;
	scgi_temp_path        ${TMPDIR} 1;

	access_log ${LOGDIR}/endpoint.access;

	server {
		listen *:${PORT};
		listen [::]:${PORT};
		server_name "";
		location /v1.0/admin {
			proxy_pass         http://127.0.0.1:${FLASK}/v1.0/admin;
			proxy_redirect     off;

			proxy_set_header   Host             $host;
			proxy_set_header   X-Real-IP        $remote_addr;
			proxy_set_header   X-Forwarded-For  $proxy_add_x_forwarded_for;
		}
		location /v1.0 {
			proxy_pass         http://127.0.0.1:${PROXY}/v1.0;
			proxy_redirect     off;

			proxy_set_header   Host             $host;
			proxy_set_header   X-Real-IP        $remote_addr;
			proxy_set_header   X-Forwarded-For  $proxy_add_x_forwarded_for;
		}
	}
}
"""

template_rawx_service = """
LoadModule mpm_worker_module   modules/mod_mpm_worker.so
LoadModule authz_core_module   modules/mod_authz_core.so
LoadModule unixd_module        modules/mod_unixd.so
LoadModule dav_module          modules/mod_dav.so
LoadModule log_config_module   modules/mod_log_config.so
LoadModule mime_module         modules/mod_mime.so
LoadModule dav_rawx_module     @APACHE2_MODULES_DIRS@/mod_dav_rawx.so

Listen ${IP}:${PORT}
PidFile ${RUNDIR}/${NS}-${SRVTYPE}-httpd-${SRVNUM}.pid
ServerRoot ${TMPDIR}
ServerName localhost
ServerSignature Off
ServerTokens Prod
DocumentRoot ${RUNDIR}
TypesConfig /etc/mime.types

User  ${USER}
Group ${USER}

LogFormat "%h %l %t \\"%r\\" %>s %b %D" log/common
ErrorLog ${SDSDIR}/logs/${NS}-${SRVTYPE}-httpd-${SRVNUM}-errors.log
CustomLog ${SDSDIR}/logs/${NS}-${SRVTYPE}-httpd-${SRVNUM}-access.log log/common
LogLevel info

<IfModule mod_env.c>
SetEnv nokeepalive 1
SetEnv downgrade-1.0 1
SetEnv force-response-1.0 1
</IfModule>

<IfModule prefork.c>
MaxClients 10
StartServers 5
MinSpareServers 5
MaxSpareServers 10
</IfModule>

<IfModule worker.c>
StartServers 1
MaxClients 10
MinSpareThreads 2
MaxSpareThreads 10
ThreadsPerChild 10
MaxRequestsPerChild 0
</IfModule>

DavDepthInfinity Off

grid_hash_width 2
grid_hash_depth 1
grid_docroot ${DATADIR}/${NS}-${SRVTYPE}-${SRVNUM}
grid_namespace NS
grid_dir_run ${RUNDIR}
#grid_upload_blocksize 65536
#grid_upload_fileflags DIRECT|SYNC|NOATIME

<Directory />
DAV rawx
AllowOverride None
Require all granted
</Directory>

<VirtualHost ${IP}:${PORT}>
# DO NOT REMOVE (even if empty) !
</VirtualHost>
"""

template_agent = """
[General]
user=${UID}
group=${GID}

service_check_freq=1
cluster_update_freq=1

period_get_ns=1
period_get_srv=1
period_get_srvtype=1
#period_get_evtconfig=30
period_push_srv=1

#enable_broken_elements=false
#period_broken_push=30
#period_broken_get=30

events.spool.dir=${SPOOLDIR}/${NS}-spool
events.spool.size=9999
events.mode.dir=755
events.mode.file=644
events.manage.enable=yes
events.receive.enable=yes

events.max_pushes_per_round=10
events.max_status_per_round=20
events.max_incoming_per_round=50

[server.inet]
port=${PORT}

[server.unix]
mode=0600
uid=${UID}
gid=${GID}
path=${RUNDIR}/agent.sock
"""

template_conscience = """
[General]
### Now is 'daemon' ignored (this is managed at the CLI)
### Now is 'pidfile' ingnored (managed at CLI too)
# Timeout on read operations
to_op=1000
# Timeout on accepting connections
to_cnx=1000

flag.NOLINGER=true
flag.SHUTDOWN=false
flag.KEEPALIVE=false
flag.QUICKACK=false

[Server.conscience]
min_workers=2
min_spare_workers=2
max_spare_workers=10
max_workers=10
listen=${IP}:${PORT}
plugins=conscience,stats,fallback

[Service]
namespace=${NS}
type=conscience
register=false
load_ns_info=false

[Plugin.stats]
path=${LIBDIR}/grid/msg_stats.so

[Plugin.fallback]
path=${LIBDIR}/grid/msg_fallback.so

[Plugin.conscience]
path=${LIBDIR}/grid/msg_conscience.so
param_namespace=${NS}
param_chunk_size=10485760
param_score_timeout=86400

param_option.ns_status=MASTER
param_option.WORM=false
param_option.service_update_policy=meta2=NONE|${M2_REPLICAS}|1|tag.type=m2v2;meta1=REPLACE;sqlx=KEEP|1|1|
param_option.automatic_open=true
param_option.meta2_max_versions=${VERSIONING}
param_option.storage_policy=${STGPOL}

param_option.meta2_check.put.GAPS=false
param_option.meta2_check.put.DISTANCE=false
param_option.meta2_check.put.STGCLASS=false
param_option.meta2_check.put.SRVINFO=false

param_storage_conf=${CFGDIR}/${NS}-conscience-policies.conf

param_events=${CFGDIR}/${NS}-conscience-events.conf

param_service.default.score_timeout=30
param_service.default.score_variation_bound=5
param_service.default.score_expr=100

param_service.meta0.score_timeout=3600
param_service.meta0.score_variation_bound=5
param_service.meta0.score_expr=(num stat.cpu)

param_service.meta1.score_timeout=120
param_service.meta1.score_variation_bound=5
param_service.meta1.score_expr=(num stat.cpu)

param_service.meta2.score_timeout=120
param_service.meta2.score_variation_bound=5
param_service.meta2.score_expr=(num stat.cpu)

param_service.rawx.score_timeout=120
param_service.rawx.score_variation_bound=5
param_service.rawx.score_expr=(num stat.cpu)

param_service.sqlx.score_timeout=120
param_service.sqlx.score_variation_bound=5
param_service.sqlx.score_expr=(num stat.cpu)

param_service.echo.score_timeout=120
param_service.echo.score_variation_bound=5
param_service.echo.score_expr=(num stat.cpu)
"""

template_conscience_events = """
*=drop
"""

template_conscience_policies = """
[STORAGE_POLICY]
SINGLE=NONE:NONE:NONE
TWOCOPIES=NONE:DUPONETWO:NONE
FIVECOPIES=NONE:DUPONEFIVE:NONE
RAIN=NONE:RAIN:NONE

[STORAGE_CLASS]
# <CLASS> = FALLBACK[,FALLBACK]...
SUPERFAST=PRETTYGOOD,REASONABLYSLOW,NONE
PRETTYGOOD=REASONABLYSLOW,NONE
REASONABLYSLOW=NONE

[DATA_SECURITY]
DUPONETWO=DUP:distance=1|nb_copy=2
DUPONEFIVE=DUP:distance=1|nb_copy=5
RAIN=RAIN:k=6|m=2|algo=liber8tion

[DATA_TREATMENTS]
"""

template_gridinit_header = """
[Default]
listen=${RUNDIR}/gridinit.sock
pidfile=${RUNDIR}/gridinit.pid
uid=${UID}
gid=${GID}
working_dir=${TMPDIR}
env.PATH=${PATH}
env.LD_LIBRARY_PATH=${HOME}/.local/lib:${LIBDIR}

limit.core_size=-1
limit.max_files=2048
limit.stack_size=256

#include=${CFGDIR}/*-gridinit.conf

[service.gridagent]
group=common,localhost,agent
on_die=respawn
enabled=true
start_at_boot=true
command=${EXE_PREFIX}-cluster-agent -s SDS,${NS},agent ${CFGDIR}/agent.conf
env.PATH=${HOME}/.local/bin:${CODEDIR}/bin
env.LD_LIBRARY_PATH=${HOME}/.local/lib:${LIBDIR}

"""

template_gridinit_ns = """
[service.${NS}-gridevents]
group=${NS},localhost,events
on_die=respawn
enabled=false
start_at_boot=false
command=${EXE_PREFIX}-cluster-agent -s SDS,${NS},events--child-evt=${NS} ${CFGDIR}/agent.conf
env.PATH=${PATH}
env.LD_LIBRARY_PATH=${HOME}/.local/lib:${LIBDIR}

[service.${NS}-conscience]
group=${NS},localhost,conscience
on_die=respawn
enabled=true
start_at_boot=true
#command=${EXE_PREFIX}-daemon -s SDS,${NS},conscience ${CFGDIR}/${NS}-conscience.conf
command=${EXE_PREFIX}-daemon -q ${CFGDIR}/${NS}-conscience.conf
env.PATH=${HOME}/.local/bin:${CODEDIR}/bin
env.LD_LIBRARY_PATH=${HOME}/.local/lib:${LIBDIR}

[service.${NS}-proxy]
group=${NS},localhost,proxy
on_die=respawn
enabled=true
start_at_boot=false
command=${EXE_PREFIX}-proxy -s SDS,${NS},proxy ${IP}:${PORT} ${NS}
env.PATH=${HOME}/.local/bin:${CODEDIR}/bin
env.LD_LIBRARY_PATH=${HOME}/.local/lib:${LIBDIR}
"""

template_gridinit_service = """
[service.${NS}-${SRVTYPE}-${SRVNUM}]
group=${NS},localhost,${SRVTYPE}
on_die=respawn
enabled=true
start_at_boot=false
command=${EXE} -s SDS,${NS},${SRVTYPE},${SRVNUM} -O Endpoint=${IP}:${PORT} ${NS} ${DATADIR}/${NS}-${SRVTYPE}-${SRVNUM}
env.PATH=${PATH}
env.LD_LIBRARY_PATH=${HOME}/.local/lib:${LIBDIR}
"""

template_gridinit_rawx = """
[Service.${NS}-${SRVTYPE}-${SRVNUM}]
group=${NS},localhost,${SRVTYPE}
command=${EXE_PREFIX}-svc-monitor -s SDS,${NS},${SRVTYPE},${SRVNUM} -p 1 -m '${EXE_PREFIX}-rawx-monitor.py' -i '${NS}|${SRVTYPE}|${IP}:${PORT}' -c '/usr/sbin/httpd -D FOREGROUND -f ${CFGDIR}/${NS}-${SRVTYPE}-httpd-${SRVNUM}.conf'
enabled=true
start_at_boot=false
on_die=respawn
env.PATH=${PATH}
env.LD_LIBRARY_PATH=${HOME}/.local/lib:${LIBDIR}
"""

template_local_header = """
[default]
agent=${RUNDIR}/agent.sock
"""

template_local_ns = """
[${NS}]
zookeeper=${IP}:2181
conscience=${IP}:${PORT_CS}
endpoint=${IP}:${PORT_ENDPOINT}
"""

HOME = str(os.environ['HOME'])
EXE_PREFIX = "@EXE_PREFIX@"
OIODIR = HOME + '/.oio'
SDSDIR = OIODIR + '/sds'
CFGDIR = SDSDIR + '/conf'
RUNDIR = SDSDIR + '/run'
LOGDIR = SDSDIR + '/logs'
SPOOLDIR = SDSDIR + '/spool'
DATADIR = SDSDIR + '/data'
TMPDIR = '/tmp'
CODEDIR = '@CMAKE_INSTALL_PREFIX@'
LIBDIR = CODEDIR + '/@LD_LIBDIR@'
PATH = HOME+"/.local/bin:@CMAKE_INSTALL_PREFIX@/bin"
port = 6000

def mkdir_noerror (d):
	try:
		os.makedirs (d, 0700)
	except OSError as e:
		if e.errno != errno.EEXIST:
			raise e

def type2exe (t):
	return EXE_PREFIX + '-' + str(t) + '-server'

def next_port ():
	global port
	res, port = port, port + 1
	return res

def generate (ns, ip, options={}):
	port_cs = next_port()
	port_agent = next_port() # for TCP connection is use by Java applications
	port_proxy = next_port()
	port_flask = next_port()
	port_endpoint = next_port()
	services = (
			('meta0', EXE_PREFIX + '-meta0-server', 1, next_port()),

			('meta1', EXE_PREFIX + '-meta1-server', 1, next_port()),
			('meta1', EXE_PREFIX + '-meta1-server', 2, next_port()),
			('meta1', EXE_PREFIX + '-meta1-server', 3, next_port()),

			('meta2', EXE_PREFIX + '-meta2-server', 1, next_port()),
			('meta2', EXE_PREFIX + '-meta2-server', 2, next_port()),
			('meta2', EXE_PREFIX + '-meta2-server', 3, next_port()),

			('sqlx',  EXE_PREFIX + '-sqlx-server', 1, next_port()),
			('sqlx',  EXE_PREFIX + '-sqlx-server', 2, next_port()),
			('sqlx',  EXE_PREFIX + '-sqlx-server', 3, next_port()),
	)
	rawx = (
		(1, next_port()),
		(2, next_port()),
		(3, next_port()),
		(4, next_port()),
	)

	versioning = 1
	stgpol = "SINGLE"
	replicas = 3

	if options.M2_REPLICAS is not None:
		versioning = int(options.M2_REPLICAS)
	if options.M2_VERSIONS is not None:
		versioning = int(options.M2_VERSIONS)
	if options.M2_STGPOL is not None:
		stgpol = str(options.M2_STGPOL)

	env = dict(IP=ip, NS=ns, HOME=HOME, EXE_PREFIX=EXE_PREFIX,
			PATH=PATH, LIBDIR=LIBDIR,
			SDSDIR=SDSDIR, TMPDIR=TMPDIR,
			DATADIR=DATADIR, CFGDIR=CFGDIR, RUNDIR=RUNDIR, SPOOLDIR=SPOOLDIR,
			LOGDIR=LOGDIR, CODEDIR=CODEDIR,
			UID=str(os.geteuid()), GID=str(os.getgid()), USER=str(os.getlogin()),
			VERSIONING=versioning, STGPOL=stgpol, REPLICAS=replicas)

	mkdir_noerror(SDSDIR)
	mkdir_noerror(CODEDIR)
	mkdir_noerror(DATADIR)
	mkdir_noerror(CFGDIR)
	mkdir_noerror(RUNDIR)
	mkdir_noerror(LOGDIR)

	# Global SDS configuration
	with open(OIODIR + '/'+ 'sds.conf', 'w+') as f:
		tpl = Template(template_local_header)
		f.write(tpl.safe_substitute(env))
		env['PORT_CS'] = port_cs
		env['PORT_ENDPOINT'] = port_endpoint
		tpl = Template(template_local_ns)
		f.write(tpl.safe_substitute(env))

	# Conscience configuration
	with open(CFGDIR + '/'+ns+'-conscience.conf', 'w+') as f:
		env['PORT'] = port_cs
		tpl = Template(template_conscience)
		f.write(tpl.safe_substitute(env))
	with open(CFGDIR + '/' + ns + '-conscience-events.conf', 'w+') as f:
		tpl = Template(template_conscience_events)
		f.write(tpl.safe_substitute(env))
	with open(CFGDIR + '/' + ns + '-conscience-policies.conf', 'w+') as f:
		tpl = Template(template_conscience_policies)
		f.write(tpl.safe_substitute(env))

	# Generate the "GRIDD-like" services
	with open(CFGDIR + '/' + 'gridinit.conf', 'a+') as f:
		tpl = Template(template_gridinit_header)
		f.write(tpl.safe_substitute(env))
	with open(CFGDIR + '/' + 'gridinit.conf', 'a+') as f:
		env['PORT'] = port_proxy
		tpl = Template(template_gridinit_ns)
		f.write(tpl.safe_substitute(env))
		tpl = Template(template_gridinit_service)
		for t, e, n, p in services:
			mkdir_noerror(DATADIR + '/' + ns + '-' + t + '-' + str(n))
			env['SRVTYPE'] = t
			env['SRVNUM'] = n
			env['PORT'] = p
			env['EXE'] = e
			f.write(tpl.safe_substitute(env))

	# Generate the RAWX services
	tpl = Template(template_gridinit_rawx)
	with open(CFGDIR + '/' + 'gridinit.conf', 'a+') as f:
		for n,p in rawx:
			mkdir_noerror(DATADIR + '/' + ns + '-rawx-' + str(n))
			env['SRVTYPE'] = 'rawx'
			env['SRVNUM'] = n
			env['PORT'] = p
			f.write(tpl.safe_substitute(env))
	tpl = Template(template_rawx_service)
	for n,p in rawx:
		env['SRVTYPE'] = 'rawx'
		env['SRVNUM'] = n
		env['PORT'] = p
		with open(CFGDIR + '/' + ns + '-rawx-httpd-' + str(n) + '.conf', 'w+') as f:
			f.write(tpl.safe_substitute(env))

	# Central endpoint service
	env['PORT'] = port_endpoint
	env['FLASK'] = port_flask
	env['PROXY'] = port_proxy
	with open(CFGDIR + '/' + ns + '-endpoint.conf', 'w+') as f:
		tpl = Template(template_nginx_endpoint)
		f.write(tpl.safe_substitute(env))
	with open(CFGDIR + '/' + 'gridinit.conf', 'a+') as f:
		tpl = Template(template_nginx_gridinit)
		f.write(tpl.safe_substitute(env))

	# Central administration flask
	env['PORT'] = port_flask
	with open(CFGDIR + '/' + 'gridinit.conf', 'a+') as f:
		tpl = Template(template_flask_gridinit)
		f.write(tpl.safe_substitute(env))

	# Central agent configuration
	env['PORT'] = port_agent
	with open(CFGDIR + '/'+ 'agent.conf', 'w+') as f:
		tpl = Template(template_agent)
		f.write(tpl.safe_substitute(env))

def main ():
	from optparse import OptionParser as OptionParser
	parser = OptionParser()
	parser.add_option("-B", "--bucket-replicas",
			action="store", type="int", dest="M2_REPLICAS",
			help="Number of containers replicas")
	parser.add_option("-V", "--versioning",
			action="store", type="int", dest="M2_VERSIONS",
			help="Number of contents versions")
	parser.add_option("-S", "--stgpol",
			action="store", type="string", dest="M2_STGPOL",
			help="How many replicas for META2")
	options, args = parser.parse_args()
	generate(args[0], args[1], options)

if __name__ == '__main__':
	main()

