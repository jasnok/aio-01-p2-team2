import asyncio
from types import SimpleNamespace

import pytest

from backend.app.services import guest_session_service, legal_term_run_store, session_service


@pytest.fixture(params=['auth', 'guest', 'term'])
def store(request, monkeypatch):
    settings = SimpleNamespace(redis_enabled=False, auth_session_ttl_seconds=10,
                               guest_session_ttl_seconds=10, term_run_ttl_seconds=10)
    clock = [0.0]
    for module in (session_service, guest_session_service, legal_term_run_store):
        monkeypatch.setattr(module, 'get_settings', lambda: settings)
        monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    kind = request.param
    if kind == 'auth':
        service = session_service.SessionService()
    elif kind == 'guest':
        service = guest_session_service.GuestSessionService()
    else:
        service = legal_term_run_store.LegalTermRunStore()

    async def write(key):
        if kind == 'auth':
            token, _ = await service.issue(1)
            return token
        if kind == 'guest':
            await service.save_analysis(key, dict(run_id=key, question='임시 질문', status='completed',
                                                   result={'answer': key}))
        else:
            await service.remember(actor={'id': 1, 'role': 'USER'}, request_id=key,
                                   question='임시 질문', answer=key, conversation_id=None)
        return key

    async def read(key):
        if kind == 'auth':
            return await service.read(key)
        if kind == 'guest':
            items, _ = await service.list_analyses(key)
            return items or None
        try:
            return await service.get_for_actor(key, {'id': 1, 'role': 'USER'})
        except legal_term_run_store.LegalTermRunNotFoundError:
            return None

    return service, clock, write, read


def test_new_write_removes_unread_expired_entries_and_keeps_live_sessions(store):
    service, clock, write, read = store

    async def verify():
        old = [await write(f'old-{index}') for index in range(200)]
        clock[0] = 5.0
        live = await write('live')
        clock[0] = 10.0
        new = await write('new')
        # Check retention before reading old keys: reads already removed their own expired key.
        assert set(service._memory) == {live, new}
        assert all(key not in service._memory for key in old)
        assert await read(live) is not None
        assert await read(new) is not None
        assert await read(old[0]) is None
        clock[0] = 15.0
        assert await read(live) is None
        assert await read(new) is not None

    asyncio.run(verify())


def test_concurrent_new_writes_preserve_all_unexpired_sessions(store):
    service, clock, write, read = store

    async def verify():
        await write('expired')
        clock[0] = 10.0
        keys = await asyncio.gather(*(write(f'new-{index}') for index in range(32)))
        assert set(service._memory) == set(keys)
        assert all(item is not None for item in await asyncio.gather(*(read(key) for key in keys)))

    asyncio.run(verify())


def test_guest_rewrite_renews_ttl_without_losing_other_live_history(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(guest_session_service, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(guest_session_service, 'get_settings', lambda: SimpleNamespace(
        redis_enabled=False, guest_session_ttl_seconds=10))
    service = guest_session_service.GuestSessionService()

    def run(key):
        return dict(run_id=key, question='질문', status='completed', result={'answer': key})

    async def verify():
        await service.save_analysis('guest', run('first'))
        clock[0] = 5.0
        await service.save_term_chat('guest', run('second'))
        await service.save_analysis('other', run('other'))
        clock[0] = 10.0
        await service.save_analysis('new', run('new'))
        items, ttl = await service.list_analyses('guest')
        assert [item['run_id'] for item in items] == ['second', 'first']
        assert ttl == 5
        assert (await service.list_analyses('other'))[0][0]['run_id'] == 'other'
        clock[0] = 15.0
        await service.save_analysis('guest', run('fresh'))
        assert [item['run_id'] for item in (await service.list_analyses('guest'))[0]] == ['fresh']

    asyncio.run(verify())
