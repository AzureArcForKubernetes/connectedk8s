# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
import os
import sys
from contextlib import ExitStack
from typing import Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
from azure.cli.core.azclierror import (
    AzCLIError,
    MutuallyExclusiveArgumentError,
    ValidationError,
)
from kubernetes.client.models import (
    V1ConfigMap,
    V1Node,
    V1NodeList,
    V1NodeSpec,
    V1ObjectMeta,
)
from kubernetes.client.rest import ApiException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from azext_connectedk8s._constants import (
    CI_ConfigMap_Error_Message,
    CI_ConfigMap_Proxy_Bypass_Annotation,
    CI_ConfigMap_Removal_Error_Message,
    Diagnostic_Check_Passed,
)
from azext_connectedk8s._containerinsightsutils import (
    container_insights_bypass_requested,
    create_container_insights_proxy_bypass_configmap,
    ensure_container_insights_proxy_bypass_configmap,
    merge_proxy_bypass_into_agent_settings,
    remove_container_insights_proxy_bypass_configmap,
    remove_proxy_bypass_from_agent_settings,
    sync_container_insights_proxy_bypass_configmap,
)
from azext_connectedk8s.custom import (
    add_config_protected_settings,
    create_connectedk8s,
    delete_connectedk8s,
    expand_proxy_skip_range_keywords,
    get_kubernetes_distro,
    get_kubernetes_infra,
    update_connected_cluster,
)


def create_node(
    provider_id: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None,
    annotations: Optional[Dict[str, str]] = None,
) -> V1Node:
    spec = V1NodeSpec(provider_id=provider_id)
    metadata = V1ObjectMeta(labels=labels or {}, annotations=annotations or {})
    return V1Node(spec=spec, metadata=metadata)


class _StopUpdate(AzCLIError):
    """Raised by tests to stop update_connected_cluster once the values are captured.

    Subclasses AzCLIError so the telemetry decorator re-raises it untouched.
    """


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


@pytest.mark.parametrize(
    "no_proxy, expected",
    [
        # The Arc keyword is case- and space-insensitive.
        ("Arc", ARC_PUBLIC),
        ("arc", ARC_PUBLIC),
        ("ARC", ARC_PUBLIC),
        (" aRc ", ARC_PUBLIC),
        # Repeats, and endpoints differing only in case, are not duplicated.
        ("Arc,Arc", ARC_PUBLIC),
        ("Arc, .his.ARC.azure.com", ARC_PUBLIC),
        # Other entries survive alongside the expansion.
        ("Arc,10.0.0.0/16,.svc", ARC_PUBLIC + ",10.0.0.0/16,.svc"),
        # Container Insights is applied through a ConfigMap, so it drops out of NO_PROXY.
        ("Microsoft.AzureMonitor.Containers", ""),
        ("microsoft.azuremonitor.containers", ""),
        ("MICROSOFT.AZUREMONITOR.CONTAINERS", ""),
        (" Microsoft.AzureMonitor.Containers ", ""),
        ("Microsoft.AzureMonitor.Containers,10.0.0.0/16,.svc", "10.0.0.0/16,.svc"),
        ("Arc,Microsoft.AzureMonitor.Containers,10.0.0.0/16", ARC_PUBLIC + ",10.0.0.0/16"),
        # A value carrying no keyword passes through untouched.
        ("10.0.0.0/16,.svc,localhost", "10.0.0.0/16,.svc,localhost"),
        ("", ""),
    ],
)
def test_expand_proxy_skip_range_keywords(no_proxy, expected):
    assert expand_proxy_skip_range_keywords(_proxy_cmd(), no_proxy) == expected


@pytest.mark.parametrize(
    "active_directory, expected",
    [
        ("https://login.microsoftonline.com", ARC_PUBLIC),
        (
            "https://login.chinacloudapi.cn",
            ".his.arc.azure.cn,"
            ".dp.kubernetesconfiguration.azure.cn,"
            ".guestconfiguration.azure.cn",
        ),
        (
            "https://login.microsoftonline.us",
            ".his.arc.azure.us,"
            ".dp.kubernetesconfiguration.azure.us,"
            ".guestconfiguration.azure.us",
        ),
        (
            "https://login.microsoftonline.microsoft.scloud",
            ".his.arc.azure.microsoft.scloud,"
            ".dp.kubernetesconfiguration.azure.microsoft.scloud,"
            ".guestconfiguration.azure.microsoft.scloud",
        ),
        (
            "https://login.microsoftonline.eaglex.ic.gov",
            ".his.arc.azure.eaglex.ic.gov,"
            ".dp.kubernetesconfiguration.azure.eaglex.ic.gov,"
            ".guestconfiguration.azure.eaglex.ic.gov",
        ),
    ],
)
def test_expand_arc_keyword_per_cloud(active_directory, expected):
    # The Arc endpoints follow each cloud's own domain, taken from its AAD login endpoint.
    assert (
        expand_proxy_skip_range_keywords(_proxy_cmd(active_directory), "Arc") == expected
    )


