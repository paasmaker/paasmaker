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
import signal
import tempfile
from tornado  import stack_context
from datetime import timedelta
from collections import deque
import unittest
from mock import patch
import functools

class Manager(object):
    def __init__(self, io_loop = None):
        self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()
        self.children = dict()
        signal.signal(signal.SIGCHLD, self.on_child_died)

    def on_child_died(self, *args, **kw_args):
        self.io_loop.add_timeout(timedelta(milliseconds = 10), self.reap)

    def reap(self):
        pid = None
        while True:
            try:
                pid, rc = os.waitpid(-1, os.WNOHANG)
            except OSError, e:
                if e.errno != 10: # No child processes
                    raise
                else:
                    break

            child = self.children.pop(pid, None)
            child.join(rc)

class Popen(subprocess.Popen):
    _manager = None

    def __init__(self, cmd, uid = None, redirect_stderr = False, on_stdout = None, on_stderr = None, on_exit = None, io_loop = None, *args, **kwargs):
        if isinstance(cmd, basestring):
            cmd = shlex.split(str(cmd))

        self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()

        if on_stdout:
            self.on_stdout = stack_context.wrap(on_stdout)
            kwargs['stdout'] = subprocess.PIPE
        if redirect_stderr:
            kwargs['stderr'] = subprocess.STDOUT
        elif on_stderr:
            self.on_stderr = stack_context.wrap(on_stderr)
            kwargs['stderr'] = subprocess.PIPE
        if on_exit:
            self.on_exit = stack_context.wrap(on_exit)

        kwargs['stdin'] = subprocess.PIPE

        if uid is not None:
            kwargs['preexec_fn'] = lambda: os.setuid(uid)

        super(Popen, self).__init__(cmd, *args, **kwargs)
        self.prepare_stdin()

        with stack_context.NullContext():
            if hasattr(self, 'on_stdout'):
                self.prepare_fd('stdout')
            if hasattr(self, 'on_stderr'):
                self.prepare_fd('stderr')

        self.manager.children[self.pid] = self

    @property
    def manager(self):
        if self._manager is None:
            self.__class__._manager = Manager(io_loop = self.io_loop)
        return self._manager

    def callback(self, callback, *args, **kwargs):
        with stack_context.NullContext():
            self.io_loop.add_callback(functools.partial(callback, *args, **kwargs))

    def unblock_fd(self, fd):
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def prepare_stdin(self):
        self.write_buffer = deque()
        self._writing = False
        self.stdin_writer = self.stdin.fileno()
        self.unblock_fd(self.stdin_writer)

    def prepare_fd(self, facility):
        reader = getattr(self, facility).fileno()
        setattr(self, '%s_reader' % facility, reader)
        self.unblock_fd(reader)
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
                self.io_loop.remove_handler(fd)

        except OSError, e:
            if e.errno != 11: # Resource temporarily unavailable
                logging.error("Exception while reading from child pipe: %r" %e)
        else:
            if getattr(self, 'stdout_reader', None) == fd:
                self.callback(self.on_stdout, data)
                if len(data) == 0:
                    del self.stdout_reader
            elif getattr(self, 'stderr_reader', None) == fd:
                self.callback(self.on_stderr, data)
                if len(data) == 0:
                    del self.stderr_reader

    def _stdin_ready(self, fd, events):
        while self.write_buffer:
            try:
                data = self.write_buffer.popleft()
                bytes_written = os.write(fd, data)
                if bytes_written < len(data):
                    self.write_buffer.appendleft(data[bytes_written:])
            except OSError, e:
                if e.errno != 11: # Resource temporarily unavailable
                    logging.error("Exception while writing to child pipe: %r" %e)
                self.write_buffer.appendleft(data)

        self.io_loop.remove_handler(fd)
        self._writing = False

    def write(self, data):
        self.write_buffer.append(data)
        if not self._writing:
            with stack_context.NullContext():
                self.io_loop.add_handler(self.stdin_writer, self._stdin_ready, self.io_loop.WRITE)
            self._writing = True

    def __del__(self):
        self.drain()
        super(Popen, self).__del__()

    def join(self, rc):
        if hasattr(self, 'on_exit'):
            self.callback(self.on_exit, rc)
        super(Popen, self).join()

