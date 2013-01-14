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