# ------------- Tests for detecting the Container Insights keyword -------------
@pytest.mark.parametrize(
    "no_proxy, expected",
    [
        ("Microsoft.AzureMonitor.Containers", True),
        ("10.0.0.0/16,Microsoft.AzureMonitor.Containers", True),
        ("Arc, microsoft.azuremonitor.containers ", True),
        ("MICROSOFT.AZUREMONITOR.CONTAINERS", True),
        ("", False),
        (None, False),
        ("Arc", False),
        ("10.0.0.0/16,.svc", False),
    ],
)
def test_container_insights_bypass_requested(no_proxy, expected):
    assert container_insights_bypass_requested(no_proxy) is expected


# ------------- Tests for merging the proxy bypass into an existing ConfigMap -------------
_BYPASS_SETTING = 'ignore_proxy_settings = "true"'
_ALREADY_BYPASSING = f"[agent_settings.proxy_config]\n    {_BYPASS_SETTING}"


@pytest.mark.parametrize(
    "agent_settings, expected",
    [
        # An absent or empty agent-settings gets a fresh, active proxy_config block.
        ("", _ALREADY_BYPASSING),
        # Already bypassing: returned unchanged, so no needless ConfigMap write happens.
        (_ALREADY_BYPASSING, _ALREADY_BYPASSING),
        # An explicit "false" is flipped in place rather than duplicated.
        (
            '[agent_settings.proxy_config]\n    ignore_proxy_settings = "false"',
            _ALREADY_BYPASSING,
        ),
        # A header with nothing under it gets the setting, without a second header.
        ("[agent_settings.proxy_config]\n", _ALREADY_BYPASSING),
        # Unrelated sections are preserved and the bypass is appended.
        (
            "[agent_settings.high_log_scale]\n  enabled = false\n",
            f"[agent_settings.high_log_scale]\n  enabled = false\n{_ALREADY_BYPASSING}",
        ),
        # The commented-out template shipped by Container Insights is not an active
        # setting, so it is left in place and a real one is added.
        (
            "# [agent_settings.proxy_config]\n"
            '#    ignore_proxy_settings = "true"  # if this is not applied, default value is false\n',
            "# [agent_settings.proxy_config]\n"
            '#    ignore_proxy_settings = "true"  # if this is not applied, default value is false\n'
            f"{_ALREADY_BYPASSING}",
        ),
        # The setting only counts under proxy_config, so a same-named one in another
        # section is left alone and a proper section is added instead.
        (
            '[agent_settings.some_other]\n    ignore_proxy_settings = "false"',
            '[agent_settings.some_other]\n    ignore_proxy_settings = "false"\n'
            f"{_ALREADY_BYPASSING}",
        ),
        # With both sections present, only the one under proxy_config is flipped.
        (
            '[agent_settings.some_other]\n    ignore_proxy_settings = "false"\n'
            '[agent_settings.proxy_config]\n    ignore_proxy_settings = "false"',
            '[agent_settings.some_other]\n    ignore_proxy_settings = "false"\n'
            f"{_ALREADY_BYPASSING}",
        ),
    ],
)
def test_merge_proxy_bypass_into_agent_settings(agent_settings, expected):
    assert merge_proxy_bypass_into_agent_settings(agent_settings) == expected


# --------- Tests for the ensure/create ConfigMap kube-client interaction ---------
_CIUTILS = "azext_connectedk8s._containerinsightsutils"
_UNRELATED = "[agent_settings.high_log_scale]\n  enabled = false\n"


def _configmap(agent_settings, stamped=False):
    # V1ConfigMap stand-in that carries (or deliberately lacks) the ownership annotation.
    annotations = {CI_ConfigMap_Proxy_Bypass_Annotation: "azure-cli"} if stamped else {}
    return V1ConfigMap(
        data={"agent-settings": agent_settings},
        metadata=V1ObjectMeta(annotations=annotations),
    )


