
from base import BasePrepare, BasePrepareTest

class PrepareShell(BasePrepare):
	def prepare(self, callback, error_callback):
		raise NotImplementedError("You must implement prepare()")