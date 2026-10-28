"""Small, time-based log rotation shared by the Raspberry Pi services."""

import glob
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import sys
import time


MAX_LOG_AGE_SECONDS = 24 * 60 * 60


def log_uncaught_exception(exception_type, exception, traceback):
    """Keep uncaught Python errors in the same rotating application log."""
    logging.getLogger().critical(
        "Uncaught Python exception",
        exc_info=(exception_type, exception, traceback),
    )


class RetentionTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Rotate hourly and remove application log files older than 24 hours."""

    def __init__(self, filename):
        if os.path.exists(filename) and os.path.getmtime(filename) < time.time() - MAX_LOG_AGE_SECONDS:
            os.remove(filename)
        super().__init__(
            filename,
            when="H",
            interval=1,
            backupCount=23,
            utc=True,
            encoding="utf-8",
        )
        self.remove_expired_logs()

    def remove_expired_logs(self):
        cutoff = time.time() - MAX_LOG_AGE_SECONDS
        for filename in glob.glob(self.baseFilename + ".*"):
            try:
                if os.path.getmtime(filename) < cutoff:
                    os.remove(filename)
            except FileNotFoundError:
                pass

    def doRollover(self):
        super().doRollover()
        self.remove_expired_logs()


def configure_app_logging(app_name):
    """Log to a 24-hour rotating file under systemd, or stdout when run manually."""
    log_directory = os.environ.get("APP_LOG_DIR")
    if log_directory:
        os.makedirs(log_directory, exist_ok=True)
        handler = RetentionTimedRotatingFileHandler(
            os.path.join(log_directory, f"{app_name}.log")
        )
    else:
        handler = logging.StreamHandler()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[handler],
        force=True,
    )
    sys.excepthook = log_uncaught_exception
