# Installation

This is a rough setup guide at the moment. It should be encoded into Chef recipes
at some stage.

## Target

All these steps currently use Ubuntu 12.04.

## Redis

sudo apt-get install redis-server

## Rabbitmq

sudo apt-get install rabbitmq-server

## OpenResty

* Download from http://openresty.org/
* Currently used version 1.2.3.1.
* Unpack.
* ./configure
* (Install any missing deps like build-essential)
* make
* make install

## Python

The target version is 2.7.

Ubuntu 12.04 comes with Python 2.7 by default. However, you will need to install pip packages.
At this time, I'm not currently using virtualenv or equivalents; however this should
be easily possible.

sudo apt-get install python-pip
sudo pip install -r requirements.txt