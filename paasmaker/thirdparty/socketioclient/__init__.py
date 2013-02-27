# This class is from here: https://github.com/invisibleroads/socketIO-client
# It was under the MIT licence.
# It was then updated to allow it to work with Tornado, and support XHR Long polls.

from json import dumps, loads
import time
from urllib import urlopen, quote
import traceback
import logging

import tornado

from ..twc.websocket import WebSocket

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


__version__ = '0.3-tornado'


PROTOCOL = 1  # SocketIO protocol version
FRAME_SEPARATOR = u'\ufffd'

# TODO:
# - XHR Longpoll support.
# - When calling the callbacks, the stack context is not preserved. This can lead to dead spots in the code.


class BaseNamespace(object):  # pragma: no cover

    def __init__(self, socketIO):
        self.socketIO = socketIO

    def on_connect(self, socketIO):
        pass

    def on_disconnect(self):
        pass

    def on_error(self, reason, advice):
        logger.debug('[SocketIO client unhandled] [Error] %s' % advice)

    def on_message(self, messageData):
        logger.debug('[SocketIO client unhandled] [Message] %s' % messageData)

    def on_(self, eventName, *eventArguments):
        logger.debug('[SocketIO client unhandled] [Event] %s%s' % (eventName, eventArguments))

    def on_open(self, *args):
        logger.debug('[SocketIO client unhandled] [Open] %s', args)

    def on_close(self, *args):
        logger.debug('[SocketIO client unhandled] [Close] %s', args)

    def on_retry(self, *args):
        logger.debug('[SocketIO client unhandled] [Retry] %s', args)

    def on_reconnect(self, *args):
        logger.debug('[SocketIO client unhandled] [Reconnect] %s', args)

class WebsocketTransport(WebSocket):

    def configure(self, socketio):
        self.socketio = socketio
        self.connected = False

    def on_open(self):
        self.connected = True
        self.socketio._transport_connected()

    def on_message(self, data):
        self.socketio._recv_packet(data)

    def on_close(self):
        self.connected = False
        self.socketio._transport_disconnected()

    def on_unsupported(self):
        # Not supported by remote end or something in between.
        self.socketio._websocket_unsupported()

    def send(self, data):
        self.write_message(data)

class LongpollTransport(object):

    def __init__(self, endpoint, io_loop):
        self.endpoint = endpoint
        self.io_loop = io_loop

        self.sending = False
        self.receiving = False
        self.queue = []

    def configure(self, socketio):
        self.socketio = socketio

        # Start receiving the first time.
        self._receive()

    def _receive(self):
        if self.receiving:
            return

        def receive_result(response):
            self.receiving = False

            # Was it an error?
            if response.code != 200:
                # It was an error. Wait, and retry again shortly.
                error_callback = self.socketio.get_callback('', 'connection_error')
                error_callback(str(response.error))

                self.io_loop.add_timeout(time.time() + 1, self._receive)
            else:
                # Got a response. Parse it.
                packets = response.body.split(FRAME_SEPARATOR)
                for packet in packets:
                    self.socketio._recv_packet(packet)

                # And listen again.
                self.io_loop.add_callback(self._receive)

        self.receiving = True
        client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
        client.fetch(self.endpoint, receive_result)

    def send(self, data):
        if self.sending:
            self.queue.append(data)
        else:
            # Send off what we have.
            self.queue.append(data)
            self._real_send()

    def _real_send(self):
        if len(self.queue) > 0:
            this_send = self.queue
            self.queue = []

            body = FRAME_SEPARATOR.join(this_send)
            self.sending = True

            def send_complete(response):
                self.sending = False

                if response.code != 200:
                    # It failed. Put everything back on the queue for later.
                    all_queue = this_send
                    all_queue.extend(self.queue)
                    self.queue = all_queue

                    error_callback = self.socketio.get_callback('', 'connection_error')
                    error_callback(str(response.error))

                    # Try again shortly.
                    self.io_loop.add_callback(time.time() + 1, self._real_send)

                # Call send again in case something was queued
                # whilst we were sending.
                self._real_send()

            client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
            client.fetch(
                self.endpoint,
                send_complete,
                method="POST",
                body=body
            )

