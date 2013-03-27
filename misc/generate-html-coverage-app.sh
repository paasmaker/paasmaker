# Paasmaker: generate-html-coverage-app.sh
#
# Generates an app displaying test coverage results
# that can be deployed on Paasmaker.
# - run all unit tests in coverage-gathering mode
# - generate HTML output
# - output a zip file that can be deployed as a Paasmaker app
#
# First (and only) argument should be the source directory for
# the git clone of Paasmaker. If not provided, we assume it's
# in the current user's home directory.
#
# Dumps a zip file into the current working directory.
#
# 2013-02-01

if [ "$1" ]
then
	"$1"/testsuite.py -c all
else
	~/paasmaker/testsuite.py -c all
fi

coverage html

echo "manifest:
  format: 1

application:
  name: coverage.paasmaker.org

instances:
  - name: web
    quantity: 1
    runtime:
      plugin: paasmaker.runtime.static
      parameters:
        document_root: htmlcov/
      version: 1
    placement:
      plugin: paasmaker.placement.default
    hostnames:
      - coverage.paasmaker.org" > manifest.yml

rm -f paasmaker-test-coverage.zip
zip -qr paasmaker-test-coverage.zip manifest.yml htmlcov/

coverage erase
rm -rf manifest.yml
rm -rf htmlcov/
