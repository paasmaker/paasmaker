#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

# Define constants. Why? Because if we spell these wrong
# in the code, Python will tell us. If we spell it wrong
# inside the string, the code just won't work the way we
# expect.

# MAJOR PLATFORM NAMES
WINDOWS = 'Windows'
DARWIN = 'Darwin'
LINUX = 'Linux'

# MINOR PLATFORM NAMES
UBUNTU = 'Ubuntu'
GENERIC = 'Generic'

# SYSTEM PACKAGE LISTS
SYSTEM_PACKAGES = {
	LINUX: {
		UBUNTU: {
			'core': [
				# Real core.
				'git-core',
				'build-essential',
				'curl',
				'zip',
				'python-pip',
				'python-dev',
				'file',

				# For the MySQL python module.
				'libmysqlclient-dev',

				# Python Postgres module. TODO: Make optional.
				'libpq-dev',

				# Nginx.
				'libreadline-dev',
				'libncurses5-dev',
				'libpcre3-dev',
				'libssl-dev',
				'perl'
			],
			'runtime-php': [
				'libapache2-mod-php5',
				'php5-cli',
				'php5-mysql',
				'php5-pgsql',
				'php5-mcrypt'
			],
			'runtime-rbenv': [
				'zlib1g-dev',
				'libssl-dev',
				'libreadline-dev'
			],
			'service-mysql': [
				'mysql-server'
			],
			'service-postgres': [
				'postgresql'
			],
			'service-mongodb': [
				'mongodb'
			]
		}
	},
	DARWIN: {
		GENERIC: {
			'core': [
				# Real core.
				'wget',
				'md5sha1sum',

				# TODO: In homebrew, in theory we should be able to just
				# install the mysql-connector-c to allow the Python library
				# to link. However, mysql and mysql-connector-c conflict
				# in homebrew, so we just install mysql (which comes with
				# the connecting libraries) although this takes more time
				# and disk space.
				'mysql',

				# Nginx.
				'pcre',
				'openssl',
			],
			'runtime-php': [
				# Already ships with OSX.
			],
			'runtime-rbenv': [
				# Handled in another way for OSX.
			],
			'service-mysql': [
				'mysql'
			],
			'service-postgres': [
				'postgresql'
			],
			'service-mongodb': [
				'mongodb'
			]
		}
	}
}

# FROM SOURCE PACKAGE METADATA
OPENRESTY = {
	'working_name': 'ngx_openresty-1.2.6.1.tar.gz',
	'url': "http://agentzh.org/misc/nginx/ngx_openresty-1.2.6.1.tar.gz",
	'unpacked_name': 'ngx_openresty-1.2.6.1',
	'sha1': '6e25cf573faf58deb233f04dafde35c612cadcc7',
	'binary': 'ngx_openresty-1.2.6.1/nginx/sbin/nginx',
	'configure_command': './configure --with-luajit --prefix=`pwd` --with-ipv6',
	'darwin_generic_configure_command': './configure --with-ipv6 --with-luajit --prefix=`pwd`  --with-cc-opt="-I%(homebrew_pcre_path)s/include" --with-ld-opt="-L%(homebrew_pcre_path)s/lib"',
	'make_command': 'make -j 16',
	'install_command': 'make install' # NOTE: No sudo here - we're installing to the build location.
}
REDIS = {
	'working_name': 'redis-2.6.9',
	'url': "http://redis.googlecode.com/files/redis-2.6.9.tar.gz",
	'sha1': "519fc3d1e7a477217f1ace73252be622e0101001",
	'binary': 'redis-2.6.9/src/redis-server',
	'unpacked_name': 'redis-2.6.9',
	'make_command': 'make -j 16'
}

# DEFAULT CONFIGURATION FOR THE INSTALLER
DEFAULT_INSTALLER_CONFIGURATION = {
	'is_heart': True,
	'is_router': True,
	'is_pacemaker': True,

	'cluster_hostname': 'local.paasmaker.net',
	'frontend_domain_postfix': ':42530',
	'cluster_name': None,

	'redis_mode': 'completely-managed', # or 'defer-to-master'. If node is a router and defer-to-master is set, will create a managed slave.

	'master_node': 'localhost',
	'master_port': 42500,
	'my_name': None,
	'my_route': None,
	'node_token': None,
	'super_token': None,

	'shutdown_daemons_on_exit': False,

	'install_init_script': True,
	'enable_init_script': False,
	'init_redirect_port80': False,

	'use_system_openresty': False,
	'openresty_binary': 'thirdparty/ngx_openresty-1.2.6.1/nginx/sbin/nginx',

	'use_system_redis': False,
	'redis_binary': 'thirdparty/redis-2.6.9/src/redis-server',

	'runtime_shell_enable': True,

	'runtime_php_enable': False,
	'runtime_php_apache_modules': ['rewrite'],
	'runtime_php_extra_packages': [],
	'runtime_php_disable_system_apache': False,

	'runtime_rbenv_enable': False,
	'runtime_rbenv_for_user': True,
	'runtime_rbenv_versions': ['1.9.3-p327'],

	'runtime_nvm_enable': False,
	'runtime_nvm_for_user': True,
	'runtime_nvm_versions': ['v0.8.22'],

	'service_managedmysql_enable': False,
	'service_managedmysql_disable_system_mysql': False,

	'service_managedpostgres_enable': False,
	'service_managedmysql_disable_system_postgres': False,

	'service_managedredis_enable': False,

	'service_managedmongodb_enable': False,
	'service_managedmongodb_disable_system_mongodb': False,

	'extra_plugins': [],

	'write_paasmaker_configuration': True
}

