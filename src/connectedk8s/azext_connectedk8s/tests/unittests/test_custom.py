# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
import os
import sys
from types import SimpleNamespace
from typing import Dict, Optional
from unittest.mock import MagicMock

import pytest
from azure.cli.core.azclierror import AzCLIError, FileOperationError, ValidationError
from kubernetes.client.exceptions import ApiException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from kubernetes.client.models import (
    V1Node,
    V1NodeList,
    V1NodeSpec,
    V1ObjectMeta,
)

from azext_connectedk8s import custom
from azext_connectedk8s.custom import (
    _get_kubernetes_client_locations,
    _telemetry_catch_all,
    expand_proxy_skip_range_keywords,
    get_kubernetes_distro,
    get_kubernetes_infra,
)


def test_get_kubernetes_client_locations_preserves_az_cli_error(monkeypatch):
    expected = custom.AzCLIError("[AZK8S0515] HelmClientError")
    monkeypatch.setattr(
        custom,
        "get_kubectl_client_location",
        MagicMock(return_value="/usr/bin/kubectl"),
    )
    monkeypatch.setattr(
        custom, "get_helm_client_location", MagicMock(side_effect=expected)
    )

    with pytest.raises(custom.AzCLIError) as raised:
        _get_kubernetes_client_locations(MagicMock(), "AzureCloud")

    assert raised.value is expected


def test_telemetry_catch_all_uses_keyword_cmd(monkeypatch):
    class ReportedError(Exception):
        pass

    cmd = MagicMock()
    cmd.cli_ctx = MagicMock()
    report_error = MagicMock(return_value=ReportedError("reported"))
    monkeypatch.setattr(custom.utils, "report_connectedk8s_error", report_error)

    @_telemetry_catch_all
    def command(*, cmd):
        raise RuntimeError("failed")

    with pytest.raises(ReportedError):
        command(cmd=cmd)

    assert report_error.call_args.args[0] is cmd


def _cmd_without_arm_id():
    return SimpleNamespace(cli_ctx=SimpleNamespace(data={}))


def _assert_standardized_telemetry(mock_telemetry, error, user_fault):
    _, properties = mock_telemetry.add_extension_event.call_args.args
    assert properties["Context.Default.AzureCLI.errorCode"] == error.code
    assert properties["Context.Default.AzureCLI.errorName"] == error.name
    assert properties["Context.Default.AzureCLI.errorFaultType"] == error.fault_type
    assert (
        mock_telemetry.set_exception.call_args.kwargs["summary"]
        == properties["Context.Default.AzureCLI.errorMessage"]
    )
    mock_telemetry.add_extension_event.assert_called_once()
    mock_telemetry.set_exception.assert_called_once()
    if user_fault:
        mock_telemetry.set_user_fault.assert_called_once_with()
    else:
        mock_telemetry.set_user_fault.assert_not_called()


@pytest.mark.parametrize("operation", ["create", "update"])
def test_agent_state_timeout_reports_real_standardized_error(monkeypatch, operation):
    mock_telemetry = MagicMock()
    monkeypatch.setattr(custom.utils, "telemetry", mock_telemetry)

    error = custom._agent_state_timeout_error(_cmd_without_arm_id(), operation)

    assert isinstance(error, custom.CLIInternalError)
    assert str(error).startswith("[AZK8S0506] AgentStateTimeout:")
    assert f"during {operation}" in str(error)
    _assert_standardized_telemetry(
        mock_telemetry, custom.errors.AGENT_STATE_TIMEOUT, False
    )


