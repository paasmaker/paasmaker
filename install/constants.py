
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
				'php5-pgsql'
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
	'configure_command': './configure --with-luajit --prefix=`pwd`',
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
	'runtime_php_extra_packages': [],
	'runtime_php_disable_system_apache': False,

	'runtime_rbenv_enable': False,
	'runtime_rbenv_for_user': True,
	'runtime_rbenv_versions': ['1.9.3-p327'],

	'service_managedmysql_enable': True,
	'service_managedmysql_disable_system_mysql': False,

	'service_managedpostgres_enable': True,
	'service_managedmysql_disable_system_postgres': False,

	'service_managedredis_enable': True,

	'extra_plugins': [],

	'write_paasmaker_configuration': True
}

DEFAULT_PAASMAKER_CONFIGURATION = {
	'heart': {
		'enabled': False
	},
	'pacemaker': {
		'enabled': False,
		'cluster_hostname': '',
		'dsn': 'sqlite:///scratch/paasmaker.db'
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