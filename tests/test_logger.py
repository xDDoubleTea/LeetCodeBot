import logging
import logging.handlers

import pytest

import config.logger
from config.constants import PERF_LOG_FILE_NAME, PERF_LOGGER_NAME
from config.logger import setup_logger
from utils import perf

LOGGERS_TOUCHED = ("", "sqlalchemy.engine", PERF_LOGGER_NAME)


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """Run setup_logger into tmp_path, then remove every handler it added."""
    monkeypatch.setattr(config.logger, "LOG_DIR", str(tmp_path))
    before = {name: list(logging.getLogger(name).handlers) for name in LOGGERS_TOUCHED}
    levels = {name: logging.getLogger(name).level for name in LOGGERS_TOUCHED}
    propagate = logging.getLogger("sqlalchemy.engine").propagate

    setup_logger(logging.INFO)
    logging.getLogger(PERF_LOGGER_NAME).setLevel(logging.INFO)
    yield tmp_path

    for name in LOGGERS_TOUCHED:
        target = logging.getLogger(name)
        for handler in target.handlers[:]:
            if handler not in before[name]:
                target.removeHandler(handler)
                handler.close()
        target.setLevel(levels[name])
    logging.getLogger("sqlalchemy.engine").propagate = propagate


def perf_handlers() -> list[logging.Handler]:
    return [
        handler
        for handler in logging.getLogger(PERF_LOGGER_NAME).handlers
        if isinstance(handler, logging.FileHandler)
        and handler.baseFilename.endswith(PERF_LOG_FILE_NAME)
    ]


class TestPerfLog:
    """setup_logger keeps latency lines in their own file."""

    def test_perf_module_logs_through_the_perf_logger(self):
        assert perf.logger.name == PERF_LOGGER_NAME

    def test_latency_line_is_written_to_perf_log(self, log_dir):
        perf.logger.info(perf.format_latency("problem", 12.3, 45.6))

        content = (log_dir / PERF_LOG_FILE_NAME).read_text(encoding="utf-8")

        assert "latency command=problem handler_ms=12.3 e2e_ms=45.6" in content

    def test_other_loggers_stay_out_of_perf_log(self, log_dir):
        logging.getLogger("cogs.leetcode").warning("not a latency line")

        content = (log_dir / PERF_LOG_FILE_NAME).read_text(encoding="utf-8")

        assert "not a latency line" not in content

    def test_perf_log_never_rotates(self, log_dir):
        handlers = perf_handlers()

        assert len(handlers) == 1
        assert not isinstance(handlers[0], logging.handlers.BaseRotatingHandler)
