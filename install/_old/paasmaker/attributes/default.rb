
default['paasmaker']['run_user'] = "ubuntu"
default['paasmaker']['run_group'] = "ubuntu"

default['paasmaker']['pacemaker']['enabled'] = true

default['paasmaker']['heart']['enabled'] = true
default['paasmaker']['heart']['runtimes'] = {
	'php' => {
		'enabled' => true
	},
	'shell' => {
		'enabled' => true
	}
}

default['paasmaker']['router']['enabled'] = true
default['paasmaker']['router']['system'] = true