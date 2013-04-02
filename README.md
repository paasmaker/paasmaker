# Paasmaker

Paasmaker is an open source, extensible, highly visible tool for building a
[platform as a service](http://docs.paasmaker.org/introduction.html) (PaaS)
and deploying to it.

## Installation

We've tried to make it as easy as possible to get started. Paasmaker ships with
an installation script that will do most of the heavy lifting for you. On
Ubuntu 12.04 and greater, you should just be able to clone the repo, and run:

	$ ./install.py install/configs/example-paasmaker-hacking.yml

We also support installing a development version on Mac OS X (10.7 or 10.8).
On OS X you have to install [Homebrew](http://mxcl.github.com/homebrew/) and
[pip](http://www.pip-installer.org/) first.

For full details, [check out the documentation](http://docs.paasmaker.org/installation.html).

## Running

Once the install script has completed (which can take 20 minutes), run:

	$ ./pm-server.py --debug=1

and visit [localhost:42500](http://localhost:42500) in your web browser. In the
default configuration, you can log in with username and password "paasmaker" to
start experimenting.

To get you going, we have simple example applications written in
[Python](https://bitbucket.org/paasmaker/sample-python-simple),
[PHP](https://bitbucket.org/paasmaker/sample-php-simple),
and [node.js](https://bitbucket.org/paasmaker/sample-node-simple).
There's also a [Ruby](https://bitbucket.org/paasmaker/sample-ruby-simple)
example that requires the
[rbenv](http://docs.paasmaker.org/plugin-runtime-rbenv.html) runtime.

## More information

The Paasmaker website is the starting point for information about Paasmaker:
[www.paasmaker.org](http://paasmaker.org)
