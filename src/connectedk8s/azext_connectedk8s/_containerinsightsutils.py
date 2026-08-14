# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
"""
Container Insights proxy bypass for az connectedk8s connect/update/delete.

The Container Insights agent (ama-logs) does not read the proxy settings held by the Arc
agents. It is configured through the "container-azm-ms-agentconfig" ConfigMap in the
"kube-system" namespace, where "ignore_proxy_settings" under [agent_settings.proxy_config]
tells it to bypass the proxy.

Passing the Container Insights extension type to --proxy-skip-range therefore cannot be
handled like an no_proxy address. custom.py strips the keyword out of no_proxy and
calls into this module instead.

Flow:
  1. custom.py calls container_insights_bypass_requested() on the user's --proxy-skip-range
  2. sync_container_insights_proxy_bypass_configmap() then dispatches on that answer, so
     connect and update cannot drift apart:
       - requested     -> ensure_container_insights_proxy_bypass_configmap() writes the
                          setting, creating the ConfigMap only if it does not already exist
       - not requested -> remove_container_insights_proxy_bypass_configmap() undoes a setting
                          added by an earlier run, identified by the annotation this CLI stamps
  3. delete calls remove_container_insights_proxy_bypass_configmap() directly
  4. Every call runs before the step it protects, so a failure stops the command instead of
     leaving the agents and the ConfigMap out of step

Only the "ignore_proxy_settings" line is ever written or removed, and removal happens only
where the annotation shows this CLI added it, so settings the customer owns are left alone.
"""

from __future__ import annotations

from azure.cli.core import telemetry
from knack.log import get_logger
from kubernetes import client as kube_client

import azext_connectedk8s._constants as consts
import azext_connectedk8s._utils as utils

logger = get_logger(__name__)


def container_insights_bypass_requested(no_proxy: str | None) -> bool:
    # True when the user requested the Container Insights proxy bypass via the keyword.
    if not no_proxy:
        return False
    return any(
        entry.strip().lower() == consts.Proxy_Skip_Range_ContainerInsights_Keyword
        for entry in no_proxy.split(",")
    )


def find_active_proxy_bypass_setting(lines: list[str]) -> tuple[int | None, int | None]:
    # Find the active ignore_proxy_settings line inside [agent_settings.proxy_config]. The
    # setting is scoped to that section, so a match anywhere else is not a proxy bypass.
    # Returns its header and index, or the first proxy_config header when the setting is absent.
    first_header: int | None = None
    current_header: int | None = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Track which section the following settings belong to.
        if stripped.startswith("["):
            in_section = stripped.startswith(consts.CI_ConfigMap_Proxy_Config_Section)
            current_header = i if in_section else None
            if in_section and first_header is None:
                first_header = i
            continue
        if current_header is not None and stripped.startswith(
            consts.CI_ConfigMap_Proxy_Bypass_Setting
        ):
            return current_header, i

    return first_header, None


def merge_proxy_bypass_into_agent_settings(agent_settings: str) -> str:
    # Set ignore_proxy_settings to "true" in place, leaving the agent's other settings intact.
    lines = agent_settings.splitlines()
    header, setting = find_active_proxy_bypass_setting(lines)

    # An existing active setting is forced to "true".
    if setting is not None:
        line = lines[setting]
        enabled = consts.CI_ConfigMap_Proxy_Bypass_Enabled.replace(" ", "")
        if line.strip().replace(" ", "").startswith(enabled):
            return agent_settings
        indent = line[: len(line) - len(line.lstrip())]
        lines[setting] = f"{indent}{consts.CI_ConfigMap_Proxy_Bypass_Enabled}"
        return "\n".join(lines)

    # No active setting: add it under an existing active proxy_config header if present.
    if header is not None:
        lines.insert(header + 1, f"    {consts.CI_ConfigMap_Proxy_Bypass_Enabled}")
        return "\n".join(lines)

    # Otherwise append a fresh proxy_config section.
    block = consts.CI_ConfigMap_Proxy_Bypass_Block
    if not agent_settings.strip():
        return block
    return agent_settings.rstrip("\n") + "\n" + block


