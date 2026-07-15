# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
"""Shared pytest configuration for connectedk8s unit tests.

Centralises sys.modules stubbing so every test file sees a consistent set of
mock dependencies regardless of collection order.  Previously each test file
performed its own stubbing at module-import time, which caused flaky failures
when pytest discovered files in a different order: whichever file was imported
first would win the sys.modules race, leaving later files with stale or
conflicting stubs.

The ``_install_stubs`` session-scoped fixture runs exactly once per test
process, before any test module is imported, and restores the originals at
session teardown.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest


def _make_package_mock():
    """Create a MagicMock that Python's import system treats as a package.

    Ordinary MagicMock lacks ``__path__`` as a real list, so
    ``import pkg.sub`` fails with "'pkg' is not a package".
    Setting ``__path__ = []`` tells the importer "I'm a package, but
    don't search the filesystem for sub-modules" — sub-module lookups
    fall through to ``sys.modules`` where our stubs live.
    """
    m = MagicMock()
    m.__path__ = []
    return m


# ---------------------------------------------------------------------------
# Comprehensive stub list — union of all stubs the four test files need.
# Covers external dependencies that may not be installed in lightweight
# test environments.  Internal azext_connectedk8s modules are NOT stubbed
# here — individual test files handle those as needed.
# ---------------------------------------------------------------------------
_STUBS = {
    # kubernetes
    "kubernetes": _make_package_mock(),
    "kubernetes.config": _make_package_mock(),
    "kubernetes.config.kube_config": _make_package_mock(),
    "kubernetes.watch": _make_package_mock(),
    "kubernetes.client": _make_package_mock(),
    "kubernetes.client.models": _make_package_mock(),
    "kubernetes.client.rest": _make_package_mock(),
    "kubernetes.utils": _make_package_mock(),
    # azure SDK / CLI — core
    "azure": _make_package_mock(),
    "azure.cli": _make_package_mock(),
    "azure.cli.core": _make_package_mock(),
    "azure.cli.core._config": _make_package_mock(),
    "azure.cli.core._profile": _make_package_mock(),
    "azure.cli.core.azclierror": _make_package_mock(),
    "azure.cli.core.commands": _make_package_mock(),
    "azure.cli.core.commands.client_factory": _make_package_mock(),
    "azure.cli.core.commands.parameters": _make_package_mock(),
    "azure.cli.core.commands.validators": _make_package_mock(),
    "azure.cli.core.profiles": _make_package_mock(),
    "azure.cli.core.style": _make_package_mock(),
    "azure.cli.core.telemetry": _make_package_mock(),
    "azure.cli.core.util": _make_package_mock(),
    # azure.cli.command_modules (used by custom.py)
    "azure.cli.command_modules": _make_package_mock(),
    "azure.cli.command_modules.role": _make_package_mock(),
    # azure.cli.testsdk
    "azure.cli.testsdk": _make_package_mock(),
    # azure SDK — deep paths needed by vendored_sdks
    "azure.core": _make_package_mock(),
    "azure.core.async_paging": _make_package_mock(),
    "azure.core.configuration": _make_package_mock(),
    "azure.core.exceptions": _make_package_mock(),
    "azure.core.paging": _make_package_mock(),
    "azure.core.pipeline": _make_package_mock(),
    "azure.core.pipeline.policies": _make_package_mock(),
    "azure.core.pipeline.transport": _make_package_mock(),
    "azure.core.polling": _make_package_mock(),
    "azure.core.rest": _make_package_mock(),
    "azure.core.serialization": _make_package_mock(),
    "azure.core.settings": _make_package_mock(),
    "azure.core.tracing": _make_package_mock(),
    "azure.core.tracing.decorator": _make_package_mock(),
    "azure.core.tracing.decorator_async": _make_package_mock(),
    "azure.core.utils": _make_package_mock(),
    "azure.mgmt": _make_package_mock(),
    "azure.mgmt.core": _make_package_mock(),
    "azure.mgmt.core.exceptions": _make_package_mock(),
    "azure.mgmt.core.policies": _make_package_mock(),
    "azure.mgmt.core.polling": _make_package_mock(),
    "azure.mgmt.core.polling.arm_polling": _make_package_mock(),
    "azure.mgmt.core.tools": _make_package_mock(),
    # msrest
    "msrest": _make_package_mock(),
    "msrest.exceptions": _make_package_mock(),
    "msrest.serialization": _make_package_mock(),
    "msrestazure": _make_package_mock(),
    # knack
    "knack": _make_package_mock(),
    "knack.log": _make_package_mock(),
    "knack.help_files": _make_package_mock(),
    "knack.util": _make_package_mock(),
    "knack.cli": _make_package_mock(),
    "knack.config": _make_package_mock(),
    "knack.prompting": _make_package_mock(),
    "knack.commands": _make_package_mock(),
    "knack.arguments": _make_package_mock(),
    "knack.events": _make_package_mock(),
    # Third-party libraries that may not be installed
    "oras": _make_package_mock(),
    "oras.client": _make_package_mock(),
    "yaml": _make_package_mock(),
    "Crypto": _make_package_mock(),
    "Crypto.IO": _make_package_mock(),
    "Crypto.IO.PEM": _make_package_mock(),
    "Crypto.PublicKey": _make_package_mock(),
    "Crypto.PublicKey.RSA": _make_package_mock(),
    "Crypto.Util": _make_package_mock(),
    "Crypto.Util.asn1": _make_package_mock(),
    "packaging": _make_package_mock(),
    "packaging.version": _make_package_mock(),
    "psutil": _make_package_mock(),
    "requests": _make_package_mock(),
    # sibling modules that have heavy transitive imports
    "azext_connectedk8s._client_factory": _make_package_mock(),
}

# Track originals so we can restore at teardown
_originals: dict[str, object | None] = {}


def _install():
    """Insert stubs into sys.modules (only for modules not already importable).

    Unlike a plain ``setdefault``, we *attempt* a real import first.
    This ensures that installed packages (e.g. ``kubernetes`` in a full
    azdev venv) are used as-is, while missing ones get a MagicMock stub.
    """
    for mod, stub in _STUBS.items():
        if mod in sys.modules:
            continue  # already loaded — leave it
        try:
            __import__(mod)
        except Exception:
            sys.modules[mod] = stub
            _originals[mod] = None  # remember to remove at teardown
        else:
            _originals[mod] = sys.modules[mod]  # remember original

    # Ensure the package path is importable
    pkg_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)


def _uninstall():
    """Restore sys.modules to its pre-stub state."""
    for mod, original in _originals.items():
        if original is None:
            sys.modules.pop(mod, None)
        else:
            sys.modules[mod] = original
    _originals.clear()


# ---------------------------------------------------------------------------
# Session-scoped fixture — runs once before any test, tears down at the end.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _install_stubs():
    """Install module stubs for the entire test session."""
    _install()
    yield
    _uninstall()


# ---------------------------------------------------------------------------
# Force subprocess-level isolation when pytest-xdist is used.
# Each worker gets its own module cache, eliminating cross-worker races.
# ---------------------------------------------------------------------------
def pytest_configure(config):
    """Ensure test isolation by installing stubs early (before collection)."""
    _install()
