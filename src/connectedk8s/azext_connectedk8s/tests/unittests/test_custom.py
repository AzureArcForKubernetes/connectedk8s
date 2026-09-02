# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
import os
import sys
from typing import Dict, Optional
from unittest.mock import MagicMock

import pytest
from kubernetes.client.models import V1Node, V1NodeList, V1NodeSpec, V1ObjectMeta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from azext_connectedk8s import custom
from azext_connectedk8s.custom import (
    _telemetry_catch_all,
    get_arc_proxy_skip_range_endpoints,
    get_kubernetes_distro,
    get_kubernetes_infra,
)


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


# ---------------- Tests for get_arc_proxy_skip_range_endpoints ----------------
def _proxy_cmd(active_directory="https://login.microsoftonline.com"):
    cmd = MagicMock()
    cmd.cli_ctx.cloud.endpoints.active_directory = active_directory
    return cmd


def test_arc_endpoints_public_cloud():
    assert get_arc_proxy_skip_range_endpoints(_proxy_cmd()) == [
        ".his.arc.azure.com",
        ".dp.kubernetesconfiguration.azure.com",
        ".guestconfiguration.azure.com",
    ]


def test_arc_endpoints_china_cloud():
    cmd = _proxy_cmd("https://login.chinacloudapi.cn")
    assert get_arc_proxy_skip_range_endpoints(cmd) == [
        ".his.arc.azure.cn",
        ".dp.kubernetesconfiguration.azure.cn",
        ".guestconfiguration.azure.cn",
    ]


def test_arc_endpoints_usgov_cloud():
    cmd = _proxy_cmd("https://login.microsoftonline.us")
    assert get_arc_proxy_skip_range_endpoints(cmd) == [
        ".his.arc.azure.us",
        ".dp.kubernetesconfiguration.azure.us",
        ".guestconfiguration.azure.us",
    ]


def test_arc_endpoints_ussec_cloud():
    cmd = _proxy_cmd("https://login.microsoftonline.microsoft.scloud")
    assert get_arc_proxy_skip_range_endpoints(cmd) == [
        ".his.arc.azure.microsoft.scloud",
        ".dp.kubernetesconfiguration.azure.microsoft.scloud",
        ".guestconfiguration.azure.microsoft.scloud",
    ]


def test_arc_endpoints_usnat_cloud():
    cmd = _proxy_cmd("https://login.microsoftonline.eaglex.ic.gov")
    assert get_arc_proxy_skip_range_endpoints(cmd) == [
        ".his.arc.azure.eaglex.ic.gov",
        ".dp.kubernetesconfiguration.azure.eaglex.ic.gov",
        ".guestconfiguration.azure.eaglex.ic.gov",
    ]