def remove_proxy_bypass_from_agent_settings(agent_settings: str) -> str:
    # Remove the ignore_proxy_settings line, leaving the agent's other settings intact.
    lines = agent_settings.splitlines()
    header, setting = find_active_proxy_bypass_setting(lines)

    # Nothing to undo unless proxy_config holds an active setting.
    if setting is None or header is None:
        return agent_settings

    del lines[setting]

    # Drop that header as well, unless another setting still belongs to it.
    for i in range(header + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            break
        return "\n".join(lines)

    del lines[header]
    return "\n".join(lines)


def report_container_insights_configmap_failure(
    e: Exception,
    fault_type: str,
    summary: str,
    raise_on_failure: bool = True,
    error_message: str = consts.CI_ConfigMap_Error_Message,
) -> None:
    # True raises so the command stops here; False logs a warning and returns.
    if not raise_on_failure:
        logger.warning(consts.CI_ConfigMap_Removal_Failed_Warning)
        logger.debug("Kubernetes Exception: ", exc_info=True)
        telemetry.set_exception(exception=e, fault_type=fault_type, summary=summary)
        return

    utils.kubernetes_exception_handler(
        e,
        fault_type,
        summary,
        error_message=error_message,
        message_for_unauthorized_request=consts.CI_ConfigMap_Unauthorized_Message,
    )


def ensure_container_insights_proxy_bypass_configmap(
    api_instance: kube_client.CoreV1Api,
) -> None:
    # Create the ConfigMap when absent, otherwise merge the bypass into the existing one.
    # Runs before the cluster resource and the helm upgrade, so a failure stops the command.
    print(
        f"Step: {utils.get_utctimestring()}: Ensuring '{consts.CI_ConfigMap_Name}' ConfigMap "
        f"in '{consts.CI_ConfigMap_Namespace}' namespace bypasses the proxy for Container Insights"
    )

    try:
        existing = api_instance.read_namespaced_config_map(
            name=consts.CI_ConfigMap_Name,
            namespace=consts.CI_ConfigMap_Namespace,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        # An absent ConfigMap is not a failure; it is created with just the bypass setting.
        if getattr(e, "status", None) == 404:
            create_container_insights_proxy_bypass_configmap(api_instance)
            return
        report_container_insights_configmap_failure(
            e,
            consts.Read_ConfigMap_Fault_Type,
            "Unable to read Container Insights proxy-bypass ConfigMap",
        )
        return

    # Merge the bypass into the existing agent-settings, keeping all other settings.
    data = existing.data or {}
    current = data.get(consts.CI_ConfigMap_Agent_Settings_Key, "")
    merged = merge_proxy_bypass_into_agent_settings(current)
    if merged == current:
        print(
            f"Step: {utils.get_utctimestring()}: '{consts.CI_ConfigMap_Name}' ConfigMap already "
            f"bypasses the proxy for Container Insights; no change needed"
        )
        return

    data[consts.CI_ConfigMap_Agent_Settings_Key] = merged
    existing.data = data
    # Only reached when this CLI changed the setting, so stamp it for removal by a later run.
    if existing.metadata is None:
        existing.metadata = kube_client.V1ObjectMeta(
            name=consts.CI_ConfigMap_Name,
            namespace=consts.CI_ConfigMap_Namespace,
        )
    annotations = existing.metadata.annotations or {}
    annotations[consts.CI_ConfigMap_Proxy_Bypass_Annotation] = "azure-cli"
    existing.metadata.annotations = annotations
    try:
        api_instance.replace_namespaced_config_map(
            name=consts.CI_ConfigMap_Name,
            namespace=consts.CI_ConfigMap_Namespace,
            body=existing,
        )
        print(
            f"Step: {utils.get_utctimestring()}: Updated existing '{consts.CI_ConfigMap_Name}' "
            f"ConfigMap to bypass the proxy for Container Insights"
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        report_container_insights_configmap_failure(
            e,
            consts.Create_ConfigMap_Fault_Type,
            "Unable to update Container Insights proxy-bypass ConfigMap",
        )


def create_container_insights_proxy_bypass_configmap(
    api_instance: kube_client.CoreV1Api,
) -> None:
    # Seed only the proxy-bypass setting; the Container Insights solution fills in the rest.
    configmap = kube_client.V1ConfigMap(
        metadata=kube_client.V1ObjectMeta(
            name=consts.CI_ConfigMap_Name,
            namespace=consts.CI_ConfigMap_Namespace,
            # Stamp the ConfigMap so a later run can remove the setting added here.
            annotations={consts.CI_ConfigMap_Proxy_Bypass_Annotation: "azure-cli"},
        ),
        data={
            "schema-version": "v1",
            "config-version": "ver1",
            consts.CI_ConfigMap_Agent_Settings_Key: consts.CI_ConfigMap_Proxy_Bypass_Block,
        },
    )

    try:
        api_instance.create_namespaced_config_map(
            namespace=consts.CI_ConfigMap_Namespace,
            body=configmap,
        )
        print(
            f"Step: {utils.get_utctimestring()}: Created '{consts.CI_ConfigMap_Name}' ConfigMap "
            f"in '{consts.CI_ConfigMap_Namespace}' namespace for Container Insights proxy bypass"
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        if getattr(e, "status", None) == 409:
            # ConfigMap appeared between the read and this create; merge into it instead.
            logger.warning(
                "ConfigMap '%s' appeared concurrently in '%s' namespace; merging the "
                "proxy-bypass setting into it.",
                consts.CI_ConfigMap_Name,
                consts.CI_ConfigMap_Namespace,
            )
            ensure_container_insights_proxy_bypass_configmap(api_instance)
            return
        report_container_insights_configmap_failure(
            e,
            consts.Create_ConfigMap_Fault_Type,
            "Unable to create Container Insights proxy-bypass ConfigMap",
        )


def remove_container_insights_proxy_bypass_configmap(
    api_instance: kube_client.CoreV1Api,
    raise_on_failure: bool = True,
) -> None:
    # Undo the bypass only where the annotation shows this CLI added it. A setting without that
    # annotation is customer-configured and is left untouched.
    try:
        existing = api_instance.read_namespaced_config_map(
            name=consts.CI_ConfigMap_Name,
            namespace=consts.CI_ConfigMap_Namespace,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        # No ConfigMap means there is no setting to undo; never create one here.
        if getattr(e, "status", None) == 404:
            return
        report_container_insights_configmap_failure(
            e,
            consts.Read_ConfigMap_Fault_Type,
            "Unable to read Container Insights proxy-bypass ConfigMap",
            raise_on_failure,
            error_message=consts.CI_ConfigMap_Removal_Error_Message,
        )
        return

    # Without metadata there is no annotation, so the setting was not added by this CLI.
    metadata = existing.metadata
    annotations = (metadata.annotations or {}) if metadata else {}
    if consts.CI_ConfigMap_Proxy_Bypass_Annotation not in annotations:
        return

    data = existing.data or {}
    current = data.get(consts.CI_ConfigMap_Agent_Settings_Key, "")
    data[consts.CI_ConfigMap_Agent_Settings_Key] = (
        remove_proxy_bypass_from_agent_settings(current)
    )
    existing.data = data

    # Drop the annotation too, so a later run does not look for a setting that is no longer there.
    del annotations[consts.CI_ConfigMap_Proxy_Bypass_Annotation]
    metadata.annotations = annotations

    try:
        api_instance.replace_namespaced_config_map(
            name=consts.CI_ConfigMap_Name,
            namespace=consts.CI_ConfigMap_Namespace,
            body=existing,
        )
        print(
            f"Step: {utils.get_utctimestring()}: Removed the Container Insights proxy bypass "
            f"from '{consts.CI_ConfigMap_Name}' ConfigMap in "
            f"'{consts.CI_ConfigMap_Namespace}' namespace"
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        report_container_insights_configmap_failure(
            e,
            consts.Create_ConfigMap_Fault_Type,
            "Unable to remove the Container Insights proxy-bypass setting",
            raise_on_failure,
            error_message=consts.CI_ConfigMap_Removal_Error_Message,
        )


def sync_container_insights_proxy_bypass_configmap(
    api_instance: kube_client.CoreV1Api,
    requested: bool,
    raise_on_removal_failure: bool = True,
) -> None:
    # Single entry point for connect and update, so the two cannot drift apart.
    # Apply the bypass when requested, otherwise remove it.
    if requested:
        ensure_container_insights_proxy_bypass_configmap(api_instance)
    else:
        remove_container_insights_proxy_bypass_configmap(
            api_instance, raise_on_failure=raise_on_removal_failure
        )
