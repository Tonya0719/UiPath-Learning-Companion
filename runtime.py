"""Per-request experiment mode and audit trace."""
from contextvars import ContextVar
from contextlib import contextmanager
import time
variant = ContextVar('variant', default='C')
trace = ContextVar('trace', default=None)
progress = ContextVar('progress', default=None)
started = ContextVar('started', default=None)

def record(kind, **details):
    event = {'kind': kind, **details}
    if started.get() is not None:
        event['elapsed_seconds'] = round(time.perf_counter() - started.get(), 3)
    if trace.get() is not None:
        trace.get().append(event)
    if progress.get() is not None:
        progress.get()(event)

@contextmanager
def observe(callback=None):
    a, b = progress.set(callback), started.set(time.perf_counter())
    try:
        yield
    finally:
        progress.reset(a)
        started.reset(b)

@contextmanager
def experiment(mode='C'):
    if mode not in {'A', 'B', 'C'}:
        raise ValueError('Unknown experiment variant')
    events = []
    a, b = variant.set(mode), trace.set(events)
    try:
        yield events
    finally:
        variant.reset(a)
        trace.reset(b)
