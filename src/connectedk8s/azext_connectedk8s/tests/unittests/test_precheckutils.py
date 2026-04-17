# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
"""Unit tests for prediagnostic telemetry functions in _precheckutils.py."""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

# Stub out heavy dependencies before importing the module under test.
# Use setdefault so real modules are preferred when available (e.g. in azdev CI),
# but stubs are used in lightweight environments without full CLI installed.
_STUBS = {
    "kubernetes": MagicMock(),
    "kubernetes.config": MagicMock(),
    "kubernetes.watch": MagicMock(),
    "kubernetes.client": MagicMock(),
    "kubernetes.client.models": MagicMock(),
    "azure": MagicMock(),
    "azure.cli": MagicMock(),
    "azure.cli.core": MagicMock(),
    "azure.cli.core.telemetry": MagicMock(),
    "azure.cli.core.azclierror": MagicMock(),
    "azure.cli.core.commands": MagicMock(),
    "azure.cli.core.commands.client_factory": MagicMock(),
    "azure.cli.core.util": MagicMock(),
    "azure.cli.core._config": MagicMock(),
    "azure.core": MagicMock(),
    "azure.core.exceptions": MagicMock(),
    "azure.mgmt": MagicMock(),
    "azure.mgmt.core": MagicMock(),
    "azure.mgmt.core.tools": MagicMock(),
    "msrest": MagicMock(),
    "msrestazure": MagicMock(),
    "knack": MagicMock(),
    "knack.log": MagicMock(),
    "knack.help_files": MagicMock(),
    "knack.util": MagicMock(),
    "knack.cli": MagicMock(),
    "knack.config": MagicMock(),
    "knack.prompting": MagicMock(),
    "knack.commands": MagicMock(),
    "knack.arguments": MagicMock(),
    "knack.events": MagicMock(),
    # Stub the sibling module to avoid its transitive imports
    "azext_connectedk8s._utils": MagicMock(),
}
for mod, stub in _STUBS.items():
    sys.modules.setdefault(mod, stub)

# Make process_helm_error_detail a transparent passthrough so telemetry message assertions work
sys.modules["azext_connectedk8s._utils"].process_helm_error_detail = lambda x: x

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import azext_connectedk8s._constants as consts  # noqa: E402
import azext_connectedk8s._precheckutils as precheckutils  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_globals():
    """Reset module-level globals to a clean state before each test."""
    precheckutils.diagnoser_output = []
    precheckutils.prediagnostic_job_execution_status = "NotStarted"
    precheckutils.prediagnostic_entra_check = "Starting"
    precheckutils.prediagnostic_crd_check = "Starting"


# ---------------------------------------------------------------------------
# send_prediagnostic_job_execution_error_telemetry
# ---------------------------------------------------------------------------

class TestSendJobExecutionErrorTelemetry:
    def setup_method(self):
        _reset_globals()

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_sends_event_with_correct_error_type(self, mock_telemetry):
        precheckutils.prediagnostic_job_execution_status = "ExecutionFailed"
        precheckutils.send_prediagnostic_job_execution_error_telemetry()

        mock_telemetry.add_extension_event.assert_called_once()
        args = mock_telemetry.add_extension_event.call_args
        assert args[0][0] == "connectedk8s"
        props = args[0][1]
        assert props["Context.Default.AzureCLI.onboardingErrorType"] == consts.Install_Prediagnostics_Job_Execution_Error_Fault_Type

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_message_includes_job_execution_status(self, mock_telemetry):
        precheckutils.prediagnostic_job_execution_status = "ExecutionFailed"
        precheckutils.send_prediagnostic_job_execution_error_telemetry()

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert msg["jobExecutionStatus"] == "ExecutionFailed"

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_message_includes_reason_when_provided(self, mock_telemetry):
        precheckutils.prediagnostic_job_execution_status = "NotCompleted"
        precheckutils.send_prediagnostic_job_execution_error_telemetry(reason="ImagePullBackOff")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert msg["reason"] == "ImagePullBackOff"

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_message_omits_reason_when_empty(self, mock_telemetry):
        precheckutils.send_prediagnostic_job_execution_error_telemetry()

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert "reason" not in msg

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_message_is_valid_json(self, mock_telemetry):
        precheckutils.send_prediagnostic_job_execution_error_telemetry(reason="ContainerCreating")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert isinstance(msg, dict)


# ---------------------------------------------------------------------------
# send_prediagnostic_check_failure_telemetry
# ---------------------------------------------------------------------------