def test_key_pair_generation_reports_real_standardized_error(monkeypatch):
    monkeypatch.setattr(
        custom.RSA,
        "generate",
        MagicMock(side_effect=RuntimeError("key generation failed")),
    )
    mock_telemetry = MagicMock()
    monkeypatch.setattr(custom.utils, "telemetry", mock_telemetry)

    with pytest.raises(custom.CLIInternalError) as raised:
        custom._generate_key_pair(_cmd_without_arm_id())

    assert str(raised.value).startswith("[AZK8S0507] KeyPairGenerationFailed:")
    assert "key generation failed" in str(raised.value)
    _assert_standardized_telemetry(
        mock_telemetry, custom.errors.KEY_PAIR_GENERATION_FAILED, False
    )


def test_cleanup_stale_arc_agents_passes_aligned_arguments(monkeypatch):
    cmd = _cmd_without_arm_id()
    cleanup_crds = MagicMock()
    delete_agents = MagicMock()
    monkeypatch.setattr(custom, "crd_cleanup_force_delete", cleanup_crds)
    monkeypatch.setattr(custom.utils, "delete_arc_agents", delete_agents)

    custom._cleanup_stale_arc_agents(
        cmd,
        "/usr/bin/kubectl",
        "/tmp/kubeconfig",
        "context",
        "azure-arc",
        "/usr/bin/helm",
        True,
    )

    cleanup_crds.assert_called_once_with(
        cmd, "/usr/bin/kubectl", "/tmp/kubeconfig", "context"
    )
    delete_agents.assert_called_once_with(
        "azure-arc",
        "/tmp/kubeconfig",
        "context",
        "/usr/bin/helm",
        True,
        True,
        cmd=cmd,
    )


def test_validate_release_namespace_reports_real_standardized_error(monkeypatch):
    monkeypatch.setattr(
        custom.utils, "get_release_namespace", MagicMock(return_value=None)
    )
    mock_telemetry = MagicMock()
    monkeypatch.setattr(custom.utils, "telemetry", mock_telemetry)

    with pytest.raises(custom.ClientRequestError) as raised:
        custom.validate_release_namespace(
            _cmd_without_arm_id(),
            MagicMock(),
            "cluster",
            "resource-group",
            None,
            None,
            "/usr/bin/helm",
        )

    assert str(raised.value).startswith("[AZK8S0508] ReleaseNamespaceNotFound:")
    assert "has not been onboarded" in str(raised.value)
    _assert_standardized_telemetry(
        mock_telemetry, custom.errors.RELEASE_NAMESPACE_NOT_FOUND, True
    )


@pytest.mark.parametrize(
    "helm_error, expected_user_fault",
    [("Error: values failed", False), ("Error: forbidden", True)],
)
def test_get_all_helm_values_reports_real_standardized_error(
    monkeypatch, helm_error, expected_user_fault
):
    process = MagicMock(returncode=1)
    process.communicate.return_value = (b"", helm_error.encode("ascii"))
    monkeypatch.setattr(custom, "Popen", MagicMock(return_value=process))
    mock_telemetry = MagicMock()
    monkeypatch.setattr(custom.utils, "telemetry", mock_telemetry)

    with pytest.raises(custom.CLIInternalError) as raised:
        custom.get_all_helm_values(
            _cmd_without_arm_id(), "azure-arc", None, None, "/usr/bin/helm"
        )

    assert str(raised.value).startswith("[AZK8S0509] HelmValuesGetFailed:")
    assert helm_error in str(raised.value)
    _assert_standardized_telemetry(
        mock_telemetry,
        custom.errors.HELM_VALUES_GET_FAILED,
        expected_user_fault,
    )


def test_validate_cluster_connect_disable_preserves_helm_values_error(monkeypatch):
    expected = custom.CLIInternalError("[AZK8S0509] HelmValuesGetFailed")
    monkeypatch.setattr(custom, "get_all_helm_values", MagicMock(side_effect=expected))

    with pytest.raises(custom.CLIInternalError) as raised:
        custom._validate_cluster_connect_disable(
            _cmd_without_arm_id(),
            "azure-arc",
            None,
            None,
            "/usr/bin/helm",
            False,
        )

    assert raised.value is expected


