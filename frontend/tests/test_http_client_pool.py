from concurrent.futures import ThreadPoolExecutor
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Barrier, Thread
from time import sleep
from types import SimpleNamespace

import httpx
import pytest

from frontend.clients import backend_client as api
from frontend.clients import http_client as pool


@pytest.fixture
def isolated_pool():
    pool.close_client()
    yield
    pool.close_client()


def test_concurrent_initialization_creates_one_client_and_close_releases_it(monkeypatch, isolated_pool):
    original = httpx.Client
    created = []
    barrier = Barrier(8)

    def factory(**kwargs):
        sleep(0.01)
        client = original(transport=httpx.MockTransport(lambda request: httpx.Response(200)), **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(pool.httpx, 'Client', factory)

    def acquire(_):
        barrier.wait()
        return pool.get_client()

    with ThreadPoolExecutor(max_workers=8) as threads:
        clients = list(threads.map(acquire, range(8)))
    assert len(created) == 1
    assert all(client is created[0] for client in clients)
    pool.close_client()
    pool.close_client()
    assert created[0].is_closed
    assert pool.get_client() is not created[0]
    assert len(created) == 2


def test_concurrent_actors_never_share_auth_headers_or_response_cookies(monkeypatch, isolated_pool):
    original = httpx.Client

    def handle(request):
        assert 'cookie' not in request.headers
        owner = request.headers.get('Authorization', 'guest')
        sleep(0.001)
        return httpx.Response(200, json={'owner': owner}, headers={'Set-Cookie': f'session={owner}; Path=/'})

    monkeypatch.setattr(pool.httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    actors = ['Bearer user-a', None, 'Bearer user-b', None] * 16

    def ask(owner):
        headers = {'Authorization': owner} if owner else {}
        return pool.request('GET', 'http://backend.test/private', headers=headers).json()['owner']

    with ThreadPoolExecutor(max_workers=8) as threads:
        results = list(threads.map(ask, actors))
    assert results == [owner or 'guest' for owner in actors]
    assert not list(pool.get_client().cookies.jar)
    assert 'Authorization' not in pool.get_client().headers


def test_backend_requests_reuse_real_tcp_connection_without_cookie_or_identity_leaks(monkeypatch, isolated_pool):
    ports = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_GET(self):
            ports.append(self.client_address[1])
            body = json.dumps({'owner': self.headers.get('Authorization', 'guest'),
                               'cookie': self.headers.get('Cookie'), 'path': self.path}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Set-Cookie', 'session=private-value; Path=/')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        settings = SimpleNamespace(normalized_backend_url=f'http://127.0.0.1:{server.server_port}',
                                   frontend_request_timeout_seconds=3)
        monkeypatch.setattr(api, 'get_frontend_settings', lambda: settings)
        for owner in ['Bearer user-a', None, 'Bearer user-b', None]:
            headers = {'Authorization': owner} if owner else {}
            result = api._request('GET', '/private', headers=headers)
            assert result == {'owner': owner or 'guest', 'cookie': None, 'path': '/private'}
        assert len(set(ports)) == 1
    finally:
        pool.close_client()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_each_request_uses_current_backend_url_and_timeout(monkeypatch, isolated_pool):
    original = httpx.Client
    captured = []

    def handle(request):
        captured.append((str(request.url), request.extensions['timeout']['read']))
        return httpx.Response(200, json={'ok': True})

    monkeypatch.setattr(pool.httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    settings = SimpleNamespace(normalized_backend_url='http://first.test', frontend_request_timeout_seconds=2)
    monkeypatch.setattr(api, 'get_frontend_settings', lambda: settings)
    api._request('GET', '/health')
    settings.normalized_backend_url = 'http://second.test'
    settings.frontend_request_timeout_seconds = 7
    api._request('GET', '/health')
    assert captured == [('http://first.test/health', 2), ('http://second.test/health', 7)]
