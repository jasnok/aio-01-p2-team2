"""Process-local admission slots, including requests awaiting Redis reservation."""
from backend.app.core.config import get_settings


class RunCapacityError(RuntimeError):
    pass


class RunSlot:
    def __init__(self, capacity):
        self.capacity = capacity
        self.released = False

    def release(self):
        if not self.released:
            self.released = True
            self.capacity.used -= 1


class RunCapacity:
    def __init__(self):
        self.used = 0

    def acquire(self) -> RunSlot:
        # No await: admission is atomic within the API event loop.
        if self.used >= get_settings().agent_run_max_concurrency:
            raise RunCapacityError("Analysis capacity exhausted")
        self.used += 1
        return RunSlot(self)


run_capacity = RunCapacity()