def test_get_helm_client_location_reports_real_agc_not_installed_error(
    monkeypatch,
):
    monkeypatch.setattr(custom.shutil, "which", MagicMock(return_value=None))
    mock_telemetry = MagicMock()
    monkeypatch.setattr(custom.utils, "telemetry", mock_telemetry)

    with pytest.raises(custom.CLIInternalError) as raised:
        custom.get_helm_client_location(_cmd_without_arm_id(), azure_cloud="ussec")

    assert str(raised.value).startswith("[AZK8S0510] HelmNotInstalled:")
    assert "AGC environment" in str(raised.value)
    _assert_standardized_telemetry(
        mock_telemetry, custom.errors.HELM_NOT_INSTALLED, True
    )


def test_load_kube_config_forwards_command_context(monkeypatch):
    cmd = MagicMock()
    expected = ValidationError("reported")
    report_error = MagicMock(return_value=expected)
    monkeypatch.setattr(
        custom.config,
        "load_kube_config",
        MagicMock(side_effect=RuntimeError("invalid kubeconfig")),
    )
    monkeypatch.setattr(custom.utils, "report_connectedk8s_error", report_error)

    with pytest.raises(ValidationError) as raised:
        custom.load_kube_config(None, None, False, cmd=cmd)

    assert raised.value is expected
    assert report_error.call_args.args[0] is cmd
    assert report_error.call_args.kwargs["user_fault"] is True
    assert report_error.call_args.kwargs["details"] == "invalid kubeconfig"


def test_check_kube_connection_forwards_command_context(monkeypatch):
    cmd = MagicMock()
    api_instance = MagicMock()
    api_instance.get_code.side_effect = RuntimeError("cluster unreachable")
    exception_handler = MagicMock(side_effect=ValidationError("reported"))
    monkeypatch.setattr(
        custom.kube_client, "VersionApi", MagicMock(return_value=api_instance)
    )
    monkeypatch.setattr(custom.utils, "kubernetes_exception_handler", exception_handler)

    with pytest.raises(ValidationError):
        custom.check_kube_connection(cmd=cmd)

    assert exception_handler.call_args.kwargs["cmd"] is cmd


def test_private_key_injection_forwards_command_context(monkeypatch):
    cmd = MagicMock()
    api_instance = MagicMock()
    api_instance.create_namespaced_secret.side_effect = ApiException(status=403)
    exception_handler = MagicMock(side_effect=ValidationError("reported"))
    monkeypatch.setattr(
        custom.utils,
        "ensure_arc_namespace_with_helm_metadata",
        MagicMock(),
    )
    monkeypatch.setattr(
        custom.utils.kube_client,
        "CoreV1Api",
        MagicMock(return_value=api_instance),
    )
    monkeypatch.setattr(custom.utils, "kubernetes_exception_handler", exception_handler)

    with pytest.raises(ValidationError):
        custom.utils.inject_onboarding_private_key_secret("private-key", cmd=cmd)

    assert exception_handler.call_args.kwargs["cmd"] is cmd


def test_namespace_cleanup_transient_lookup_failure_is_not_reported(monkeypatch):
    cmd = MagicMock()
    api_instance = MagicMock()
    api_instance.list_namespace.side_effect = [
        RuntimeError("cluster unreachable"),
        MagicMock(items=[]),
    ]
    exception_handler = MagicMock()
    sleep = MagicMock()
    monkeypatch.setattr(
        custom.utils.kube_client,
        "CoreV1Api",
        MagicMock(return_value=api_instance),
    )
    monkeypatch.setattr(custom.utils, "kubernetes_exception_handler", exception_handler)
    monkeypatch.setattr(custom.utils.time, "sleep", sleep)

    custom.utils.ensure_namespace_cleanup(cmd)

    exception_handler.assert_not_called()
    sleep.assert_not_called()


