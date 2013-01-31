import subprocess

class DarwinSubprocess():
	@staticmethod
	def check_output(command):
		"""
		An alternative to
		`subprocess <http://docs.python.org/library/subprocess.html>`_.check_output()
		for OS X.
		
		* Depending on the version of Python installed, subprocess might not be EINTR safe;
		  i.e. Popen calls that are interrupted by a system signal might not be retried.
		  (EINTR is more likely to be a problem on OS X than on other platforms.)
		* :ref:`ProcessCheck <paasmaker.util.processcheck.ProcessCheck>` needs
		  to routinely call an external program (``ps -p``) with a non-zero exit
		  value, which makes subprocess throw an exception.

		For more on EINTR safety, see Python issues 
		`1068268 <http://bugs.python.org/issue1068268>`_, 
		`9867 <http://bugs.python.org/issue9867>`_, 
		`10956 <http://bugs.python.org/issue10956>`_, 
		and `12268 <http://bugs.python.org/issue12268>`_.
		"""
		ps = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
		output = None
		while output is None:
			try:
				output = ps.stdout.read()
			except IOError:
				# on OS X, this often means an EINTR
				# happened, so we can just try again
				pass
		
		# none of the users of this function
		# need leading/trailing whitespace
		output = output.strip()
		return output
