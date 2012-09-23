# Installation

This is a rough setup guide at the moment. It should be encoded into Chef recipes
at some stage.

## Target

All these steps currently use Ubuntu 12.04.

## Tools

	sudo apt-get install git-core
	sudo apt-get install build-essential

## Redis

	sudo apt-get install redis-server

## Rabbitmq

	sudo apt-get install rabbitmq-server

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

Ubuntu 12.04 comes with Python 2.7 by default. However, you will need to install pip packages.
At this time, I'm not currently using virtualenv or equivalents; however this should
be easily possible.

	sudo apt-get install python-pip
	sudo apt-get install python-dev
	sudo pip install -r requirements.txt
    sudo pip instal coverage
