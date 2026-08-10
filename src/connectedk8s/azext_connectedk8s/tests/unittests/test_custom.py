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
from azure.cli.core.azclierror import AzCLIError, MutuallyExclusiveArgumentError
from kubernetes.client.models import (
    V1ConfigMap,
    V1Node,
    V1NodeList,
    V1NodeSpec,
    V1ObjectMeta,
)
from kubernetes.client.rest import ApiException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from azext_connectedk8s._constants import CI_ConfigMap_Proxy_Bypass_Annotation
from azext_connectedk8s.custom import (
    add_config_protected_settings,
    container_insights_bypass_requested,
    create_container_insights_proxy_bypass_configmap,
    delete_connectedk8s,
    ensure_container_insights_proxy_bypass_configmap,
    expand_proxy_skip_range_keywords,
    get_kubernetes_distro,
    get_kubernetes_infra,
    merge_proxy_bypass_into_agent_settings,
    remove_container_insights_proxy_bypass_configmap,
    remove_proxy_bypass_from_agent_settings,
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


# ------------- Tests for the Container Insights proxy-skip-range keyword -------------
def test_expand_container_insights_keyword_dropped_preserves_other_entries():
    # Container Insights is handled via a ConfigMap, so it is dropped from NO_PROXY.
    out = expand_proxy_skip_range_keywords(
        _proxy_cmd(), "Microsoft.AzureMonitor.Containers,10.0.0.0/16,.svc"
    )
    assert out == "10.0.0.0/16,.svc"


@pytest.mark.parametrize(
    "keyword",
    [
        "Microsoft.AzureMonitor.Containers",
        "microsoft.azuremonitor.containers",
        "MICROSOFT.AZUREMONITOR.CONTAINERS",
        " Microsoft.AzureMonitor.Containers ",
    ],
)
def test_expand_container_insights_keyword_is_case_and_space_insensitive(keyword):
    assert expand_proxy_skip_range_keywords(_proxy_cmd(), keyword) == ""


def test_expand_arc_and_container_insights_together():
    # Arc expands to its endpoints; Container Insights is dropped; other entries kept.
    out = expand_proxy_skip_range_keywords(
        _proxy_cmd(), "Arc,Microsoft.AzureMonitor.Containers,10.0.0.0/16"
    )
    assert out == ARC_PUBLIC + ",10.0.0.0/16"


@pytest.mark.parametrize(
    "no_proxy",
    [
        "Microsoft.AzureMonitor.Containers",
        "10.0.0.0/16,Microsoft.AzureMonitor.Containers",
        "Arc, microsoft.azuremonitor.containers ",
        "MICROSOFT.AZUREMONITOR.CONTAINERS",
    ],
)
def test_container_insights_bypass_requested_true(no_proxy):
    assert container_insights_bypass_requested(no_proxy) is True


@pytest.mark.parametrize("no_proxy", ["", None, "Arc", "10.0.0.0/16,.svc"])
def test_container_insights_bypass_requested_false(no_proxy):
    assert container_insights_bypass_requested(no_proxy) is False


# ------------- Tests for merging the proxy bypass into an existing ConfigMap -------------
def test_merge_adds_block_when_agent_settings_empty():
    # An absent/empty agent-settings gets a fresh, active proxy_config block.
    assert (
        merge_proxy_bypass_into_agent_settings("")
        == '[agent_settings.proxy_config]\n    ignore_proxy_settings = "true"'
    )


def test_merge_is_noop_when_already_true():
    # Already bypassing: return the input unchanged so no needless ConfigMap write happens.
    existing = '[agent_settings.proxy_config]\n    ignore_proxy_settings = "true"'
    assert merge_proxy_bypass_into_agent_settings(existing) == existing


def test_merge_flips_false_to_true_without_duplicating():
    existing = '[agent_settings.proxy_config]\n    ignore_proxy_settings = "false"'
    out = merge_proxy_bypass_into_agent_settings(existing)
    assert 'ignore_proxy_settings = "true"' in out
    assert '"false"' not in out
    assert out.count("[agent_settings.proxy_config]") == 1


def test_merge_preserves_existing_unrelated_settings():
    existing = "[agent_settings.high_log_scale]\n  enabled = false\n"
    out = merge_proxy_bypass_into_agent_settings(existing)
    # Existing content is untouched...
    assert "[agent_settings.high_log_scale]" in out
    assert "enabled = false" in out
    # ...and the bypass is appended.
    assert "[agent_settings.proxy_config]" in out
    assert 'ignore_proxy_settings = "true"' in out


def test_merge_ignores_commented_template_and_adds_one_active_setting():
    existing = (
        "# [agent_settings.proxy_config]\n"
        '#    ignore_proxy_settings = "true"  # if this is not applied, default value is false\n'
    )
    out = merge_proxy_bypass_into_agent_settings(existing)
    # The commented template lines are preserved...
    assert "# [agent_settings.proxy_config]" in out
    # ...and exactly one ACTIVE ignore_proxy_settings line is present.
    active = [
        ln for ln in out.splitlines() if ln.strip().startswith("ignore_proxy_settings")
    ]
    assert active == ['    ignore_proxy_settings = "true"']


def test_merge_inserts_under_active_header_without_duplicating():
    out = merge_proxy_bypass_into_agent_settings("[agent_settings.proxy_config]\n")
    assert out.count("[agent_settings.proxy_config]") == 1
    assert 'ignore_proxy_settings = "true"' in out


def test_merge_ignores_the_setting_in_another_section():
    # The setting only applies under proxy_config, so a same-named setting elsewhere is left
    # alone and a proper section is added instead.
    existing = '[agent_settings.some_other]\n    ignore_proxy_settings = "false"'
    out = merge_proxy_bypass_into_agent_settings(existing)
    assert '[agent_settings.some_other]\n    ignore_proxy_settings = "false"' in out
    assert out.endswith(
        '[agent_settings.proxy_config]\n    ignore_proxy_settings = "true"'
    )


def test_merge_targets_proxy_config_when_another_section_has_the_setting():
    existing = (
        '[agent_settings.some_other]\n    ignore_proxy_settings = "false"\n'
        '[agent_settings.proxy_config]\n    ignore_proxy_settings = "false"'
    )
    out = merge_proxy_bypass_into_agent_settings(existing)
    assert out == (
        '[agent_settings.some_other]\n    ignore_proxy_settings = "false"\n'
        '[agent_settings.proxy_config]\n    ignore_proxy_settings = "true"'
    )


# --------- Tests for the ensure/create ConfigMap kube-client interaction ---------
_BYPASS_SETTING = 'ignore_proxy_settings = "true"'
_ALREADY_BYPASSING = f"[agent_settings.proxy_config]\n    {_BYPASS_SETTING}"


def _configmap(data):
    # Minimal V1ConfigMap stand-in carrying the given data dict.
    return V1ConfigMap(data=data)


def test_ensure_creates_configmap_when_absent():
    # A 404 on read means the ConfigMap is absent, so a fresh one must be created.
    api = MagicMock()
    api.read_namespaced_config_map.side_effect = ApiException(status=404)

    ensure_container_insights_proxy_bypass_configmap(api)

    api.create_namespaced_config_map.assert_called_once()
    body = api.create_namespaced_config_map.call_args.kwargs["body"]
    assert _BYPASS_SETTING in body.data["agent-settings"]
    api.replace_namespaced_config_map.assert_not_called()


def test_ensure_merges_into_existing_configmap_preserving_other_settings():
    # An existing ConfigMap is updated in place, keeping unrelated agent settings.
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _configmap(
        {"agent-settings": "[agent_settings.high_log_scale]\n  enabled = false\n"}
    )

    ensure_container_insights_proxy_bypass_configmap(api)

    api.create_namespaced_config_map.assert_not_called()
    api.replace_namespaced_config_map.assert_called_once()
    body = api.replace_namespaced_config_map.call_args.kwargs["body"]
    merged = body.data["agent-settings"]
    assert "[agent_settings.high_log_scale]" in merged
    assert _BYPASS_SETTING in merged


def test_ensure_is_noop_when_existing_configmap_already_bypasses():
    # If the ConfigMap already bypasses the proxy, no write should happen.
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _configmap(
        {"agent-settings": _ALREADY_BYPASSING}
    )

    ensure_container_insights_proxy_bypass_configmap(api)

    api.replace_namespaced_config_map.assert_not_called()
    api.create_namespaced_config_map.assert_not_called()


def test_create_falls_back_to_merge_on_conflict():
    # A 409 on create means the ConfigMap appeared concurrently; fall back to merge.
    api = MagicMock()
    api.create_namespaced_config_map.side_effect = ApiException(status=409)

    with patch(
        "azext_connectedk8s.custom.ensure_container_insights_proxy_bypass_configmap"
    ) as mock_ensure:
        create_container_insights_proxy_bypass_configmap(api)

    mock_ensure.assert_called_once_with(api)


# --------- Tests for the annotation that marks the setting as written by this CLI ---------


def _stamped_configmap(data, stamped=True):
    # V1ConfigMap stand-in that carries (or deliberately lacks) the ownership annotation.
    annotations = {CI_ConfigMap_Proxy_Bypass_Annotation: "azure-cli"} if stamped else {}
    return V1ConfigMap(data=data, metadata=V1ObjectMeta(annotations=annotations))


def test_create_stamps_the_configmap_with_the_annotation():
    # A ConfigMap created by this CLI must carry the annotation.
    api = MagicMock()

    create_container_insights_proxy_bypass_configmap(api)

    body = api.create_namespaced_config_map.call_args.kwargs["body"]
    assert (
        body.metadata.annotations[CI_ConfigMap_Proxy_Bypass_Annotation] == "azure-cli"
    )


def test_ensure_stamps_the_configmap_when_it_writes_the_setting():
    # Adding the setting to an existing ConfigMap must stamp it too.
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _configmap(
        {"agent-settings": "[agent_settings.high_log_scale]\n  enabled = false\n"}
    )

    ensure_container_insights_proxy_bypass_configmap(api)

    body = api.replace_namespaced_config_map.call_args.kwargs["body"]
    assert (
        body.metadata.annotations[CI_ConfigMap_Proxy_Bypass_Annotation] == "azure-cli"
    )


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


def test_remove_leaves_an_unstamped_configmap_alone():
    # Without the annotation the setting is customer-configured, so it must survive.
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _stamped_configmap(
        {"agent-settings": _ALREADY_BYPASSING}, stamped=False
    )

    remove_container_insights_proxy_bypass_configmap(api)

    api.replace_namespaced_config_map.assert_not_called()


def test_remove_strips_both_the_setting_and_the_stamp():
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _stamped_configmap(
        {"agent-settings": _ALREADY_BYPASSING}
    )

    remove_container_insights_proxy_bypass_configmap(api)

    body = api.replace_namespaced_config_map.call_args.kwargs["body"]
    assert body.data["agent-settings"] == ""
    assert CI_ConfigMap_Proxy_Bypass_Annotation not in body.metadata.annotations


def test_remove_keeps_unrelated_agent_settings():
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _stamped_configmap(
        {
            "agent-settings": (
                f"[agent_settings.high_log_scale]\n  enabled = false\n{_ALREADY_BYPASSING}"
            )
        }
    )

    remove_container_insights_proxy_bypass_configmap(api)

    body = api.replace_namespaced_config_map.call_args.kwargs["body"]
    assert "[agent_settings.high_log_scale]" in body.data["agent-settings"]
    assert _BYPASS_SETTING not in body.data["agent-settings"]


def test_customer_owned_bypass_survives_a_later_removal():
    # A bypass the customer set themselves is left as is, so nothing is written back.
    api = MagicMock()
    api.read_namespaced_config_map.return_value = _stamped_configmap(
        {"agent-settings": _ALREADY_BYPASSING}, stamped=False
    )

    ensure_container_insights_proxy_bypass_configmap(api)
    remove_container_insights_proxy_bypass_configmap(api)

    api.replace_namespaced_config_map.assert_not_called()


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


def test_delete_removes_the_bypass_when_no_helm_release_is_present():
    # Delete returns early when the agents are already gone, but the bypass can still be there.
    patches = [
        patch(
            "azext_connectedk8s.custom.send_cloud_telemetry", return_value="AzureCloud"
        ),
        patch("azext_connectedk8s.custom.set_kube_config", return_value=None),
        patch("azext_connectedk8s.custom.load_kube_config"),
        patch("azext_connectedk8s.custom.check_kube_connection"),
        patch("azext_connectedk8s.custom.get_helm_client_location", return_value=""),
        patch(
            "azext_connectedk8s.custom.utils.get_release_namespace", return_value=None
        ),
        patch("azext_connectedk8s.custom.utils.validate_node_api_response"),
        patch("azext_connectedk8s.custom.check_arm64_node", return_value=False),
        patch("azext_connectedk8s.custom.delete_cc_resource"),
    ]
    with ExitStack() as stack:
        for each in patches:
            stack.enter_context(each)
        core_api = stack.enter_context(
            patch("azext_connectedk8s.custom.kube_client.CoreV1Api")
        )
        remove_bypass = stack.enter_context(
            patch(
                "azext_connectedk8s.custom.remove_container_insights_proxy_bypass_configmap"
            )
        )

        delete_connectedk8s(
            MagicMock(), MagicMock(), "resource-group", "cluster", yes=True
        )

    remove_bypass.assert_called_once_with(core_api.return_value)


# --------------------- Tests for clearing NO_PROXY ---------------------
def test_no_proxy_is_skipped_when_the_flag_was_not_passed():
    # Nothing was requested, so the proxy feature must not be touched at all.
    settings, protected, redacted = add_config_protected_settings(
        "", "", "", "", None, None, None
    )

    assert settings == {}
    assert protected == {}
    assert redacted == {}


def test_empty_no_proxy_is_sent_when_clearing_was_requested():
    # The Container Insights keyword expands to an empty no_proxy. It still has to be sent,
    # otherwise the previously configured NO_PROXY silently survives on the cluster.
    settings, protected, redacted = add_config_protected_settings(
        "", "", "", "", None, None, None, clear_no_proxy=True
    )

    assert settings == {"proxy": {}}
    assert protected == {"proxy": {"no_proxy": ""}}
    assert redacted == {"proxy": {"no_proxy": "redacted:proxy:no_proxy"}}


def test_non_empty_no_proxy_is_unchanged_by_the_clear_flag():
    _, protected, _ = add_config_protected_settings(
        "", "", "10.0.0.0/24", "", None, None, None, clear_no_proxy=True
    )

    assert protected == {"proxy": {"no_proxy": "10.0.0.0/24"}}


def test_clearing_no_proxy_preserves_the_other_proxy_settings():
    _, protected, _ = add_config_protected_settings(
        "http://proxy:3128",
        "https://proxy:3128",
        "",
        "",
        None,
        None,
        None,
        clear_no_proxy=True,
    )

    assert protected == {
        "proxy": {
            "http_proxy": "http://proxy:3128",
            "https_proxy": "https://proxy:3128",
            "no_proxy": "",
        }
    }


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
