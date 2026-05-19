# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
from __future__ import annotations

from typing import TYPE_CHECKING

from azure.cli.core import AzCommandsLoader

from azext_connectedk8s._help import helps


def _patch_urllib3_getheaders_compat() -> None:
    """
    Restore ``urllib3.response.HTTPResponse.getheaders`` if the urllib3 that
    az core loads is v2.x and dropped the method. The kubernetes python client
    (through at least 29.x) still calls ``http_resp.getheaders()`` inside
    ``ApiException.__init__``, so without this shim any non-2xx Kubernetes API
    response (e.g. a 404 on ``read_namespace('azure-arc')`` during onboarding)
    crashes with ``AttributeError: 'HTTPResponse' object has no attribute
    'getheaders'``.

    We can't fix this by pinning urllib3 in setup.py: az core's site-packages
    appears earlier on sys.path than the extension's bundled copy, so az's
    urllib3 always wins. The patch is idempotent and a no-op when getheaders
    already exists.
    """
    try:
        from urllib3.response import HTTPResponse
    except Exception:  # pylint: disable=broad-except
        return
    if hasattr(HTTPResponse, "getheaders"):
        return

    def getheaders(self):  # type: ignore[no-untyped-def]
        return self.headers

    HTTPResponse.getheaders = getheaders  # type: ignore[attr-defined,method-assign]


_patch_urllib3_getheaders_compat()

if TYPE_CHECKING:
    from azure.cli.core import AzCli
    from knack.commands import CLICommand


class Connectedk8sCommandsLoader(AzCommandsLoader):  # type: ignore[misc]
    def __init__(self, cli_ctx: AzCli | None = None) -> None:
        from azure.cli.core.commands import CliCommandType

        from azext_connectedk8s._client_factory import cf_connectedk8s

        connectedk8s_custom = CliCommandType(
            operations_tmpl="azext_connectedk8s.custom#{}",
            client_factory=cf_connectedk8s,
        )
        super().__init__(cli_ctx=cli_ctx, custom_command_type=connectedk8s_custom)

    def load_command_table(self, args: list[str] | None) -> dict[str, CLICommand]:
        from azext_connectedk8s.commands import load_command_table

        load_command_table(self, args)
        command_table: dict[str, CLICommand] = self.command_table
        return command_table

    def load_arguments(self, command: CLICommand) -> None:
        from azext_connectedk8s._params import load_arguments

        load_arguments(self, command)


COMMAND_LOADER_CLS = Connectedk8sCommandsLoader

__all__ = [
    "COMMAND_LOADER_CLS",
    "Connectedk8sCommandsLoader",
    "helps",
]
