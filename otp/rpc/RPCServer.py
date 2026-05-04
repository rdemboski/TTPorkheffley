from panda3d.core import *
from direct.directnotify.DirectNotifyGlobal import *
from direct.showbase import PythonUtil
from direct.fsm.FSM import *
import urllib.parse
import binascii
import json
import socket
import selectors
import http.client
import time

rpc_server_endpoint = ConfigVariableString(
    'rpc-server-endpoint', '',
    'Specifies the URL that the RPC-server will listen on.')

rpc_server_listen = ConfigVariableInt(
    'rpc-server-listen', 5,
    'Specifies the depth of the listening socket\'s listen queue.')

rpc_server_polltime = ConfigVariableInt(
    'rpc-server-polltime', 2,
    'Specifies the number of milliseconds, per polling iteration, to wait for'
    ' incoming requests.')

rpc_server_polliters = ConfigVariableInt(
    'rpc-server-polliters', 5,
    'Specifies the number of polling iterations to perform each frame.')

rpc_server_keepalive = ConfigVariableInt(
    'rpc-server-keepalive', 5,
    'How many seconds the server will leave a Keep-Alive connection open.')

_selector = selectors.DefaultSelector()


class _Dispatcher:
    """Non-blocking socket dispatcher (replaces asyncore.dispatcher)."""

    def __init__(self, sock=None):
        self._sock = None
        self._write_buf = b''
        self._closing = False
        if sock is not None:
            self._attach(sock)

    def _attach(self, sock):
        self._sock = sock
        self._sock.setblocking(False)
        _selector.register(self._sock, selectors.EVENT_READ, self)

    def _update_selector(self):
        if self._sock is None:
            return
        events = selectors.EVENT_READ
        if self._write_buf:
            events |= selectors.EVENT_WRITE
        try:
            _selector.modify(self._sock, events, self)
        except KeyError:
            pass

    def create_socket(self, family=socket.AF_INET, stype=socket.SOCK_STREAM):
        self._sock = socket.socket(family, stype)
        self._sock.setblocking(False)

    def set_reuse_addr(self):
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def bind(self, addr):
        self._sock.bind(addr)

    def listen(self, backlog):
        self._sock.listen(backlog)
        _selector.register(self._sock, selectors.EVENT_READ, self)

    def push(self, data):
        if isinstance(data, str):
            data = data.encode('latin-1')
        self._write_buf += data
        self._update_selector()

    def close_when_done(self):
        self._closing = True
        if not self._write_buf:
            self._do_close()

    def handle_read_event(self):
        self.handle_read()

    def handle_write_event(self):
        if self._write_buf:
            try:
                sent = self._sock.send(self._write_buf)
                self._write_buf = self._write_buf[sent:]
            except OSError:
                self._do_close()
                return
        if not self._write_buf:
            if self._closing:
                self._do_close()
            else:
                self._update_selector()

    def _do_close(self):
        if self._sock is None:
            return
        try:
            _selector.unregister(self._sock)
        except KeyError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass
        self._sock = None

    def handle_read(self):
        pass

    def handle_close(self):
        pass


