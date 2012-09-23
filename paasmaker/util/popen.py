# Based on https://gist.github.com/3492507.
# Epic win.

import logging
import shlex
import subprocess
import tornado
import tornado.testing
import os
import fcntl
import sys
import time

class Popen(subprocess.Popen):
    def __init__(self, cmd, uid=None, redirect_stderr=False, on_stdout=None, on_stderr=None, io_loop=None, on_exit=None, *args, **kwargs):
        if isinstance(cmd, basestring):
            cmd = shlex.split(str(cmd))

        self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()

        if on_stdout:
            self.on_stdout = on_stdout
            kwargs['stdout'] = subprocess.PIPE
        if redirect_stderr:
            kwargs['stderr'] = subprocess.STDOUT
        elif on_stderr:
            self.on_stderr = on_stderr
            kwargs['stderr'] = subprocess.PIPE

        if on_exit:
            self.on_exit = on_exit

        if uid is not None:
            kwargs['preexec_fn'] = lambda: os.setuid(uid)

        super(Popen, self).__init__(cmd, *args, **kwargs)
        if hasattr(self, 'on_stdout'):
            self.prepare_fd('stdout')
        if hasattr(self, 'on_stderr'):
            self.prepare_fd('stderr')

    def prepare_fd(self, facility):
        reader = getattr(self, facility).fileno()
        setattr(self, '%s_reader' % facility, reader)
        flags = fcntl.fcntl(reader, fcntl.F_GETFL)
        fcntl.fcntl(reader, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self.io_loop.add_handler(reader, self._data_ready, self.io_loop.READ)

    def drain(self):
        if getattr(self, 'stdout_reader', None):
            self.read_from_stdout()
            del self.stdout_reader
        if getattr(self, 'stderr_reader', None):
            self.read_from_stderr()
            del self.stderr_reader

    def read_from_stderr(self):
        self._data_ready(self.stderr_reader, self.io_loop.READ)

    def read_from_stdout(self):
        self._data_ready(self.stdout_reader, self.io_loop.READ)

    def _data_ready(self, fd, events):
        try:
            data = os.read(fd, 4096)
            if len(data) == 0:
                logging.info("Child pipe closed")
                # TODO: Sigh, have to call back once it's settled.
                self.io_loop.add_timeout(time.time() + 0.1, self.check_completed)
                self.io_loop.remove_handler(fd)

        except OSError, e:
            if e.errno != 11: # Resource temporarily unavailable
                logging.error("Exception while reading from child pipe: %r" %e)
        else:
            if getattr(self, 'stdout_reader', None) == fd:
                self.on_stdout(data)
                if len(data) == 0:
                    del self.stdout_reader
            elif getattr(self, 'stderr_reader', None) == fd:
                self.on_stderr(data)
                if len(data) == 0:
                    del self.stderr_reader

    def __del__(self):
        self.drain()
        super(Popen, self).__del__()

    def check_completed(self):
        self.poll()
        if self.returncode is not None and self.on_exit:
            logging.info("Process is complete with return code %d", self.returncode)
            self.on_exit(self.returncode)
            # Clear the callback once called - this prevents several calls
            # due to the closing of stderr/stdout.
            self.on_exit = None

class PopenTest(tornado.testing.AsyncTestCase):
    def log(self, msg):
        return
        print self.__class__, msg

    def setUp(self):
        super(PopenTest, self).setUp()
        self.stdout = []
        self.stderr = []

    def kill(self):
        try:
            os.kill(self.p.pid, signal.SIGKILL)
            pid, rc = os.waitpid(self.p.pid, 0)
        except Exception, e:
            pass

    def tearDown(self):
        self.kill()

    def get_helper_path(self):
    	here = os.path.dirname(__file__)
    	there = os.path.join(here, '..', '..', 'misc')
    	final = os.path.abspath(there)
    	return final

    def make_command(self, iterations, itertime, killtime):
        return "%s %s/make_it_last.py %d %0.2f %0.2f" %(
            sys.executable, self.get_helper_path(), iterations, itertime, killtime
        )

    def make_command_no_new_lines(self, iterations, itertime, killtime):
        return "%s %s/print_wo_newlines.py %d %0.2f %0.2f" %(
            sys.executable, self.get_helper_path(), iterations, itertime, killtime
        )

    def on_stdout(self, data):
        self.stdout.append(data)
        self.stop()

    def on_stderr(self, data):
        self.stderr.append(data)
        self.stop()

    def on_sink(self, data):
        # Do nothing!
        pass

    def test_line_streaming_wo_newline(self):
        chars_to_print = 409600
        cmd = self.make_command_no_new_lines(chars_to_print, 0.001, 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, on_stderr=self.on_stderr)

        self.wait()
        self.wait()
        self.io_loop.add_timeout(time.time()+0.01, self.stop)
        self.wait()
        self.p.terminate()
        self.p.wait()
        self.io_loop.add_timeout(time.time()+0.01, self.stop)
        self.wait()
        self.assertEquals(len(self.stdout), 3)

    def test_popen(self):
        cmd = self.make_command(1, 0., 0.)
        self.p = Popen(cmd, io_loop=self.io_loop, close_fds=True, on_stdout=self.on_sink, on_stderr=self.on_sink)

    def test_popen_exited(self):
        cmd = self.make_command(1, 0., 0.)
        self.p = Popen(cmd, io_loop=self.io_loop, close_fds=True, on_stdout=self.on_sink, on_stderr=self.on_sink, on_exit=self.stop)
        code = self.wait()
        self.assertEquals(code, 0)

    def test_popen_stdout(self):
        cmd = self.make_command(1, 0., 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, close_fds=True, on_stderr=self.on_sink)
        self.wait()
        self.assertEquals(len(self.stdout), 1)

    def test_popen_stdout_3_iterations(self):
        cmd = self.make_command(3, 0., 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, close_fds=True, on_stderr=self.on_sink)
        self.wait()
        self.assertEquals(len(self.stdout[0].split('\n')), 4)

    def test_popen_stdout_3_iterations_w_delay(self):
        cmd = self.make_command(3, 0.05, 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, close_fds=True, on_stderr=self.on_sink)
        self.wait()
        self.assertEquals(len(self.stdout[0].split('\n')), 4)

    def test_popen_stderr(self):
        cmd = self.make_command(1, 0., 0.)
        self.p = Popen(cmd, on_stdout=self.on_sink, on_stderr=self.on_stderr, io_loop=self.io_loop, close_fds=True)
        self.wait()
        self.assertEquals(len(self.stderr), 1)

    def test_popen_both(self):
        cmd = self.make_command(1, 0., 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, on_stderr=self.on_stderr, io_loop=self.io_loop, close_fds=True)
        self.wait()
        self.wait()
        self.assertEquals(len(self.stdout), 1)
        self.assertEquals(len(self.stderr), 1)

    def test_popen_redirect(self):
        cmd = self.make_command(1, 0., 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, redirect_stderr=True, io_loop=self.io_loop, close_fds=True)
        self.wait()
        self.wait()
        self.assertEquals(len(self.stdout), 2)