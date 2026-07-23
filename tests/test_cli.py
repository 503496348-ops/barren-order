"""Tests for barren-order CLI entry point."""
import subprocess
import sys
import os

SCRIPTS = os.path.join(os.path.dirname(__file__), '..', 'scripts')


def test_help():
    """CLI --help should exit 0."""
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, 'cli.py'), '--help'],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0
    assert 'barren-order' in r.stdout.lower()


def test_info():
    """CLI info should return JSON."""
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, 'cli.py')],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0
    assert 'workflow' in r.stdout.lower()