def test_namespace_cleanup_reports_persistent_lookup_failure_without_raising(
    monkeypatch,
):
    cmd = MagicMock()
    lookup_error = RuntimeError("cluster unreachable")
    api_instance = MagicMock()
    api_instance.list_namespace.side_effect = lookup_error
    exception_handler = MagicMock()
    monkeypatch.setattr(
        custom.utils.kube_client,
        "CoreV1Api",
        MagicMock(return_value=api_instance),
    )
    monkeypatch.setattr(custom.utils, "kubernetes_exception_handler", exception_handler)
    monkeypatch.setattr(custom.utils.time, "sleep", MagicMock())
    monkeypatch.setattr(
        custom.utils.time,
        "time",
        MagicMock(side_effect=[0, 0, 181, 181]),
    )

    custom.utils.ensure_namespace_cleanup(cmd)

    exception_handler.assert_called_once()
    assert exception_handler.call_args.args[0] is lookup_error
    assert exception_handler.call_args.kwargs["raise_error"] is False
    assert exception_handler.call_args.kwargs["cmd"] is cmd


@pytest.fixture
def onboarding_access_context(monkeypatch):
    cmd = MagicMock()
    cmd.cli_ctx.data = {}
    cmd.cli_ctx.cloud.endpoints.resource_manager = "https://management.azure.com"
    telemetry = MagicMock()
    monkeypatch.setattr(custom, "telemetry", telemetry)
    monkeypatch.setattr(custom.utils, "telemetry", telemetry)
    monkeypatch.setattr(custom.precheckutils, "telemetry", telemetry)
    for name, value in {
        "get_subscription_id": "subscription",
        "send_cloud_telemetry": "AzureCloud",
        "set_kube_config": "kubeconfig",
        "get_config_dp_endpoint": ("endpoint", "stable"),
        "get_kubectl_client_location": "kubectl",
        "get_helm_client_location": "helm",
    }.items():
        monkeypatch.setattr(custom, name, MagicMock(return_value=value))
    for name, value in {
        "validate_custom_token": (False, "eastus"),
        "check_provider_registrations": None,
        "get_values_file": None,
        "get_metadata": {},
    }.items():
        monkeypatch.setattr(custom.utils, name, MagicMock(return_value=value))
    monkeypatch.setattr(custom.config, "load_kube_config", MagicMock())
    version_api = MagicMock()
    version_api.get_code.return_value.git_version = "v1.30.0"
    monkeypatch.setattr(
        custom.kube_client, "VersionApi", MagicMock(return_value=version_api)
    )
    core_api = MagicMock()
    monkeypatch.setattr(
        custom.kube_client, "CoreV1Api", MagicMock(return_value=core_api)
    )
    permission = MagicMock(return_value=False)
    monkeypatch.setattr(custom.utils, "can_create_clusterrolebindings", permission)
    helm_install = MagicMock()
    monkeypatch.setattr(custom.utils, "helm_install_release", helm_install)
    return SimpleNamespace(
        cmd=cmd,
        telemetry=telemetry,
        core_api=core_api,
        permission=permission,
        helm_install=helm_install,
        version_api=version_api,
    )


