# app/logging_utils.py
import os
import logging
from pathlib import Path

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

def setup_logger(name: str) -> logging.Logger:
    """
    Create or return a logger that writes to logs/<name>.log using env settings:
      LOG_DIR (default 'logs'), LOG_LEVEL (default 'INFO'), LOG_FORMAT ('plain' or 'json')
    """
    log_dir = os.getenv("LOG_DIR", "logs")
    log_level = _LEVELS.get(os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "plain").lower()

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logfile = Path(log_dir) / f"{name}.log"

    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    logger.propagate = False  # avoid duplicate lines from root

    # If handler already attached (hot-reload), don't add another
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "_app_logfile", None) == str(logfile) for h in logger.handlers):
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh._app_logfile = str(logfile)  # mark for dedup

        if log_format == "json":
            # Minimal JSON lines; easy to expand later
            fmt = '{"t":"%(asctime)s","lv":"%(levelname)s","lg":"%(name)s","msg":"%(message)s"}'
        else:
            fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

        fh.setFormatter(logging.Formatter(fmt))
        fh.setLevel(log_level)
        logger.addHandler(fh)

    return logger

def log_kv(logger: logging.Logger, **kv):
    """
    Convenience: logs a single line with key=val pairs.
    Example: log_kv(log, stage="parse-pages", doc_id=1, elapsed_ms=1234)
    """
    parts = [f"{k}={v}" for k, v in kv.items()]
    logger.info(" ".join(parts))