class _BufferedChat(_Dispatcher):
    """Buffered line/length reader (replaces asynchat.async_chat)."""

    def __init__(self, sock=None):
        super().__init__(sock)
        self._in_buf = b''
        self._terminator = None

    def set_terminator(self, term):
        if isinstance(term, str):
            term = term.encode('latin-1')
        self._terminator = term

    def handle_read(self):
        try:
            data = self._sock.recv(8192)
        except OSError:
            self._do_close()
            self.handle_close()
            return
        if not data:
            self._do_close()
            self.handle_close()
            return
        self._in_buf += data
        self._process_input()

    def _process_input(self):
        while self._terminator is not None:
            term = self._terminator
            if isinstance(term, int):
                if len(self._in_buf) >= term:
                    chunk = self._in_buf[:term].decode('latin-1')
                    self._in_buf = self._in_buf[term:]
                    self._terminator = None
                    self.collect_incoming_data(chunk)
                    self.found_terminator()
                else:
                    break
            else:
                idx = self._in_buf.find(term)
                if idx >= 0:
                    chunk = self._in_buf[:idx].decode('latin-1')
                    self._in_buf = self._in_buf[idx + len(term):]
                    self._terminator = None
                    self.collect_incoming_data(chunk)
                    self.found_terminator()
                else:
                    if len(self._in_buf) > len(term):
                        safe = len(self._in_buf) - len(term)
                        self.collect_incoming_data(self._in_buf[:safe].decode('latin-1'))
                        self._in_buf = self._in_buf[safe:]
                    break

    def collect_incoming_data(self, data):
        pass

    def found_terminator(self):
        pass


class RPCServer(_Dispatcher):
    notify = directNotify.newCategory('RPCServer')

    def __init__(self, handler, url=None):
        super().__init__()

        self.handler = handler
        url = urllib.parse.urlparse(url or rpc_server_endpoint.getValue())

        if url.scheme and url.scheme != 'http':
            self.notify.error('Scheme must be HTTP, not %s!' % url.scheme)

        hostname = url.hostname
        port = url.port or 80

        if hostname is None:
            return

        username = url.username
        password = url.password

        auth = username
        if password is not None:
            auth += ':' + password

        if auth is not None:
            self.auth = binascii.b2a_base64(auth.encode()).strip().decode('ascii')
        else:
            self.auth = None

        self.path = url.path or '/'

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((hostname, port))
        self.listen(5)

        taskMgr.add(self.task, 'RPCServer')

    def task(self, task):
        timeout = rpc_server_polltime.getValue() * 0.001
        count = rpc_server_polliters.getValue()
        for _ in range(count):
            events = _selector.select(timeout=timeout)
            for key, mask in events:
                obj = key.data
                if mask & selectors.EVENT_READ:
                    obj.handle_read_event()
                if mask & selectors.EVENT_WRITE:
                    obj.handle_write_event()
        return task.cont

    def handle_read_event(self):
        self.handle_accept()

    def handle_accept(self):
        try:
            sock, addr = self._sock.accept()
        except OSError:
            return
        RPCConnection(sock, self)