@pytest.mark.parametrize("node_os", ["linux", "windows"])
@pytest.mark.parametrize("permission", [False, "Unknown"])
def test_onboarding_permission_failure_emits_one_fault(
    onboarding_access_context, node_os, permission
):
    ctx = onboarding_access_context
    ctx.core_api.list_node.return_value = V1NodeList(
        items=[create_node(labels={"kubernetes.io/os": node_os})]
    )
    ctx.permission.return_value = permission

    with pytest.raises(ValidationError, match="ClusterRoleBindingCreateForbidden"):
        custom.create_connectedk8s(
            ctx.cmd,
            MagicMock(),
            "rg",
            "cluster",
            infrastructure="azure_stack_hci",
            distribution="aks_edge_k3s",
        )

    ctx.telemetry.set_exception.assert_called_once()
    fault = ctx.telemetry.set_exception.call_args.kwargs
    assert (
        fault["fault_type"]
        == custom.consts.Cannot_Create_ClusterRoleBindings_Fault_Type
    )
    ctx.permission.assert_called_once()
    ctx.helm_install.assert_not_called()
    properties = ctx.telemetry.add_extension_event.call_args.args[1]
    assert properties[custom.consts.Telemetry_Error_Code_Key] == (
        custom.errors.CLUSTER_ROLE_BINDING_CREATE_FORBIDDEN.code
    )
    assert properties[
        custom.consts.Connected_Cluster_Arm_Id_Telemetry_Property
    ].endswith("/connectedClusters/cluster")
    warning_events = [
        call.args[1]
        for call in ctx.telemetry.add_extension_event.call_args_list
        if custom.consts.Telemetry_Warning_Code_Key in call.args[1]
    ]
    assert len(warning_events) == (0 if node_os == "linux" else 1)


@pytest.mark.parametrize("failure_point", ["kubeconfig", "connectivity"])
def test_onboarding_cluster_access_failure_is_not_reported_twice(
    onboarding_access_context, monkeypatch, failure_point
):
    ctx = onboarding_access_context
    if failure_point == "kubeconfig":
        monkeypatch.setattr(
            custom.config,
            "load_kube_config",
            MagicMock(side_effect=RuntimeError("invalid kubeconfig")),
        )
    else:
        ctx.version_api.get_code.side_effect = ApiException(status=403)

    with pytest.raises(AzCLIError):
        custom.create_connectedk8s(ctx.cmd, MagicMock(), "rg", "cluster")

    ctx.telemetry.set_exception.assert_called_once()
    ctx.core_api.list_node.assert_not_called()
    ctx.permission.assert_not_called()
    ctx.helm_install.assert_not_called()
    properties = ctx.telemetry.add_extension_event.call_args.args[1]
    assert properties[custom.consts.Telemetry_Error_Exception_Type_Key] == (
        "RuntimeError" if failure_point == "kubeconfig" else "ApiException"
    )
    if failure_point == "connectivity":
        assert properties[custom.consts.Telemetry_Error_Http_Status_Code_Key] == 403


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_private_key_failure_retains_status_and_emits_one_fault(monkeypatch, status):
    cmd = SimpleNamespace(cli_ctx=SimpleNamespace(data={}))
    telemetry = MagicMock()
    monkeypatch.setattr(custom.utils, "telemetry", telemetry)
    monkeypatch.setattr(custom, "telemetry", telemetry)
    monkeypatch.setattr(
        custom.utils, "ensure_arc_namespace_with_helm_metadata", MagicMock()
    )
    api = MagicMock()
    api.create_namespaced_secret.side_effect = ApiException(status=status)
    monkeypatch.setattr(
        custom.utils.kube_client, "CoreV1Api", MagicMock(return_value=api)
    )

    @_telemetry_catch_all
    def inject(cmd):
        custom.utils.inject_onboarding_private_key_secret("private-key", cmd=cmd)

    with pytest.raises(AzCLIError):
        inject(cmd)

    telemetry.set_exception.assert_called_once()
    properties = telemetry.add_extension_event.call_args.args[1]
    assert properties[custom.consts.Telemetry_Error_Http_Status_Code_Key] == status
    assert (
        properties[custom.consts.Telemetry_Error_Exception_Type_Key] == "ApiException"
    )
    assert properties[custom.consts.Telemetry_Error_Fault_Type_Key] == (
        custom.errors.KUBERNETES_PRIVATE_KEY_INJECTION_FAILED.fault_type
    )
    api.replace_namespaced_secret.assert_not_called()


