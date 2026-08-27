# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from azext_connectedk8s import _constants as consts
from azext_connectedk8s import _troubleshootutils as troubleshootutils


def _failed_helm_process(error: bytes) -> MagicMock:
    process = MagicMock()
    process.returncode = 1
    process.communicate.return_value = (b"", error)
    return process


def test_executing_diagnoser_job_records_helm_failure_without_raising(monkeypatch):
    monkeypatch.setattr(
        troubleshootutils,
        "Popen",
        MagicMock(return_value=_failed_helm_process(b"Error: forbidden")),
    )
    mock_telemetry = MagicMock()
    monkeypatch.setattr(troubleshootutils.azext_utils, "telemetry", mock_telemetry)
    troubleshootutils.diagnoser_output.clear()

    result = troubleshootutils.executing_diagnoser_job(
        MagicMock(),
        MagicMock(),
        "diagnostics.txt",
        True,
        "/tmp",
        "helm",
        "kubectl",
        "azure-arc",
        consts.Diagnostic_Check_Passed,
        None,
        None,
    )

    assert result is None
    assert len(troubleshootutils.diagnoser_output) == 1
    message = troubleshootutils.diagnoser_output[0]
    assert message.startswith("[AZK8S0509] HelmValuesGetFailed:")
    assert "Error: forbidden" in message
    _, properties = mock_telemetry.add_extension_event.call_args.args
    assert properties["Context.Default.AzureCLI.errorCode"] == "AZK8S0509"
    assert properties["Context.Default.AzureCLI.errorName"] == "HelmValuesGetFailed"
    assert properties["Context.Default.AzureCLI.errorMessage"] == message.rstrip()
    assert mock_telemetry.set_exception.call_args.kwargs["summary"] == message.rstrip()
    mock_telemetry.set_user_fault.assert_called_once_with()


def test_security_policy_check_records_helm_failure_without_overwriting(
    monkeypatch,
):
    monkeypatch.setattr(
        troubleshootutils,
        "Popen",
        MagicMock(
            return_value=_failed_helm_process(
                b"Error: timed out waiting for the condition"
            )
        ),
    )
    mock_telemetry = MagicMock()
    monkeypatch.setattr(troubleshootutils.azext_utils, "telemetry", mock_telemetry)
    troubleshootutils.diagnoser_output.clear()

    result = troubleshootutils.check_probable_cluster_security_policy(
        MagicMock(),
        "helm",
        "azure-arc",
        None,
        None,
    )

    assert result == consts.Diagnostic_Check_Incomplete
    assert len(troubleshootutils.diagnoser_output) == 1
    message = troubleshootutils.diagnoser_output[0]
    assert message.startswith("[AZK8S0509] HelmValuesGetFailed:")
    assert "timed out waiting for the condition" in message
    _, properties = mock_telemetry.add_extension_event.call_args.args
    assert properties["Context.Default.AzureCLI.errorCode"] == "AZK8S0509"
    assert properties["Context.Default.AzureCLI.errorMessage"] == message.rstrip()
    assert mock_telemetry.set_exception.call_args.kwargs["summary"] == message.rstrip()
    mock_telemetry.set_user_fault.assert_called_once_with()