class SocketIO(object):

    messageID = 0

    def __init__(self, host, port, Namespace=BaseNamespace, secure=False, io_loop=None, query=None, force_longpoll=False):
        self.host = host
        self.port = int(port)
        self.namespace = Namespace(self)
        self.secure = secure
        self.query = query

        self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()

        self.channelByName = {}
        self.callbackByEvent = {}

        self.force_longpoll = force_longpoll

    def __del__(self):
        self.heartbeat_periodic.stop()
        self.connection.close()

    def connect(self):
        self.__connect()

    def __connect(self):
        # Handshake with the socket.io server.
        self.baseURL = '%s:%d/socket.io/%s' % (self.host, self.port, PROTOCOL)
        handshakeURL = '%s://%s/' % ('https' if self.secure else 'http', self.baseURL)
        if self.query:
            handshakeURL = "%s?%s" % (handshakeURL, self.query)

        client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
        client.fetch(handshakeURL, self.__on_handshake_response)

    def __on_handshake_response(self, response):
        error_callback = self.get_callback('', 'connection_error')

        if 403 == response.code:
            auth_callback = self.get_callback('', 'access_denied')
            auth_callback('Access is denied.')
            return

        if 200 != response.code:
            error_callback(response)
            return

        responseParts = response.body.split(':')
        self.sessionID = responseParts[0]
        self.heartbeatTimeout = int(responseParts[1])
        self.connectionTimeout = int(responseParts[2])
        self.supportedTransports = responseParts[3].split(',')

        if 'websocket' not in self.supportedTransports:
            error_callback('Websocket not supported by remote.')
            return

        if self.force_longpoll:
            self._websocket_unsupported()
            return

        socketURL = '%s://%s/websocket/%s' % (
            'wss' if self.secure else 'ws', self.baseURL, self.sessionID)
        self.connection = WebsocketTransport(socketURL, io_loop=self.io_loop)
        self.connection.configure(self)

        # Once the transport is connected, it will call _transport_connected().

    def _transport_connected(self):
        # Start the heartbeat timer.
        self.heartbeat_periodic = tornado.ioloop.PeriodicCallback(
            self._send_heartbeat,
            (self.heartbeatTimeout - 2) * 1000,
            io_loop=self.io_loop
        )
        self.heartbeat_periodic.start()

        # And send one heartbeat to start - this will emit a connect
        # event when it replies.
        self._send_heartbeat()

    def _websocket_unsupported(self):
        # No websockets. Oh well, let's try again with a long poll instead.
        longpollURL = '%s://%s/xhr-polling/%s' % (
            'https' if self.secure else 'http', self.baseURL, self.sessionID)
        self.connection = LongpollTransport(longpollURL, self.io_loop)
        self.connection.configure(self)

        # Call _transport_connected(), which sets up the heartbeat,
        # and sends a heartbeat as well.

    def _recv_packet(self, packet):
        # Got a packet from the remote end.
        # Parse it and handle it.
        code, packetID, channelName, data = -1, None, None, None
        packetParts = packet.split(':', 3)
        packetCount = len(packetParts)
        if 4 == packetCount:
            code, packetID, channelName, data = packetParts
        elif 3 == packetCount:
            code, packetID, channelName = packetParts
        elif 1 == packetCount:  # pragma: no cover
            code = packetParts[0]

        code = int(code)

        try:
            delegate = {
                0: self.on_disconnect,
                1: self.on_connect,
                2: self.on_heartbeat,
                3: self.on_message,
                4: self.on_json,
                5: self.on_event,
                6: self.on_acknowledgment,
                7: self.on_error,
            }[code]

            delegate(packetID, channelName, data)
        except KeyError:
            # Unsuported action. Ignore.
            pass

    def on_disconnect(self, packetID, channelName, data):
        callback = self.get_callback(channelName, 'disconnect')
        callback()

    def on_connect(self, packetID, channelName, data):
        callback = self.get_callback(channelName, 'connect')
        callback(self)

    def on_heartbeat(self, packetID, channelName, data):
        pass

    def on_message(self, packetID, channelName, data):
        callback = self.get_callback(channelName, 'message')
        callback(data)

    def on_json(self, packetID, channelName, data):
        callback = self.get_callback(channelName, 'message')
        callback(loads(data))

    def on_event(self, packetID, channelName, data):
        valueByName = loads(data)
        eventName = valueByName['name']
        eventArguments = valueByName['args']
        callback = self.get_callback(channelName, eventName)
        try:
            callback(*eventArguments)
        except Exception, ex:
            # TODO: Pass this exception back via the stack context.
            print str(ex)
            traceback.print_exc()

    def on_acknowledgment(self, packetID, channelName, data):
        dataParts = data.split('+', 1)
        messageID = int(dataParts[0])
        arguments = loads(dataParts[1]) or []
        try:
            callback = self.callbackByMessageID[messageID]
        except KeyError:
            pass
        else:
            del self.callbackByMessageID[messageID]
            callback(*arguments)

    def on_error(self, packetID, channelName, data):
        reason, advice = data.split('+', 1)
        callback = self.get_callback(channelName, 'error')
        callback(reason, advice)

    def _send_packet(self, code, channelName='', data=''):
        self.connection.send(':'.join([str(code), '', channelName, data]))

    def disconnect(self, channelName=''):
        self._send_packet(0, channelName)
        if channelName:
            del self.channelByName[channelName]
        else:
            self.__del__()

    @property
    def connected(self):
        return self.connection.connected

    def connect_channel(self, channelName, Namespace=BaseNamespace):
        channel = Channel(self, channelName, Namespace)
        self.channelByName[channelName] = channel
        self._send_packet(1, channelName)
        return channel

    def _send_heartbeat(self):
        try:
            self._send_packet(2)
        except:
            self.__del__()

    def message(self, messageData, callback=None, channelName=''):
        if isinstance(messageData, basestring):
            code = 3
            data = messageData
        else:
            code = 4
            data = dumps(messageData)
        self._send_packet(code, channelName, data, callback)

    def emit(self, eventName, *eventArguments, **eventKeywords):
        code = 5
        channelName = eventKeywords.get('channelName', '')
        data = dumps(dict(name=eventName, args=eventArguments))
        self._send_packet(code, channelName, data)

    def get_callback(self, channelName, eventName):
        'Get callback associated with channelName and eventName'
        socketIO = self.channelByName[channelName] if channelName else self
        try:
            return socketIO.callbackByEvent[eventName]
        except KeyError:
            pass
        namespace = socketIO.namespace

        def callback_(*eventArguments):
            return namespace.on_(eventName, *eventArguments)
        return getattr(namespace, name_callback(eventName), callback_)

    def set_callback(self, callback):
        'Set callback that will be called after receiving an acknowledgment'
        self.messageID += 1
        self.namespaceThread.set_callback(self.messageID, callback)
        return '%s+' % self.messageID

    def on(self, eventName, callback):
        self.callbackByEvent[eventName] = tornado.stack_context.wrap(callback)


class Channel(object):

    def __init__(self, socketIO, channelName, Namespace):
        self.socketIO = socketIO
        self.channelName = channelName
        self.namespace = Namespace(self)
        self.callbackByEvent = {}

    def disconnect(self):
        self.socketIO.disconnect(self.channelName)

    def emit(self, eventName, *eventArguments):
        self.socketIO.emit(eventName, *eventArguments,
            channelName=self.channelName)

    def message(self, messageData, callback=None):
        self.socketIO.message(messageData, callback,
            channelName=self.channelName)

    def on(self, eventName, eventCallback):
        self.callbackByEvent[eventName] = tornado.stack_context.wrap(eventCallback)


def name_callback(eventName):
    return 'on_' + eventName.replace(' ', '_')