def _written_body(api):
    # The ConfigMap handed back to the cluster, whichever write call was used.
    write = (
        api.replace_namespaced_config_map
        if api.replace_namespaced_config_map.called
        else api.create_namespaced_config_map
    )
    return write.call_args.kwargs["body"]


def _stamp_of(body):
    return body.metadata.annotations.get(CI_ConfigMap_Proxy_Bypass_Annotation)


def test_ensure_creates_a_stamped_configmap_when_absent():
    # A 404 on read means the ConfigMap is absent, so a fresh one is created and stamped.
    api = MagicMock()
    api.read_namespaced_config_map.side_effect = ApiException(status=404)

    ensure_container_insights_proxy_bypass_configmap(api)

    api.replace_namespaced_config_map.assert_not_called()
    body = _written_body(api)
    assert _BYPASS_SETTING in body.data["agent-settings"]
    assert _stamp_of(body) == "azure-cli"


def test_ensure_merges_into_an_existing_configmap_and_stamps_it():
    # An existing ConfigMap is updated in place, keeping unrelated agent settings.
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _configmap(_UNRELATED)

    ensure_container_insights_proxy_bypass_configmap(api)

    api.create_namespaced_config_map.assert_not_called()
    body = _written_body(api)
    assert "[agent_settings.high_log_scale]" in body.data["agent-settings"]
    assert _BYPASS_SETTING in body.data["agent-settings"]
    assert _stamp_of(body) == "azure-cli"


def test_ensure_is_noop_when_the_configmap_already_bypasses():
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _configmap(_ALREADY_BYPASSING)

    ensure_container_insights_proxy_bypass_configmap(api)

    api.replace_namespaced_config_map.assert_not_called()
    api.create_namespaced_config_map.assert_not_called()


def test_create_falls_back_to_merge_on_conflict():
    # A 409 on create means the ConfigMap appeared concurrently; fall back to merge.
    api = MagicMock()
    api.create_namespaced_config_map.side_effect = ApiException(status=409)

    with patch(
        f"{_CIUTILS}.ensure_container_insights_proxy_bypass_configmap"
    ) as mock_ensure:
        create_container_insights_proxy_bypass_configmap(api)

    mock_ensure.assert_called_once_with(api)


# --------- Tests for removing the setting this CLI added ---------


@pytest.mark.parametrize(
    "agent_settings, expected",
    [
        # The block added by this CLI goes away completely, header included.
        (_ALREADY_BYPASSING, ""),
        # A header that carries other settings stays behind.
        (
            f"[agent_settings.proxy_config]\n    keep_me = 1\n    {_BYPASS_SETTING}",
            "[agent_settings.proxy_config]\n    keep_me = 1",
        ),
        # An unrelated section before the proxy_config block is untouched.
        (
            f"[agent_settings.high_log_scale]\n  enabled = false\n{_ALREADY_BYPASSING}",
            "[agent_settings.high_log_scale]\n  enabled = false",
        ),
        # An unrelated section after it survives the header removal.
        (
            f"{_ALREADY_BYPASSING}\n[agent_settings.high_log_scale]\n  enabled = false",
            "[agent_settings.high_log_scale]\n  enabled = false",
        ),
        # Nothing to remove.
        (
            "[agent_settings.high_log_scale]\n  enabled = false",
            "[agent_settings.high_log_scale]\n  enabled = false",
        ),
        # Commented-out settings are not active, so they are left alone.
        (
            f"[agent_settings.proxy_config]\n#    {_BYPASS_SETTING}",
            f"[agent_settings.proxy_config]\n#    {_BYPASS_SETTING}",
        ),
        # A same-named setting in another section is not a proxy bypass, so it survives.
        (
            '[agent_settings.some_other]\n    ignore_proxy_settings = "false"',
            '[agent_settings.some_other]\n    ignore_proxy_settings = "false"',
        ),
        # Only the setting under proxy_config is removed.
        (
            '[agent_settings.some_other]\n    ignore_proxy_settings = "false"\n'
            f"{_ALREADY_BYPASSING}",
            '[agent_settings.some_other]\n    ignore_proxy_settings = "false"',
        ),
        ("", ""),
    ],
)
def test_remove_proxy_bypass_from_agent_settings(agent_settings, expected):
    assert remove_proxy_bypass_from_agent_settings(agent_settings) == expected


def test_remove_does_nothing_when_configmap_absent():
    # A 404 means there is no setting to remove, and the ConfigMap must never be created here.
    api = MagicMock()
    api.read_namespaced_config_map.side_effect = ApiException(status=404)

    remove_container_insights_proxy_bypass_configmap(api)

    api.create_namespaced_config_map.assert_not_called()
    api.replace_namespaced_config_map.assert_not_called()


