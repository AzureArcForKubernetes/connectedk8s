# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
from __future__ import annotations

from typing import TYPE_CHECKING

from azure.cli.core.azclierror import ArgumentUsageError

import azext_connectedk8s._constants as consts

if TYPE_CHECKING:
    from argparse import Namespace

    from knack.commands import CLICommand


def parse_proxy_bypass_keywords(proxy_bypass: str | None) -> list[str]:
    # Every consumer has to split the flag value the same way, otherwise validation and
    # the code acting on the keywords can disagree about what the user asked for.
    if not proxy_bypass:
        return []
    return [keyword.strip() for keyword in proxy_bypass.split(",") if keyword.strip()]


def has_proxy_bypass_keyword(proxy_bypass: str | None, keyword: str) -> bool:
    # Matching is case-insensitive, so a keyword counts however the user typed it.
    return any(
        entry.lower() == keyword.lower()
        for entry in parse_proxy_bypass_keywords(proxy_bypass)
    )


def validate_proxy_bypass(namespace: Namespace) -> None:
    # get_enum_type rejects comma-separated lists, so each keyword is checked here.
    # --clear-proxy-bypass is update-only, so both flags are read defensively.
    allowed_values = ", ".join(consts.Proxy_Bypass_Enum_Values)
    allowed_keywords = {value.lower() for value in consts.Proxy_Bypass_Enum_Values}
    for flag, dest in (
        ("--add-proxy-bypass", "add_proxy_bypass"),
        ("--clear-proxy-bypass", "clear_proxy_bypass"),
    ):
        keywords = parse_proxy_bypass_keywords(getattr(namespace, dest, None))
        invalid = [
            keyword for keyword in keywords if keyword.lower() not in allowed_keywords
        ]
        if invalid:
            err_msg = (
                f"Invalid value for {flag}: {', '.join(invalid)}. "
                f"Allowed values are {allowed_values}."
            )
            raise ArgumentUsageError(err_msg)


def validate_private_link_properties(namespace: Namespace) -> None:
    if not namespace.enable_private_link and namespace.private_link_scope_resource_id:
        err_msg = (
            "Conflicting private link parameters received. The parameter "
            "'--private-link-scope-resource-id' should not be set if '--enable-private-link' is "
            "passed as null or False."
        )
        raise ArgumentUsageError(err_msg)
    if (
        namespace.enable_private_link is True
        and not namespace.private_link_scope_resource_id
    ):
        err_msg = (
            "The parameter '--private-link-scope-resource-id' was not provided. It is mandatory "
            "to pass this parameter for enabling private link on the connected cluster resource."
        )
        raise ArgumentUsageError(err_msg)


def override_client_request_id_header(cmd: CLICommand, namespace: Namespace) -> None:
    if namespace.correlation_id is not None:
        cmd.cli_ctx.data["headers"][consts.Client_Request_Id_Header] = (
            namespace.correlation_id
        )
    else:
        cmd.cli_ctx.data["headers"][consts.Client_Request_Id_Header] = (
            consts.Default_Onboarding_Source_Tracking_Guid
        )


def validate_gateway_updates(namespace: Namespace) -> None:
    if namespace.gateway_resource_id != "" and namespace.disable_gateway:
        raise ArgumentUsageError(
            "Cannot specify both --gateway-resource-id and --disable-gateway simultaneously."
        )


def validate_enable_oidc_issuer_updates(namespace: Namespace) -> None:
    if namespace.enable_oidc_issuer is False:
        raise ArgumentUsageError("Disabling OIDC issuer is not supported.")


def validate_self_hosted_issuer(namespace: Namespace) -> None:
    if namespace.self_hosted_issuer != "" and not namespace.enable_oidc_issuer:
        raise ArgumentUsageError(
            "Cannot specify a value for --self-hosted-issuer without --enable-oidc-issuer."
        )


def validate_workload_identity_updates(namespace: Namespace) -> None:
    if (
        namespace.enable_workload_identity is True
        and namespace.disable_workload_identity is True
    ):
        raise ArgumentUsageError(
            "Cannot specify both --enable-workload-identity and --disable-workload-identity "
            "simultaneously."
        )
