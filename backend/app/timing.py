# app/timing.py
from time import perf_counter
from functools import wraps
from contextlib import contextmanager
from .logging_utils import setup_logger, log_kv

def timeit(stage: str):
    """
    Decorator to time a function call and log start/end + elapsed_ms
    to logs/ingestion.log under the shared 'ingestion' logger.
    Usage:
        @timeit("parse-pages")
        def parse_pages(...): ...
    """
    def _decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kwargs):
            log = setup_logger("ingestion")
            log_kv(log, event="start", stage=stage)
            start = perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                elapsed_ms = int((perf_counter() - start) * 1000)
                log_kv(log, event="end", stage=stage, elapsed_ms=elapsed_ms)
        return _wrapped
    return _decorator

@contextmanager
def timed_block(stage: str):
    """
    Context manager for ad-hoc blocks:
        with timed_block("chunk-toc"):
            ... do work ...
    """
    log = setup_logger("ingestion")
    log_kv(log, event="start", stage=stage)
    start = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = int((perf_counter() - start) * 1000)
        log_kv(log, event="end", stage=stage, elapsed_ms=elapsed_ms)