def test_remove_strips_the_setting_and_the_stamp():
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _configmap(
        f"{_UNRELATED}{_ALREADY_BYPASSING}", stamped=True
    )

    remove_container_insights_proxy_bypass_configmap(api)

    body = api.replace_namespaced_config_map.call_args.kwargs["body"]
    # Unrelated settings survive; the bypass and the ownership stamp do not.
    assert body.data["agent-settings"] == _UNRELATED.rstrip("\n")
    assert CI_ConfigMap_Proxy_Bypass_Annotation not in body.metadata.annotations


def test_customer_owned_bypass_survives_a_later_removal():
    # A bypass the customer set themselves is never stamped by ensure(), so the annotation gate
    # in remove() leaves it alone. Neither call may write the ConfigMap back.
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _configmap(_ALREADY_BYPASSING)

    ensure_container_insights_proxy_bypass_configmap(api)
    remove_container_insights_proxy_bypass_configmap(api)

    api.replace_namespaced_config_map.assert_not_called()


# --------- Tests for the sync entry point that connect and update share ---------
@pytest.mark.parametrize(
    "requested, extra, remove_kwargs",
    [
        # The keyword was passed, so the bypass is applied.
        (True, {}, None),
        # It was not, so the bypass is removed - fatally by default, so a cluster is never
        # left bypassing the proxy after the user asked for that to stop.
        (False, {}, {"raise_on_failure": True}),
        # Fresh connect turns that off when no --proxy-skip-range was passed at all, so
        # cleanup nobody asked for cannot block onboarding.
        (False, {"raise_on_removal_failure": False}, {"raise_on_failure": False}),
    ],
)
def test_sync_dispatches_to_ensure_or_remove(requested, extra, remove_kwargs):
    api = MagicMock()
    with ExitStack() as stack:
        ensure = stack.enter_context(
            patch(f"{_CIUTILS}.ensure_container_insights_proxy_bypass_configmap")
        )
        remove = stack.enter_context(
            patch(f"{_CIUTILS}.remove_container_insights_proxy_bypass_configmap")
        )
        sync_container_insights_proxy_bypass_configmap(api, requested, **extra)

    if remove_kwargs is None:
        ensure.assert_called_once_with(api)
        remove.assert_not_called()
    else:
        ensure.assert_not_called()
        remove.assert_called_once_with(api, **remove_kwargs)


# --------- Tests for ConfigMap failures being fatal on connect and update ---------
@pytest.mark.parametrize(
    "func, failing_call, existing, expected_message",
    [
        # Anything other than a 404 on read is a real failure, so the command must stop.
        (
            ensure_container_insights_proxy_bypass_configmap,
            "read",
            "",
            CI_ConfigMap_Error_Message,
        ),
        (
            ensure_container_insights_proxy_bypass_configmap,
            "replace",
            "",
            CI_ConfigMap_Error_Message,
        ),
        # Anything other than a 409 on create is a real failure too.
        (
            create_container_insights_proxy_bypass_configmap,
            "create",
            "",
            CI_ConfigMap_Error_Message,
        ),
        # Removal names the action it failed at, so the error is not reported as a write.
        (
            remove_container_insights_proxy_bypass_configmap,
            "read",
            _ALREADY_BYPASSING,
            CI_ConfigMap_Removal_Error_Message,
        ),
        # A failure here would leave the cluster bypassing the proxy after the user
        # asked it to stop.
        (
            remove_container_insights_proxy_bypass_configmap,
            "replace",
            _ALREADY_BYPASSING,
            CI_ConfigMap_Removal_Error_Message,
        ),
    ],
)
def test_configmap_failures_stop_the_command(
    func, failing_call, existing, expected_message
):
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _configmap(existing, stamped=True)
    getattr(api, f"{failing_call}_namespaced_config_map").side_effect = ApiException(
        status=403
    )

    with pytest.raises(ValidationError) as raised:
        func(api)

    assert expected_message in str(raised.value)


@pytest.mark.parametrize("failing_call", ["read", "replace"])
def test_remove_only_reports_the_failure_when_delete_is_cleaning_up(failing_call):
    # Delete must still finish, so the failure is reported instead of raised.
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _configmap(
        _ALREADY_BYPASSING, stamped=True
    )
    getattr(api, f"{failing_call}_namespaced_config_map").side_effect = ApiException(
        status=403
    )

    remove_container_insights_proxy_bypass_configmap(api, raise_on_failure=False)


