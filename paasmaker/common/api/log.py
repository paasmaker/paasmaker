
import logging

import paasmaker
from apirequest import APIRequest, StreamAPIRequest, APIResponse

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Stream logs back to the client.
class LogStreamAPIRequest(StreamAPIRequest):

	def subscribe(self, job_id, position=0, unittest_force_remote=False):
		"""
		Subscribe to a remote log. The callback you set with ``set_lines_callback()``
		will be called.

		To stop streaming, call ``unsubscribe()`` with the same job ID.

		:arg str job_id: The job ID to subscribe to.
		:arg int|None position: The log position to stream from, in bytes.
		:arg bool unittest_force_remote: For internal testing use. Do not use
			this.
		"""
		logging.debug("Subscribing to %s", job_id)
		self.emit('log.subscribe', {'job_id': job_id, 'position': position, 'unittest_force_remote': unittest_force_remote})

	def unsubscribe(self, job_id):
		"""
		Unsubscribe from a remote log. This stops new entries from coming through.
		"""
		logging.debug("Unsubscribing from %s", job_id)
		self.emit('log.unsubscribe', {'job_id': job_id})

	def set_lines_callback(self, callback):
		"""
		Set the callback called when new log lines are available. The callback looks
		like this::

			def got_lines(job_id, lines, position):
				# lines is a list.
				print "\n".join(lines)
		"""
		self.on('log.lines', callback)

	def set_cantfind_callback(self, callback):
		"""
		Sets the callback called when the remote end can't find a log. This will
		be called just after your call to ``subscribe()``.

		The callback looks like so::

			def cantfind(job_id, message):
				pass
		"""
		self.on('log.cantfind', callback)

	def set_zerosize_callback(self, callback):
		"""
		Sets the callback called when the log file is zero size. Later on, log lines
		might appear, so it's possible to have this callback called, and then later
		have lines callbacks called.

		The callback looks like this::

			def zerosize(job_id):
				pass

		"""
		self.on('log.zerosize', callback)