import asyncio
from dataclasses import replace
import threading

import pytest

from backend.app.services import auth_service
from backend.app.services.auth_service import AuthService, InactiveUserError, InvalidCredentialsError
from backend.app.repositories.user_repository import DbUser


class Users:
    def __init__(self):
        self.user = DbUser(42, 'member@example.com', 'encoded-hash', '회원', 'USER', True)
        self.created = None

    async def find_by_email(self, email):
        assert email == 'member@example.com'
        return self.user

    async def create_member(self, **kwargs):
        self.created = kwargs
        return self.user


@pytest.mark.parametrize('operation', ['register', 'login'])
def test_password_work_allows_event_loop_progress(monkeypatch, operation):
    async def run():
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        started = asyncio.Event()
        release = threading.Event()
        users = Users()

        def calculate(*args):
            assert threading.get_ident() != loop_thread
            assert args == (('secret',) if operation == 'register' else ('secret', 'encoded-hash'))
            loop.call_soon_threadsafe(started.set)
            assert release.wait(5), 'event loop did not release password worker'
            return 'new-hash' if operation == 'register' else True

        monkeypatch.setattr(auth_service, 'hash_password' if operation == 'register' else 'verify_password', calculate)
        service = AuthService(users)
        task = asyncio.create_task(
            service.register(' MEMBER@EXAMPLE.COM ', 'secret', ' 회원 ')
            if operation == 'register' else service.login(' MEMBER@EXAMPLE.COM ', 'secret')
        )
        try:
            await asyncio.wait_for(started.wait(), 2)
            await asyncio.sleep(0)
            assert not task.done()
        finally:
            release.set()
        assert await task == users.user
        if operation == 'register':
            assert users.created == dict(email='member@example.com', password_hash='new-hash', display_name='회원')

    asyncio.run(run())


def test_missing_user_does_not_verify_password(monkeypatch):
    users = Users()
    users.user = None
    def unexpected(*args):
        pytest.fail('missing user must not invoke password verification')
    monkeypatch.setattr(auth_service, 'verify_password', unexpected)
    with pytest.raises(InvalidCredentialsError):
        asyncio.run(AuthService(users).login('member@example.com', 'secret'))


@pytest.mark.parametrize('valid, error', [(False, InvalidCredentialsError), (True, InactiveUserError)])
def test_inactive_member_preserves_error_order(monkeypatch, valid, error):
    users = Users()
    users.user = replace(users.user, is_active=False)
    monkeypatch.setattr(auth_service, 'verify_password', lambda *args: valid)
    with pytest.raises(error):
        asyncio.run(AuthService(users).login('member@example.com', 'secret'))


@pytest.mark.parametrize('operation', ['register', 'login'])
def test_password_worker_errors_propagate_without_database_write(monkeypatch, operation):
    users = Users()
    def fail(*args):
        raise RuntimeError('password calculation failed')
    monkeypatch.setattr(auth_service, 'hash_password' if operation == 'register' else 'verify_password', fail)
    service = AuthService(users)
    with pytest.raises(RuntimeError, match='password calculation failed'):
        asyncio.run(service.register('member@example.com', 'secret', '회원') if operation == 'register' else service.login('member@example.com', 'secret'))
    assert users.created is None