# --------------------- Tests for --disable-proxy conflict detection ---------------------
@pytest.mark.parametrize(
    "no_proxy",
    [
        "Microsoft.AzureMonitor.Containers",
        "microsoft.azuremonitor.containers",
        " Microsoft.AzureMonitor.Containers ",
        "10.0.0.0/24",
        "10.0.0.0/24,Microsoft.AzureMonitor.Containers",
    ],
)
def test_disable_proxy_conflicts_with_proxy_skip_range(no_proxy):
    # The Container Insights keyword expands to an empty no_proxy, so the conflict has to be
    # detected from the recorded request rather than from what survived the expansion.
    patches = [
        patch(
            "azext_connectedk8s.custom.send_cloud_telemetry", return_value="AzureCloud"
        ),
        patch("azext_connectedk8s.custom.set_kube_config", return_value=None),
        patch("azext_connectedk8s.custom.telemetry"),
    ]
    with ExitStack() as stack:
        for each in patches:
            stack.enter_context(each)

        with pytest.raises(MutuallyExclusiveArgumentError):
            update_connected_cluster(
                MagicMock(),
                MagicMock(),
                "resource-group",
                "cluster",
                no_proxy=no_proxy,
                disable_proxy=True,
            )


_SUBSCRIPTION_ID = "00000000-0000-0000-0000-000000000000"


def _delete_patches(release_namespace):
    # Shared scaffolding that drives delete_connectedk8s down to the ConfigMap step.
    return [
        patch(
            "azext_connectedk8s.custom.send_cloud_telemetry", return_value="AzureCloud"
        ),
        patch("azext_connectedk8s.custom.set_kube_config", return_value=None),
        patch("azext_connectedk8s.custom.load_kube_config"),
        patch("azext_connectedk8s.custom.check_kube_connection"),
        patch("azext_connectedk8s.custom.get_helm_client_location", return_value=""),
        patch("azext_connectedk8s.custom.get_kubectl_client_location", return_value=""),
        patch(
            "azext_connectedk8s.custom.utils.get_release_namespace",
            return_value=release_namespace,
        ),
        patch("azext_connectedk8s.custom.utils.validate_node_api_response"),
        patch("azext_connectedk8s.custom.check_arm64_node", return_value=False),
        patch(
            "azext_connectedk8s.custom.get_subscription_id",
            return_value=_SUBSCRIPTION_ID,
        ),
        patch("azext_connectedk8s.custom.check_proxy_kubeconfig", return_value=False),
    ]


def _run_delete(release_namespace=None, force_delete=False):
    # Returns a parent mock whose call order shows the bypass removal against the ARM delete.
    with ExitStack() as stack:
        for each in _delete_patches(release_namespace):
            stack.enter_context(each)
        core_api = stack.enter_context(
            patch("azext_connectedk8s.custom.kube_client.CoreV1Api")
        )
        # The identity check on the normal path reads 'azure-clusterconfig' and compares it
        # against the resource being deleted, so it has to match for that path to proceed.
        agent_configmap = MagicMock()
        agent_configmap.data = {
            "AZURE_RESOURCE_GROUP": "resource-group",
            "AZURE_RESOURCE_NAME": "cluster",
            "AZURE_SUBSCRIPTION_ID": _SUBSCRIPTION_ID,
        }
        core_api.return_value.read_namespaced_config_map.return_value = agent_configmap

        order = MagicMock()
        for target, name in (
            (
                f"{_CIUTILS}.remove_container_insights_proxy_bypass_configmap",
                "remove_bypass",
            ),
            ("azext_connectedk8s.custom.delete_cc_resource", "delete_cc_resource"),
            ("azext_connectedk8s.custom.crd_cleanup_force_delete", "crd_cleanup"),
            ("azext_connectedk8s.custom.utils.delete_arc_agents", "delete_agents"),
        ):
            order.attach_mock(stack.enter_context(patch(target)), name)

        delete_connectedk8s(
            MagicMock(),
            MagicMock(),
            "resource-group",
            "cluster",
            yes=True,
            force_delete=force_delete,
        )

    return order, core_api