class TestSendCheckFailureTelemetry:
    def setup_method(self):
        _reset_globals()

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_sends_event_with_correct_error_type(self, mock_telemetry):
        precheckutils.send_prediagnostic_check_failure_telemetry("Passed", "Passed")

        mock_telemetry.add_extension_event.assert_called_once()
        props = mock_telemetry.add_extension_event.call_args[0][1]
        assert props["Context.Default.AzureCLI.onboardingErrorType"] == consts.Install_Prediagnostics_Fault_Type

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_check_results_in_message(self, mock_telemetry):
        precheckutils.prediagnostic_entra_check = "Failed"
        precheckutils.prediagnostic_crd_check = "Passed"
        precheckutils.send_prediagnostic_check_failure_telemetry("Passed", "Failed")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert msg["dnsCheck"] == "Passed"
        assert msg["outboundConnectivityCheck"] == "Failed"
        assert msg["entraCheck"] == "Failed"
        assert msg["crdCheck"] == "Passed"

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_entra_error_extracted_from_diagnoser_output(self, mock_telemetry):
        precheckutils.prediagnostic_entra_check = "Failed"
        precheckutils.diagnoser_output = [
            "Some log line",
            "Error: Entra endpoint not reachable. Response code: 000",
        ]
        precheckutils.send_prediagnostic_check_failure_telemetry("Passed", "Passed")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert "entraError" in msg
        assert "000" in msg["entraError"]

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_dns_error_extracted_from_diagnoser_output(self, mock_telemetry):
        precheckutils.diagnoser_output = [
            "DNS error: resolution failed for test.example.com",
        ]
        precheckutils.send_prediagnostic_check_failure_telemetry("Failed", "Passed")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert "dnsError" in msg

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_outbound_error_extracted_from_diagnoser_output(self, mock_telemetry):
        precheckutils.diagnoser_output = [
            "Outbound connectivity error: MCR not reachable",
        ]
        precheckutils.send_prediagnostic_check_failure_telemetry("Passed", "Failed")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert "outboundError" in msg

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_multiline_error_trimmed_to_first_line(self, mock_telemetry):
        precheckutils.prediagnostic_entra_check = "Failed"
        precheckutils.diagnoser_output = [
            "Error: Entra endpoint error line1\nline2\nline3",
        ]
        precheckutils.send_prediagnostic_check_failure_telemetry("Passed", "Passed")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert "\n" not in msg.get("entraError", "")
        assert "line1" in msg.get("entraError", "")

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_no_error_detail_when_checks_pass(self, mock_telemetry):
        precheckutils.prediagnostic_entra_check = "Passed"
        precheckutils.prediagnostic_crd_check = "Passed"
        precheckutils.send_prediagnostic_check_failure_telemetry("Passed", "Passed")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert "dnsError" not in msg
        assert "entraError" not in msg
        assert "outboundError" not in msg
        assert "crdError" not in msg

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_non_error_lines_not_captured(self, mock_telemetry):
        """Lines mentioning entra but not 'error' should not be captured."""
        precheckutils.prediagnostic_entra_check = "Failed"
        precheckutils.diagnoser_output = [
            "Entra check: starting",
            "Entra Authentication Endpoint Connectivity Check Result : https://login.microsoftonline.com : 000",
        ]
        precheckutils.send_prediagnostic_check_failure_telemetry("Passed", "Passed")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert "entraError" not in msg

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_crd_error_extracted_from_diagnoser_output(self, mock_telemetry):
        precheckutils.prediagnostic_crd_check = "Failed"
        precheckutils.diagnoser_output = [
            "CRD ownership error: extensionconfigs.clusterconfig.azure.com owned by another release",
        ]
        precheckutils.send_prediagnostic_check_failure_telemetry("Passed", "Passed")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert "crdError" in msg


# ---------------------------------------------------------------------------
# send_post_diagnostic_precheck_failure_telemetry
# ---------------------------------------------------------------------------

class TestSendPostDiagnosticPrecheckFailureTelemetry:
    def setup_method(self):
        _reset_globals()

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_sends_event_with_correct_error_type(self, mock_telemetry):
        precheckutils.send_post_diagnostic_precheck_failure_telemetry("LinuxNodeExists", "No Linux nodes found")

        mock_telemetry.add_extension_event.assert_called_once()
        props = mock_telemetry.add_extension_event.call_args[0][1]
        assert props["Context.Default.AzureCLI.onboardingErrorType"] == consts.Post_Diagnostic_Precheck_Fault_Type

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_message_includes_check_name_and_reason(self, mock_telemetry):
        precheckutils.send_post_diagnostic_precheck_failure_telemetry("ClusterRoleBindings", "Insufficient permissions")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert msg["checkName"] == "ClusterRoleBindings"
        assert msg["reason"] == "Insufficient permissions"

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_message_is_valid_json(self, mock_telemetry):
        precheckutils.send_post_diagnostic_precheck_failure_telemetry("SomeCheck", "Some reason")

        props = mock_telemetry.add_extension_event.call_args[0][1]
        msg = json.loads(props["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert isinstance(msg, dict)

    @patch("azext_connectedk8s._precheckutils.telemetry")
    def test_different_check_names_produce_separate_events(self, mock_telemetry):
        precheckutils.send_post_diagnostic_precheck_failure_telemetry("LinuxNodeExists", "No nodes")
        precheckutils.send_post_diagnostic_precheck_failure_telemetry("ClusterRoleBindings", "No perms")

        assert mock_telemetry.add_extension_event.call_count == 2
        calls = mock_telemetry.add_extension_event.call_args_list
        msg1 = json.loads(calls[0][0][1]["Context.Default.AzureCLI.onboardingErrorMessage"])
        msg2 = json.loads(calls[1][0][1]["Context.Default.AzureCLI.onboardingErrorMessage"])
        assert msg1["checkName"] == "LinuxNodeExists"
        assert msg2["checkName"] == "ClusterRoleBindings"
