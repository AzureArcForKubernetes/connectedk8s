# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
"""Lightweight command dispatch that reports connectedk8s import failures."""

from __future__ import annotations

from typing import Any

from azure.cli.core import telemetry
from knack.log import get_logger

import azext_connectedk8s._constants as consts
import azext_connectedk8s._errors as errors

logger = get_logger(__name__)

_REINSTALL_DETAILS = (
    "Reinstall the connectedk8s extension and retry the command. "
    "If the problem continues, contact support with this module name."
)


def _invoke(command_name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        from azext_connectedk8s import custom
    except ModuleNotFoundError as ex:
        module_name = ex.name or "unknown"
        message = errors.MISSING_PYTHON_MODULE.format(
            module_name=module_name,
            details=_REINSTALL_DETAILS,
        )
        properties = {
            consts.Telemetry_Error_Code_Key: errors.MISSING_PYTHON_MODULE.code,
            consts.Telemetry_Error_Fault_Type_Key: (
                errors.MISSING_PYTHON_MODULE.fault_type
            ),
            consts.Telemetry_Error_Name_Key: errors.MISSING_PYTHON_MODULE.name,
            consts.Telemetry_Error_Message_Key: message,
            consts.Telemetry_Error_Exception_Type_Key: type(ex).__name__,
            consts.Telemetry_Error_Missing_Module_Key: module_name,
        }
        logger.exception(
            "Failed to load connectedk8s command '%s': "
            "Python module '%s' was not found.",
            command_name,
            module_name,
        )
        telemetry.add_extension_event("connectedk8s", properties)
        telemetry.set_exception(
            exception=ex,
            fault_type=errors.MISSING_PYTHON_MODULE.fault_type,
            summary=message,
        )
        raise errors.MISSING_PYTHON_MODULE.as_error(
            module_name=module_name,
            details=_REINSTALL_DETAILS,
        ) from ex

    return getattr(custom, command_name)(*args, **kwargs)


def create_connectedk8s(*args: Any, **kwargs: Any) -> Any:
    return _invoke("create_connectedk8s", *args, **kwargs)


def update_connected_cluster(*args: Any, **kwargs: Any) -> Any:
    return _invoke("update_connected_cluster", *args, **kwargs)


def upgrade_agents(*args: Any, **kwargs: Any) -> Any:
    return _invoke("upgrade_agents", *args, **kwargs)


def delete_connectedk8s(*args: Any, **kwargs: Any) -> Any:
    return _invoke("delete_connectedk8s", *args, **kwargs)


def enable_features(*args: Any, **kwargs: Any) -> Any:
    return _invoke("enable_features", *args, **kwargs)


def disable_features(*args: Any, **kwargs: Any) -> Any:
    return _invoke("disable_features", *args, **kwargs)


def list_connectedk8s(*args: Any, **kwargs: Any) -> Any:
    return _invoke("list_connectedk8s", *args, **kwargs)


def get_connectedk8s(*args: Any, **kwargs: Any) -> Any:
    return _invoke("get_connectedk8s", *args, **kwargs)


def client_side_proxy_wrapper(*args: Any, **kwargs: Any) -> Any:
    return _invoke("client_side_proxy_wrapper", *args, **kwargs)


def troubleshoot(*args: Any, **kwargs: Any) -> Any:
    return _invoke("troubleshoot", *args, **kwargs)
