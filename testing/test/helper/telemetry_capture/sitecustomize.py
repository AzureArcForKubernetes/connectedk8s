# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
"""Capture Azure CLI telemetry locally without starting the uploader."""

import importlib
import os

capture_dir = os.getenv("AZURE_CLI_TELEMETRY_CAPTURE_DIR")
if capture_dir:
    try:
        telemetry = importlib.import_module("azure.cli.telemetry")
        save_payload = importlib.import_module("azure.cli.telemetry.util").save_payload
    except ModuleNotFoundError:
        pass
    else:

        def capture_telemetry(_config_dir, payload):
            save_payload(capture_dir, payload)

        telemetry.save = capture_telemetry