@pytest.mark.parametrize(
    "release_namespace, force_delete, crd_cleaned, agents_deleted",
    [
        # No helm release: delete returns before any agent cleanup, so this is the last
        # chance to undo the bypass. It lives in kube-system, not in the azure-arc release.
        (None, False, False, False),
        # Force delete skips the identity check entirely, but must still undo it first.
        ("azure-arc", True, True, True),
        # The ordinary path, taken once the azure-clusterconfig identity check has passed.
        ("azure-arc", False, False, True),
    ],
)
def test_delete_removes_the_bypass_before_the_cluster_resource(
    release_namespace, force_delete, crd_cleaned, agents_deleted
):
    order, core_api = _run_delete(release_namespace, force_delete)

    # No raise_on_failure is passed, so a failure stops the command and the cluster resource is
    # left in place to retry against.
    order.remove_bypass.assert_called_once_with(core_api.return_value)

    # The bypass must go first: once the cluster resource is deleted, a retried delete stops at
    # the resource lookup and can never reach the removal again.
    call_order = [name for name, _, _ in order.mock_calls]
    assert call_order.index("remove_bypass") < call_order.index("delete_cc_resource")

    # Each row above leaves through a different branch of delete_connectedk8s.
    assert order.crd_cleanup.called is crd_cleaned
    assert order.delete_agents.called is agents_deleted


# --------- Test that a ConfigMap failure stops the command before the agents are touched ---------
def test_update_does_not_touch_the_agents_when_the_configmap_fails():
    # The whole point of doing the ConfigMap first is that a failure leaves nothing to clean up,
    # so helm must never run once the ConfigMap step has failed.
    connected_cluster = MagicMock()
    connected_cluster.id = (
        "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg"
        "/providers/Microsoft.Kubernetes/connectedClusters/cluster"
    )
    connected_cluster.agent_version = "1.0.0"
    client = MagicMock()
    client.get.return_value = connected_cluster

    patches = [
        patch(
            "azext_connectedk8s.custom.send_cloud_telemetry", return_value="AzureCloud"
        ),
        patch("azext_connectedk8s.custom.set_kube_config", return_value=None),
        patch("azext_connectedk8s.custom.telemetry"),
        patch("azext_connectedk8s.custom.load_kube_config"),
        patch("azext_connectedk8s.custom.check_kube_connection", return_value="v1.28.0"),
        patch("azext_connectedk8s.custom.get_helm_client_location", return_value=""),
        patch(
            "azext_connectedk8s.custom.validate_release_namespace",
            return_value="azure-arc",
        ),
        patch("azext_connectedk8s.custom.generate_reput_request_payload"),
        patch("azext_connectedk8s.custom.create_cc_resource"),
        patch("azext_connectedk8s.custom.LongRunningOperation"),
        patch(
            "azext_connectedk8s.custom.poll_for_agent_state",
            return_value=(True, connected_cluster),
        ),
        patch(
            "azext_connectedk8s.custom.get_config_dp_endpoint",
            return_value=("https://endpoint", "stable"),
        ),
        patch("azext_connectedk8s.custom.utils.health_check_dp"),
        patch(
            "azext_connectedk8s.custom.utils.get_helm_values",
            return_value={
                "repositoryPath": "mcr.microsoft.com/azurearck8s/agents:1.0.0",
                "helmValuesContent": {},
            },
        ),
        patch("azext_connectedk8s.custom.utils.get_chart_path", return_value="chart"),
        patch("azext_connectedk8s.custom.check_operation_support"),
        patch("azext_connectedk8s.custom.kube_client.CoreV1Api"),
    ]
    with ExitStack() as stack:
        for each in patches:
            stack.enter_context(each)
        helm_update = stack.enter_context(
            patch("azext_connectedk8s.custom.utils.helm_update_agent")
        )
        ensure_bypass = stack.enter_context(
            patch(
                "azext_connectedk8s._containerinsightsutils.ensure_container_insights_proxy_bypass_configmap",
                side_effect=ValidationError("configmap failed"),
            )
        )

        with pytest.raises(ValidationError, match="configmap failed"):
            update_connected_cluster(
                MagicMock(),
                client,
                "resource-group",
                "cluster",
                no_proxy="Microsoft.AzureMonitor.Containers",
            )

    ensure_bypass.assert_called_once()
    helm_update.assert_not_called()


