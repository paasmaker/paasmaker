# PaasMaker

An open source, extensible, highly visible platform-as-a-service.

## Installation

The system is intended to be installed as easily as possible. It is also designed
to be easily installed from binary packages where possible on Ubuntu 12.04. This
wasn't possible with nginx unfortunately, but OpenResty includes all the relevant
patches meaning that the installation of that is as simple as ./configure, make,
make install.

You will need, for the core:

* Redis (packages)
* Python (targetting 2.7) (packages + pip)
* RabbitMQ (packages)
* OpenResty (a version of nginx with patches - http://openresty.org/ - from source)

You will need a combination of the following depending on the runtimes you're working
with:

* Apache2 (packages)
* PHP (packages)

## Database Migrations

Database migrations are handled with Alembic. To create a migration, make your changes
to the models, and then run the following command:

	# alembic revision --autogenerate -m "Description of your change here"

You should then adjust the generated file as required. To apply pending migrations, use
this command:

	# alembic upgrade head

Once you've applied your migration successfully, you can check in the new migrations version
file.

## Redirecting port 80 to 42530

By default, Paasmaker runs entirely as a non-privileged user. Normally, to listen on port 80,
nginx would need to be started as root.

One way to work around this is to have iptables forward port 80 to 42531, which makes
installation and configuration of Paasmaker simpler.

The managed NGINX listens on port 42530 and port 42531. The difference between the two is the
HTTP headers forwarded to the instance. On port 42530, NGINX passes along an X-Fowarded-Port header
with 42530. On port 42531, NGINX passes along an X-Fowarded-Port header at port 80.

To do that, issue these iptables commands:

	sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 42531
	sudo iptables -t nat -I OUTPUT -p tcp -d 127.0.0.0/8 --dport 80 -j REDIRECT --to-ports 42531

If you're not running Paasmaker in production, just use port 42530 for testing, and it will
all work fine.