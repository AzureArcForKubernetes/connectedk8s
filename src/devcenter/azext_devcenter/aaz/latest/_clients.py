# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
#
# Code generated by aaz-dev-tools
# --------------------------------------------------------------------------------------------

# pylint: skip-file
# flake8: noqa

from azure.cli.core.aaz import *


@register_client("AAZMicrosoftDevcenterDataPlaneClient_devcenter")
class AAZMicrosoftDevcenterDataPlaneClient(AAZBaseClient):
    _CLOUD_HOST_TEMPLATES = {
        CloudNameEnum.AzureCloud: "https://{endpoint}",
    }

    _AAD_CREDENTIAL_SCOPES = [
        "https://devcenter.azure.com/.default",
    ]

    @classmethod
    def _build_base_url(cls, ctx, **kwargs):
        endpoint = None
        if not endpoint:
            endpoint = cls._CLOUD_HOST_TEMPLATES.get(ctx.cli_ctx.cloud.name, None)
        return endpoint

    @classmethod
    def _build_configuration(cls, ctx, credential, **kwargs):
        return AAZClientConfiguration(
            credential=credential,
            credential_scopes=cls._AAD_CREDENTIAL_SCOPES,
            **kwargs
        )


class _AAZMicrosoftDevcenterDataPlaneClientHelper:
    """Helper class for AAZMicrosoftDevcenterDataPlaneClient"""


__all__ = [
    "AAZMicrosoftDevcenterDataPlaneClient",
]
