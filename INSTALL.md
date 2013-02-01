# Installation

This is a rough setup guide at the moment. It should be encoded into Chef recipes
at some stage.

## Target

All these steps currently use Ubuntu 12.04.

## Tools - development

	sudo apt-get install git-core
	sudo apt-get install build-essential

## Tools - runtime generic

	sudo apt-get install curl
	sudo apt-get install zip

### PHP runtime

This will pull in Apache with the correct worker type. This list will need to be
updated with more modules for PHP.

	sudo apt-get install libapache2-mod-php5 php5-cli

### Ruby Runtime

Optional for now. This is from and based on rbenv: https://github.com/sstephenson/rbenv

	sudo apt-get install zlib1g-dev libssl-dev libreadline-dev
	git clone git://github.com/sstephenson/rbenv.git ~/.rbenv
	git clone git://github.com/sstephenson/ruby-build.git ~/.rbenv/plugins/ruby-build
	echo 'export PATH="$HOME/.rbenv/bin:$PATH"' >> ~/.profile
	echo 'eval "$(rbenv init -)"' >> ~/.profile
	exec $SHELL -l
	rbenv install 1.9.3-p327
	rbenv rehash
	gem install bundler
	rbenv rehash

## Redis

	sudo apt-get install redis-server

## Rabbitmq

	(Optional for now.)
	sudo apt-get install rabbitmq-server

## Postgres

For the postgres service, you will need libpq-dev.
(Not optional because momoko is in requirements.txt)

	sudo apt-get install libpq-dev

## OpenResty

* `sudo apt-get install libreadline-dev libncurses5-dev libpcre3-dev libssl-dev perl`
* Download from http://openresty.org/
* Currently used version 1.2.3.1.
* Unpack.
* `./configure --with-luajit`
* `make`
* `sudo make install`

## Python

The target version is 2.7.

Ubuntu 12.04 comes with Python 2.7 by default. The installer will set up a virtual environment
for you and invoke it when starting the server. So the instructions below should not be used.

	sudo apt-get install python-pip
	sudo apt-get install python-dev
	sudo pip install -r requirements.txt
    sudo pip install coverage

## Chef

Optional for now. To install Chef, use the Opscode repository:

http://wiki.opscode.com/display/chef/Installing+Chef+Client+on+Ubuntu+or+Debian

This is intended to be a chef-solo setup. Depending on your environment,
you might not need chef-solo at all.