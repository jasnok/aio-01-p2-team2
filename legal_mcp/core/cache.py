"""Process-local TTL/LRU cache with coalesced concurrent cold requests."""
from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from threading import Lock
from time import monotonic


class QueryCache:
    def __init__(self, max_entries=128, clock=monotonic):
        self.max_entries, self.clock = max_entries, clock
        self.values, self.pending = OrderedDict(), {}
        self.lock = Lock()

    def clear(self):
        with self.lock:
            self.values.clear()

    def get_or_load(self, key, loader, ttl):
        if ttl <= 0:
            return loader()
        with self.lock:
            entry = self.values.get(key)
            if entry and entry[0] > self.clock():
                self.values.move_to_end(key)
                return deepcopy(entry[1])
            future = self.pending.get(key)
            owner = future is None
            if owner:
                future = self.pending[key] = Future()
        if not owner:
            return deepcopy(future.result())
        try:
            value = loader()
            with self.lock:
                self.values[key] = (self.clock() + ttl, deepcopy(value))
                self.values.move_to_end(key)
                while len(self.values) > self.max_entries:
                    self.values.popitem(last=False)
            future.set_result(deepcopy(value))
            return deepcopy(value)
        except BaseException as error:
            future.set_exception(error)
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)
