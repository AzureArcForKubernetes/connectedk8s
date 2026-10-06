# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import argparse
import os
import sys

import pytest
from azure.cli.core.azclierror import ArgumentUsageError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from azext_connectedk8s.action import (
    AddConfigurationProtectedSettings,
    AddConfigurationSettings,
)


@pytest.mark.parametrize(
    "action,option,dest",
    [
        (AddConfigurationSettings, "--configuration-settings", "configuration_settings"),
        (
            AddConfigurationProtectedSettings,
            "--configuration-protected-settings",
            "configuration_protected_settings",
        ),
    ],
)
def test_configuration_settings_combine_feature_names_case_insensitively(
    action,
    option,
    dest,
):
    parser = argparse.ArgumentParser()
    parser.add_argument(option, action=action, nargs="+")

    namespace = parser.parse_args(
        [
            option,
            "workloadidentity.version=1.0.7",
            "workloadIdentity.autoUpgradeMinorVersion=false",
        ]
    )

    assert getattr(namespace, dest) == {
        "workloadidentity": {
            "version": "1.0.7",
            "autoUpgradeMinorVersion": "false",
        }
    }


@pytest.mark.parametrize(
    "action,option",
    [
        (AddConfigurationSettings, "--configuration-settings"),
        (AddConfigurationProtectedSettings, "--configuration-protected-settings"),
    ],
)
@pytest.mark.parametrize(
    "duplicate",
    [
        "workloadidentity.version=1.0.8",
        "WorkloadIdentity.VERSION=1.0.8",
    ],
)
def test_configuration_settings_reject_duplicate_settings_case_insensitively(
    action,
    option,
    duplicate,
):
    parser = argparse.ArgumentParser()
    parser.add_argument(option, action=action, nargs="+")

    with pytest.raises(ArgumentUsageError, match=r"Duplicate .* setting"):
        parser.parse_args(
            [
                option,
                "workloadidentity.version=1.0.7",
                duplicate,
            ]
        )