class RPCConnection(_BufferedChat, FSM):
    def __init__(self, sock, server):
        _BufferedChat.__init__(self, sock)
        FSM.__init__(self, 'RPCConnection')

        self.server = server

        self.data = ''
        self.found_terminator = lambda: None

        self.path = ''
        self.headers = {}
        self.id = None

        self.keepAlive = False
        self.timeout = None

        self.demand('ReadHeaders')

    def collect_incoming_data(self, data):
        self.data += data

    def handle_close(self):
        self.demand('Off')

    def enterReadHeaders(self):
        self.data = ''
        self.set_terminator('\r\n\r\n')
        self.found_terminator = self.__got_headers

    def __got_headers(self):
        self.set_terminator(None)

        self.keepAlive = False

        for i, line in enumerate(self.data.split('\n')):
            line = line.rstrip('\r')

            if i == 0:
                request = line.split(' ')
                if len(request) != 3:
                    return self.demand('HTTPError', 400)

                method, path, version = tuple(request)

                if method != 'POST':
                    return self.demand('HTTPError', 501)

                if version not in ('HTTP/1.0', 'HTTP/1.1'):
                    return self.demand('HTTPError', 505)

                self.path = path
            else:
                header = line.split(': ')
                if len(header) != 2:
                    return self.demand('HTTPError', 400)

                key, value = tuple(header)
                self.headers[key.lower()] = value

        if (self.headers.get('connection', '').lower() == 'keep-alive'):
            self.keepAlive = True

        self.demand('ReceiveData')

    def enterReceiveData(self):
        length = self.headers.get('content-length', '')
        if not length or not length.isdigit():
            return self.demand('HTTPError', 400)

        length = int(length)

        self.data = ''
        self.set_terminator(length)
        self.found_terminator = self.__got_post
        self.setTimeout(None)

    def __got_post(self):
        self.set_terminator(None)

        if self.server.auth is not None:
            if self.headers.get('authorization') != 'Basic ' + self.server.auth:
                return self.demand('HTTPError', 401)

        if self.server.path != self.path:
            return self.demand('HTTPError', 404)

        self.id = None

        try:
            request = json.loads(self.data)
        except ValueError:
            return self.demand('JSONError', -32700, 'Parse error')

        if 'method' not in request or 'params' not in request:
            return self.demand('JSONError', -32600, 'Invalid Request')

        self.id = request.get('id')

        if not isinstance(request['method'], str) or \
           not isinstance(request['params'], (tuple, list, dict)):
            return self.demand('JSONError', -32600, 'Invalid Request')

        method = getattr(self.server.handler, 'rpc_' + str(request['method']), None)
        params = request['params']
        if not method:
            return self.demand('JSONError', -32601, 'Method not found')

        request = RPCRequest(self)
        try:
            if isinstance(params, dict):
                result = method(request, **params)
            else:
                result = method(request, *params)
        except Exception:
            self.demand('JSONError', -1, PythonUtil.describeException())
        else:
            if result != request:
                if request.active:
                    request.result(result)

    def enterOff(self):
        self.setTimeout(None)
        self.close_when_done()

    def setTimeout(self, timeout):
        if self.timeout is not None:
            self.timeout.remove()

        if timeout is not None:
            self.timeout = taskMgr.doMethodLater(timeout, self.demand,
                                                 'RPCConnection-timeout-%d' % id(self),
                                                 extraArgs=['Off'])

    def sendResponse(self, body, contentType=None, code=200):
        description = http.client.responses.get(code, 'Code %d' % code)

        response =  'HTTP/1.1 %d %s\r\n' % (code, description)
        response += 'Date: %s\r\n' % time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
        response += 'Server: OTP-RPCServer/0.3\r\n'
        response += 'Content-Length: %d\r\n' % len(body)
        if contentType:
            response += 'Content-Type: %s\r\n' % contentType

        if self.server.auth is not None:
            response += 'WWW-Authenticate: Basic realm="OTP RPC server"\r\n'

        if self.keepAlive:
            response += 'Keep-Alive: timeout=%d\r\n' % rpc_server_keepalive.getValue()
            response += 'Connection: Keep-Alive\r\n'
        else:
            response += 'Connection: close\r\n'

        response += '\r\n' + body

        self.push(response)

        if self.keepAlive:
            self.setTimeout(rpc_server_keepalive.getValue())
            self.demand('ReadHeaders')
        else:
            self.demand('Off')

    def sendJSON(self, data):
        body = json.dumps(data) + '\n'
        self.sendResponse(body, 'application/json', 200)

    def enterHTTPError(self, code):
        self.server.notify.warning('Received bad HTTP request: Error code %d' % code)
        description = http.client.responses.get(code, 'Code %d' % code)
        self.sendResponse('%d %s\n' % (code, description), 'text/plain', code)

    def enterJSONError(self, code, message):
        self.server.notify.warning('Received bad JSON request: Error code %d' % code)
        response = {'jsonrpc': '2.0',
                    'error': {'code': code,
                              'message': message},
                    'id': self.id}
        self.sendJSON(response)

class RPCRequest:
    def __init__(self, connection):
        self.connection = connection
        self.active = True

    def result(self, result):
        assert self.active
        self.active = False
        self.connection.sendJSON({'jsonrpc': '2.0',
                                  'result': result,
                                  'id': self.connection.id})

    def error(self, code, message):
        assert self.active
        self.active = False
        self.connection.demand('JSONError', code, message)
