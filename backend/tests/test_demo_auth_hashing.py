import asyncio
import base64
import hashlib
import threading

import pytest
from fastapi import HTTPException

from backend.app.routers import mock_api
from backend.app.services import mock_store, password_service


@pytest.fixture
def demo_store(monkeypatch):
    store = mock_store.MemoryStore()
    monkeypatch.setattr(mock_api, 'store', store)
    monkeypatch.setattr(mock_api, 'get_settings', lambda: type('Settings', (), {'backend_mock_mode': True})())
    return store


@pytest.mark.parametrize('operation', ['register', 'login'])
def test_demo_password_work_keeps_event_loop_available(monkeypatch, demo_store, operation):
    async def run():
        loop = asyncio.get_running_loop()
        owner = threading.get_ident()
        started = asyncio.Event()
        release = threading.Event()
        def calculate(*args):
            assert threading.get_ident() != owner
            loop.call_soon_threadsafe(started.set)
            assert release.wait(5)
            return 'encoded-hash' if operation == 'register' else True
        monkeypatch.setattr(mock_api, 'hash_password' if operation == 'register' else 'verify_password', calculate)
        body = mock_api.Register(email='new@example.com', password='Password123!', display_name='신규회원') if operation == 'register' else mock_api.Credentials(email='user@lawpath.demo', password='Demo1234!')
        task = asyncio.create_task(mock_api.register(body) if operation == 'register' else mock_api.login(body))
        try:
            await asyncio.wait_for(started.wait(), 2)
            await asyncio.sleep(0)
            assert not task.done()
        finally:
            release.set()
        response = await task
        assert response['session_token'] in demo_store.sessions
        assert response['user']['role'] == 'USER'
        assert 'password_hash' not in response['user']
    asyncio.run(run())


def test_concurrent_demo_registration_keeps_email_unique(monkeypatch, demo_store):
    barrier = threading.Barrier(2)
    def calculate(password):
        barrier.wait(timeout=5)
        return 'encoded-hash'
    monkeypatch.setattr(mock_api, 'hash_password', calculate)
    body = mock_api.Register(email='same@example.com', password='Password123!', display_name='신규회원')
    async def run():
        return await asyncio.gather(mock_api.register(body), mock_api.register(body), return_exceptions=True)
    results = asyncio.run(run())
    assert sum(isinstance(item, dict) for item in results) == 1
    errors = [item for item in results if isinstance(item, HTTPException)]
    assert len(errors) == 1 and errors[0].status_code == 409
    assert sum(user['email'] == body.email for user in demo_store.users.values()) == 1
    assert len(demo_store.sessions) == 1


@pytest.mark.parametrize('password', ['Password123!', '한글🔐비밀번호'])
def test_shared_password_implementation_accepts_legacy_hashes(password):
    assert mock_store.hash_password is password_service.hash_password
    assert mock_store.verify_password is password_service.verify_password
    salt = bytes(range(16))
    legacy = 'scrypt$' + base64.b64encode(salt + hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)).decode()
    assert password_service.verify_password(password, legacy)
    assert not password_service.verify_password(password + 'wrong', legacy)
    first, second = mock_store.hash_password(password), password_service.hash_password(password)
    assert first != second
    assert mock_store.verify_password(password, second)
    assert password_service.verify_password(password, first)
