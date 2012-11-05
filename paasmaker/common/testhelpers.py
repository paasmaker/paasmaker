
import time

class TestHelpers(object):
	# A collection of functions that can be mixed into unit tests
	# to provide useful things for tests. Most assume that you're an
	# AsyncTestCase or subclass.

	def short_wait_hack(self, length=0.1):
		self.io_loop.add_timeout(time.time() + length, self.stop)
		self.wait()

	def pack_sample_application(self, application):
		# Pack up the tornado simple test application.
		temptarball = os.path.join(self.configuration.get_flat('scratch_directory'), 'testapplication.tar.gz')
		command_log = os.path.join(self.configuration.get_flat('scratch_directory'), 'testapplication.log')
		command_log_fp = open(command_log, 'w')
		workingdir = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/%s' % application)
		command = ['tar', 'zcvf', temptarball, '.']

		tarrer = paasmaker.util.Popen(command,
			on_exit=self.stop,
			stderr=command_log_fp,
			stdout=command_log_fp,
			cwd=workingdir,
			io_loop=self.io_loop)

		code = self.wait()

		self.assertEquals(code, 0, "Unable to create temporary tarball file.")

		return temptarball