# --------- Test that a failed ARM create undoes the bypass without hiding the ARM error ---------
def _connect_patches(arm_error):
    # Scaffolding that drives create_connectedk8s down to the ARM create on a fresh onboarding.
    return [
        patch(
            "azext_connectedk8s.custom.send_cloud_telemetry", return_value="AzureCloud"
        ),
        patch("azext_connectedk8s.custom.telemetry"),
        patch(
            "azext_connectedk8s.custom.utils.validate_custom_token",
            return_value=(False, "eastus"),
        ),
        patch("azext_connectedk8s.custom.utils.check_provider_registrations"),
        patch("azext_connectedk8s.custom.utils.get_metadata", return_value={}),
        patch("azext_connectedk8s.custom.generate_arc_agent_configuration"),
        patch(
            "azext_connectedk8s.custom.get_config_dp_endpoint",
            return_value=("https://endpoint", "stable"),
        ),
        patch("azext_connectedk8s.custom.set_kube_config", return_value=None),
        patch("azext_connectedk8s.custom.load_kube_config"),
        patch(
            "azext_connectedk8s.custom.check_kube_connection", return_value="v1.28.0"
        ),
        patch("azext_connectedk8s.custom.utils.validate_node_api_response"),
        patch("azext_connectedk8s.custom.check_arm64_node", return_value=False),
        patch("azext_connectedk8s.custom.check_linux_node", return_value=True),
        patch("azext_connectedk8s.custom.get_kubectl_client_location", return_value=""),
        patch("azext_connectedk8s.custom.get_helm_client_location", return_value=""),
        patch(
            "azext_connectedk8s.custom.precheckutils",
            **{
                "fetch_diagnostic_checks_results.return_value": (
                    Diagnostic_Check_Passed,
                    True,
                )
            },
        ),
        patch(
            "azext_connectedk8s.custom.utils.can_create_clusterrolebindings",
            return_value=True,
        ),
        patch(
            "azext_connectedk8s.custom.get_kubernetes_distro", return_value="generic"
        ),
        patch("azext_connectedk8s.custom.get_kubernetes_infra", return_value="generic"),
        patch("azext_connectedk8s.custom.check_aks_cluster", return_value=False),
        patch("azext_connectedk8s.custom.utils.validate_connect_rp_location"),
        patch("azext_connectedk8s.custom.cf_resource_groups"),
        patch("azext_connectedk8s.custom.resource_group_exists", return_value=True),
        patch(
            "azext_connectedk8s.custom.utils.get_release_namespace", return_value=None
        ),
        patch("azext_connectedk8s.custom.connected_cluster_exists", return_value=False),
        # Runs real kubectl subprocesses against the stubbed client location otherwise.
        patch("azext_connectedk8s.custom.crd_cleanup_force_delete"),
        # A real 4096-bit key would make this test needlessly slow.
        patch("azext_connectedk8s.custom.RSA"),
        patch("azext_connectedk8s.custom.get_public_key", return_value="public"),
        patch("azext_connectedk8s.custom.get_private_key", return_value="private"),
        patch("azext_connectedk8s.custom.generate_request_payload"),
        patch(
            "azext_connectedk8s.custom.get_subscription_id",
            return_value=_SUBSCRIPTION_ID,
        ),
        patch("azext_connectedk8s.custom.create_cc_resource", side_effect=arm_error),
    ]


def test_connect_undoes_the_bypass_but_still_reports_the_arm_failure():
    # No cluster resource was created, so the bypass applied moments earlier is undone - with
    # the real removal, denied by the cluster. Because that rollback runs with
    # raise_on_failure=False it only warns, so the provisioning error the user actually has to
    # act on still reaches them. If that flag were ever flipped to True, a ConfigMap error
    # would surface here instead.
    arm_error = Exception("ARM rejected the request")

    with ExitStack() as stack:
        for each in _connect_patches(arm_error):
            stack.enter_context(each)
        core_api = stack.enter_context(
            patch("azext_connectedk8s.custom.kube_client.CoreV1Api")
        )
        ensure_bypass = stack.enter_context(
            patch(f"{_CIUTILS}.ensure_container_insights_proxy_bypass_configmap")
        )
        core_api.return_value.read_namespaced_config_map.side_effect = ApiException(
            status=403
        )

        with pytest.raises(Exception, match="ARM rejected the request"):
            create_connectedk8s(
                MagicMock(),
                MagicMock(),
                "resource-group",
                "cluster",
                no_proxy="Microsoft.AzureMonitor.Containers",
            )

    ensure_bypass.assert_called_once_with(core_api.return_value)


def test_plain_connect_is_not_blocked_by_a_denied_configmap():
    # With no --proxy-skip-range at all, the removal is cleanup nobody asked for, so a denied
    # ConfigMap must not stop onboarding. Reaching the ARM create proves it got past that step.
    sentinel = Exception("reached the ARM create")

    with ExitStack() as stack:
        for each in _connect_patches(sentinel):
            stack.enter_context(each)
        core_api = stack.enter_context(
            patch("azext_connectedk8s.custom.kube_client.CoreV1Api")
        )
        core_api.return_value.read_namespaced_config_map.side_effect = ApiException(
            status=403
        )

        with pytest.raises(Exception, match="reached the ARM create"):
            create_connectedk8s(MagicMock(), MagicMock(), "resource-group", "cluster")