@pytest.mark.parametrize("check", ["aks", "proxy"])
def test_kubeconfig_lookup_error_keeps_command_context(monkeypatch, check):
    arm_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Kubernetes/connectedClusters/cluster"
    cmd = SimpleNamespace(
        cli_ctx=SimpleNamespace(
            data={custom.consts.Connected_Cluster_Arm_Id_Telemetry_Context_Key: arm_id}
        )
    )
    telemetry = MagicMock()
    monkeypatch.setattr(custom.utils, "telemetry", telemetry)
    monkeypatch.setattr(
        custom,
        "KubeConfigMerger",
        MagicMock(side_effect=RuntimeError("invalid kubeconfig")),
    )
    with pytest.raises(FileOperationError):
        if check == "aks":
            custom.check_aks_cluster("kubeconfig", None, cmd=cmd)
        else:
            custom.check_proxy_kubeconfig("kubeconfig", None, "hash", cmd=cmd)

    telemetry.set_exception.assert_called_once()
    properties = telemetry.add_extension_event.call_args.args[1]
    assert (
        properties[custom.consts.Connected_Cluster_Arm_Id_Telemetry_Property] == arm_id
    )


def create_node(
    provider_id: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None,
    annotations: Optional[Dict[str, str]] = None,
) -> V1Node:
    spec = V1NodeSpec(provider_id=provider_id)
    metadata = V1ObjectMeta(labels=labels or {}, annotations=annotations or {})
    return V1Node(spec=spec, metadata=metadata)


@pytest.mark.parametrize(
    "provider_id, expected",
    [
        ("k3s://node1", "k3s"),
        ("kind://node1", "kind"),
        ("azure://node1", "azure"),
        ("gce://node1", "gcp"),
        ("aws://node1", "aws"),
        ("unknown://node1", "unknown"),
        (None, "generic"),
    ],
)
def test_get_kubernetes_infra(provider_id, expected):
    node = create_node(provider_id) if provider_id is not None else None
    api_response = V1NodeList(items=[node]) if node else None
    assert get_kubernetes_infra(api_response) == expected


def test_empty_items():
    api_response = V1NodeList(items=[])
    assert get_kubernetes_infra(api_response) == "generic"


def test_invalid_provider_id():
    node = create_node(None)
    api_response = V1NodeList(items=[node])
    assert get_kubernetes_infra(api_response) == "None"


# --------------------- Tests for get_kubernetes_distro ---------------------
@pytest.mark.parametrize(
    "labels, annotations, provider_id, expected",
    [
        ({"node.openshift.io/os_id": "rhcos"}, {}, None, "openshift"),
        ({"kubernetes.azure.com/node-image-version": "2022.11.01"}, {}, None, "aks"),
        ({"cloud.google.com/gke-nodepool": "default-pool"}, {}, None, "gke"),
        ({"cloud.google.com/gke-os-distribution": "cos"}, {}, None, "gke"),
        ({"eks.amazonaws.com/nodegroup": "nodegroup-1"}, {}, None, "eks"),
        ({"minikube.k8s.io/version": "v1.25.0"}, {}, None, "minikube"),
        ({}, {"node.aksedge.io/distro": "aks_edge_k3s"}, None, "aks_edge_k3s"),
        ({}, {"node.aksedge.io/distro": "aks_edge_k8s"}, None, "aks_edge_k8s"),
        ({}, {}, "kind://node1", "kind"),
        ({}, {}, "k3s://node1", "k3s"),
        ({}, {"rke.cattle.io/external-ip": "192.168.1.1"}, None, "rancher_rke"),
        ({}, {"rke.cattle.io/internal-ip": "10.0.0.1"}, None, "rancher_rke"),
        ({}, {}, None, "generic"),
    ],
)
def test_get_kubernetes_distro(labels, annotations, provider_id, expected):
    node = create_node(provider_id=provider_id, labels=labels, annotations=annotations)
    api_response = V1NodeList(items=[node])
    assert get_kubernetes_distro(api_response) == expected


def test_distro_empty_items():
    api_response = V1NodeList(items=[])
    assert get_kubernetes_distro(api_response) == "generic"


