# conftest.py — E6 Red Teamer security test configuration
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow security tests (50-request DoS probe)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (run with --run-slow)"
    )