# --------------------- Tests for clearing NO_PROXY ---------------------
@pytest.mark.parametrize(
    "http_proxy, https_proxy, no_proxy, clear, expected_settings, expected_protected",
    [
        # Nothing was requested, so the proxy feature is not touched at all.
        ("", "", "", False, {}, {}),
        # The Container Insights keyword expands to an empty no_proxy. It still has to be
        # sent, otherwise the NO_PROXY already on the cluster silently survives.
        ("", "", "", True, {"proxy": {}}, {"proxy": {"no_proxy": ""}}),
        # A non-empty value is unaffected by the clear flag.
        (
            "",
            "",
            "10.0.0.0/24",
            True,
            {"proxy": {}},
            {"proxy": {"no_proxy": "10.0.0.0/24"}},
        ),
        # Clearing NO_PROXY leaves the other proxy settings alone.
        (
            "http://proxy:3128",
            "https://proxy:3128",
            "",
            True,
            {"proxy": {}},
            {
                "proxy": {
                    "http_proxy": "http://proxy:3128",
                    "https_proxy": "https://proxy:3128",
                    "no_proxy": "",
                }
            },
        ),
    ],
)
def test_no_proxy_is_only_sent_when_it_was_requested(
    http_proxy, https_proxy, no_proxy, clear, expected_settings, expected_protected
):
    settings, protected, _ = add_config_protected_settings(
        http_proxy,
        https_proxy,
        no_proxy,
        "",
        None,
        None,
        None,
        clear_no_proxy=clear,
    )

    assert settings == expected_settings
    assert protected == expected_protected


@pytest.mark.parametrize(
    "no_proxy, expected_no_proxy",
    [
        ("Microsoft.AzureMonitor.Containers", ""),
        ("microsoft.azuremonitor.containers", ""),
        ("10.0.0.0/24,Microsoft.AzureMonitor.Containers", "10.0.0.0\\/24"),
    ],
)
def test_update_sends_no_proxy_for_every_proxy_skip_range(no_proxy, expected_no_proxy):
    # Whatever the keyword expands to, --proxy-skip-range must always replace NO_PROXY
    # rather than leave the previous value in place.
    captured = {}

    def fake_add_config(*args, **kwargs):
        captured["no_proxy"] = args[2]
        captured["clear_no_proxy"] = kwargs.get("clear_no_proxy")
        raise _StopUpdate("stop")

    patches = [
        patch(
            "azext_connectedk8s.custom.send_cloud_telemetry", return_value="AzureCloud"
        ),
        patch("azext_connectedk8s.custom.set_kube_config", return_value=None),
        patch("azext_connectedk8s.custom.telemetry"),
        patch(
            "azext_connectedk8s.custom.add_config_protected_settings",
            side_effect=fake_add_config,
        ),
    ]
    with ExitStack() as stack:
        for each in patches:
            stack.enter_context(each)

        with pytest.raises(_StopUpdate):
            update_connected_cluster(
                MagicMock(),
                MagicMock(),
                "resource-group",
                "cluster",
                no_proxy=no_proxy,
            )

    assert captured["no_proxy"] == expected_no_proxy
    # An empty expansion still has to be written, so the clear flag carries the intent.
    assert captured["clear_no_proxy"] is (expected_no_proxy == "")


def test_update_does_not_clear_no_proxy_when_skip_range_was_not_passed():
    captured = {}

    def fake_add_config(*args, **kwargs):
        captured["clear_no_proxy"] = kwargs.get("clear_no_proxy")
        raise _StopUpdate("stop")

    patches = [
        patch(
            "azext_connectedk8s.custom.send_cloud_telemetry", return_value="AzureCloud"
        ),
        patch("azext_connectedk8s.custom.set_kube_config", return_value=None),
        patch("azext_connectedk8s.custom.telemetry"),
        patch(
            "azext_connectedk8s.custom.add_config_protected_settings",
            side_effect=fake_add_config,
        ),
    ]
    with ExitStack() as stack:
        for each in patches:
            stack.enter_context(each)

        with pytest.raises(_StopUpdate):
            update_connected_cluster(
                MagicMock(),
                MagicMock(),
                "resource-group",
                "cluster",
                https_proxy="https://proxy:3128",
            )

    assert captured["clear_no_proxy"] is False