DEFAULT_PAASMAKER_CONFIGURATION = {
	'heart': {
		'enabled': False
	},
	'pacemaker': {
		'enabled': False,
		'dsn': 'sqlite:///scratch/paasmaker.db',
		'cluster_hostname': 'not-applicable',
		'super_token': 'not-applicable'
	},
	'router': {
		'enabled': False,
		'nginx': {
			'managed': True
		},
		'stats_log': 'managed'
	},
	'plugins': [],
	'master': {}
}

DEFAULT_PAASMAKER_MANAGED_REDIS = {
	'table': {
		'host': '0.0.0.0',
		'port': 42510,
		'managed': True
	},
	'stats': {
		'host': '0.0.0.0',
		'port': 42512,
		'managed': True
	},
	'jobs': {
		'host': '0.0.0.0',
		'port': 42513,
		'managed': True
	}
}

INIT_SCRIPT = """\
#!/bin/bash

### BEGIN INIT INFO
# Provides:	paasmaker
# Required-Start:	$all
# Required-Stop:	$all
# Default-Start:	2 3 4 5
# Default-Stop:
# Short-Description:	Paasmaker Platform as a Service
### END INIT INFO

# Init script for Paasmaker.
# NOTE: This script is generated by the installation script,
# and will be overwritten next time you run the installation script.

# Configuration for this script.
PAASMAKER_HOME="%(paasmaker_home)s"
ENABLE_IPTABLES="%(enable_iptables)s"
PID_FILE="%(paasmaker_home)s/paasmaker.pid"
PAASMAKER_USER="%(paasmaker_user)s"
LOG_PATH="/var/log/paasmaker.log"

# Body of the script.
ACTION="$1"

if [ "$ACTION" == "" ];
then
	echo "Usage: $0 start|stop|restart|status"
	exit 0
fi

function fix_iptables() {
	if [ "$ENABLE_IPTABLES" == "True" ];
	then
		echo "Inserting iptables rules..."

		iptables -t nat -C PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 42531
		if [ "$?" == "1" ];
		then
			iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 42531
		fi

		iptables -t nat -C OUTPUT -p tcp -d 127.0.0.0/8 --dport 80 -j REDIRECT --to-ports 42531
		if [ "$?" == "1" ];
		then
			iptables -t nat -I OUTPUT -p tcp -d 127.0.0.0/8 --dport 80 -j REDIRECT --to-ports 42531
		fi

		echo "iptables rules are up to date."
	fi
}

function start() {
	# This will fork into the background once it's ready,
	# or fail otherwise.
	echo "Starting up..."
	su -l "$PAASMAKER_USER" -c "cd $PAASMAKER_HOME; ./pm-server.py; exit \$?" > "$LOG_PATH" 2>&1

	CODE=$?
	if [ "$CODE" == "0" ];
	then
		fix_iptables

		echo "Forked into background successfully."
		echo "Check the log file at $LOG_PATH to make sure it registered fully."
	else
		echo "Failed to start up!"
		echo "Check $LOG_PATH to find out why."
		exit 1
	fi
}

function status() {
	if [ ! -e "$PID_FILE" ];
	then
		echo "Paasmaker doesn't seem to be running."
	else
		PID=`cat $PID_FILE`
		PIDCHECKPATH="/proc/$PID/cmdline"
		if [ ! -e "$PIDCHECKPATH" ];
		then
			echo "Paasmaker has a PID file but is not running."
		else
			echo "Paasmaker is running."
		fi
	fi
}

function stop() {
	if [ ! -e "$PID_FILE" ];
	then
		echo "Paasmaker not running - no PID file found at $PID_FILE."
	else
		PID=`cat $PID_FILE`
		echo "Sending kill signal..."
		kill $PID
		echo "Waiting for shutdown..."
		while [ 1 ];
		do
			if [ ! -e "$PID_FILE" ];
			then
				# It's shut down.
				break
			fi
			echo "Waiting longer..."
			sleep 1
		done
		echo "Stopped."
	fi
}

function restart() {
	stop
	start
}

if [ "$ACTION" == "start" ];
then
	start
fi

if [ "$ACTION" == "stop" ];
then
	stop
fi

if [ "$ACTION" == "restart" ];
then
	restart
fi

if [ "$ACTION" == "status" ];
then
	status
fi

"""