def test_distro_invalid_metadata():
    node = create_node(provider_id="aws://node1", labels=None, annotations=None)
    api_response = V1NodeList(items=[node])
    assert get_kubernetes_distro(api_response) == "generic"


# --------------------- Tests for expand_proxy_skip_range_keywords ---------------------
def _proxy_cmd(active_directory="https://login.microsoftonline.com"):
    cmd = MagicMock()
    cmd.cli_ctx.cloud.endpoints.active_directory = active_directory
    return cmd


ARC_PUBLIC = (
    ".his.arc.azure.com,"
    ".dp.kubernetesconfiguration.azure.com,"
    ".guestconfiguration.azure.com"
)


def test_expand_arc_keyword_public_cloud():
    assert expand_proxy_skip_range_keywords(_proxy_cmd(), "Arc") == ARC_PUBLIC


@pytest.mark.parametrize("keyword", ["Arc", "arc", "ARC", " aRc "])
def test_expand_arc_keyword_is_case_and_space_insensitive(keyword):
    assert expand_proxy_skip_range_keywords(_proxy_cmd(), keyword) == ARC_PUBLIC


def test_expand_arc_keyword_preserves_other_entries():
    out = expand_proxy_skip_range_keywords(_proxy_cmd(), "Arc,10.0.0.0/16,.svc")
    assert out == ARC_PUBLIC + ",10.0.0.0/16,.svc"


def test_expand_arc_keyword_china_cloud():
    cmd = _proxy_cmd("https://login.chinacloudapi.cn")
    out = expand_proxy_skip_range_keywords(cmd, "Arc")
    assert out == (
        ".his.arc.azure.cn,"
        ".dp.kubernetesconfiguration.azure.cn,"
        ".guestconfiguration.azure.cn"
    )


def test_expand_arc_keyword_usgov_cloud():
    cmd = _proxy_cmd("https://login.microsoftonline.us")
    out = expand_proxy_skip_range_keywords(cmd, "Arc")
    assert out == (
        ".his.arc.azure.us,"
        ".dp.kubernetesconfiguration.azure.us,"
        ".guestconfiguration.azure.us"
    )


def test_expand_arc_keyword_ussec_cloud():
    cmd = _proxy_cmd("https://login.microsoftonline.microsoft.scloud")
    out = expand_proxy_skip_range_keywords(cmd, "Arc")
    assert out == (
        ".his.arc.azure.microsoft.scloud,"
        ".dp.kubernetesconfiguration.azure.microsoft.scloud,"
        ".guestconfiguration.azure.microsoft.scloud"
    )


def test_expand_arc_keyword_usnat_cloud():
    cmd = _proxy_cmd("https://login.microsoftonline.eaglex.ic.gov")
    out = expand_proxy_skip_range_keywords(cmd, "Arc")
    assert out == (
        ".his.arc.azure.eaglex.ic.gov,"
        ".dp.kubernetesconfiguration.azure.eaglex.ic.gov,"
        ".guestconfiguration.azure.eaglex.ic.gov"
    )


def test_expand_no_keyword_returns_unchanged():
    val = "10.0.0.0/16,.svc,localhost"
    assert expand_proxy_skip_range_keywords(_proxy_cmd(), val) == val


def test_expand_empty_returns_unchanged():
    assert expand_proxy_skip_range_keywords(_proxy_cmd(), "") == ""


def test_expand_arc_keyword_deduplicates():
    out = expand_proxy_skip_range_keywords(_proxy_cmd(), "Arc,Arc")
    assert out == ARC_PUBLIC


def test_expand_arc_keyword_dedups_case_insensitive_endpoint():
    # A user endpoint differing only in case is not duplicated in NO_PROXY.
    out = expand_proxy_skip_range_keywords(_proxy_cmd(), "Arc, .his.ARC.azure.com")
    assert out == ARC_PUBLIC