class PopenTest(tornado.testing.AsyncTestCase):
    def setUp(self):
        super(PopenTest, self).setUp()
        Popen._manager = None
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

    def relative_command(self, cmd):
        return [
            sys.executable,
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'misc', cmd))
        ]

    def make_command(self, iterations, itertime, killtime):
        return self.relative_command("make_it_last.py") + [ "%d" % iterations, "%0.2f" % itertime, "%0.2f" % killtime ]

    def make_command_no_new_lines(self, iterations, itertime, killtime):
        return self.relative_command("print_wo_newlines.py") + [ "%d" % iterations, "%0.2f" % itertime, "%0.2f" % killtime ]

    def on_stdout(self, data):
        self.stdout.append(data)
        self.stop()

    def on_stderr(self, data):
        self.stderr.append(data)
        self.stop()

    def on_output_sink(self, data):
        pass

    def test_line_streaming_wo_newline(self):
        chars_to_print = 409600
        cmd = self.make_command_no_new_lines(chars_to_print, 0.001, 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, on_stderr=self.on_output_sink)

        self.wait()
        self.wait()
        self.io_loop.add_timeout(time.time()+0.01, self.stop)
        self.wait()
        self.p.terminate()
        self.p.wait()
        self.io_loop.add_timeout(time.time()+0.01, self.stop)
        self.wait()
        self.assertEqual(len(self.stdout), 3)

    def test_popen(self):
        cmd = self.make_command(1, 0., 0.)
        # CAUTION: This test is being a hiesen test. It works when you don't run
        # all unit tests, but then sometimes fails when you run the whole suite.
        # This bug should almost certainly be fixed at some time.
        self.p = Popen(cmd, io_loop=self.io_loop, close_fds=True, on_stdout=self.on_output_sink, on_stderr=self.on_output_sink, on_exit=self.stop)
        self.wait()

    def test_popen_exit_callback(self):
        # TODO: This sometimes fails with a timeout depending on what unit tests it's run with.
        cmd = self.make_command(1, 0., 0.)
        def on_exit(rc):
            self.stop(rc)
        self.p = Popen(cmd, io_loop=self.io_loop, close_fds=True, on_exit = on_exit, on_stdout=self.on_output_sink, on_stderr=self.on_output_sink)
        rc = self.wait()
        self.assertEqual(rc, 0)

    def test_popen_stdout(self):
        cmd = self.make_command(1, 0., 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, close_fds=True, on_stderr=self.on_output_sink)
        self.wait()
        self.assertEqual(len(self.stdout), 1)

    def test_popen_stdout_3_iterations(self):
        cmd = self.make_command(3, 0., 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, close_fds=True, on_stderr=self.on_output_sink)
        self.wait()
        self.assertEqual(len(self.stdout[0].split('\n')), 4)

    def test_popen_stdout_3_iterations_w_delay(self):
        cmd = self.make_command(3, 0.05, 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, close_fds=True, on_stderr=self.on_output_sink)
        self.wait()
        self.assertEqual(len(self.stdout[0].split('\n')), 4)

    def test_popen_stderr(self):
        cmd = self.make_command(1, 0., 0.)
        self.p = Popen(cmd, on_stderr=self.on_stderr, io_loop=self.io_loop, close_fds=True, on_stdout=self.on_output_sink)
        self.wait()
        self.assertEqual(len(self.stderr), 1)

    def test_popen_both(self):
        cmd = self.make_command(1, 0., 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, on_stderr=self.on_stderr, io_loop=self.io_loop, close_fds=True)
        self.wait()
        self.wait()
        self.assertEqual(len(self.stdout), 1)
        self.assertEqual(len(self.stderr), 1)

    def test_popen_to_file(self):
        # This tests if we can redirect the output to a file directly.
        cmd = self.make_command(1, 0., 0.)
        filename = tempfile.mkstemp()[1]
        fp = open(filename, 'wb')
        self.p = Popen(cmd, stdout=fp, stderr=fp, io_loop=self.io_loop, close_fds=True, on_exit=self.stop)
        code = self.wait()
        self.assertEqual(code, 0, "Process did not exit cleanly.")
        fp.close()
        fp = open(filename, 'rb')
        fp.seek(0)
        rawdata = fp.read()
        self.assertEqual(rawdata.count('iter'), 2, "Output did not capture output.")
        fp.close()
        os.unlink(filename)

    def test_popen_redirect(self):
        cmd = self.make_command(1, 0., 0.)
        self.p = Popen(cmd, on_stdout=self.on_stdout, redirect_stderr=True, io_loop=self.io_loop, close_fds=True)
        self.wait()
        self.wait()
        self.assertEqual(len(self.stdout), 2)

    def test_popen_write(self):
        cmd = self.relative_command('echo.py')
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, close_fds=True, on_stderr=self.on_output_sink)
        self.p.write('hello\n')
        self.wait()
        self.assertEqual(self.stdout, ['hello\n'])

    def test_popen_partial_write(self):
        cmd = self.relative_command('echo.py')
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, close_fds=True, on_stderr=self.on_output_sink)
        test = self

        class MockWrite(object):
            def __init__(self):
                self.args = []

            def __call__(self, fd, data):
                self.args.append(data)
                test.stop()
                return 1

        with patch('os.write', new_callable = MockWrite) as mock_write:
            self.p.write('12')
            self.wait()
            self.assertEqual(mock_write.args, ['12', '2'])

    def test_popen_write_retry(self):
        cmd = self.relative_command('echo.py')
        self.p = Popen(cmd, on_stdout=self.on_stdout, io_loop=self.io_loop, close_fds=True, on_stderr=self.on_output_sink)
        test = self

        class MockWrite(object):
            def __init__(self):
                self.called = False
                self.args = []

            def __call__(self, fd, data):
                self.args.append(data)
                if not self.called:
                    self.called = True
                    raise OSError()
                test.stop()
                return 2

        with patch('os.write', new_callable = MockWrite) as mock_write:
            self.p.write('12')
            self.wait()
            self.assertEqual(mock_write.args, ['12', '12'])