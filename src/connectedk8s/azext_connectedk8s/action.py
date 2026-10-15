# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
from __future__ import annotations

import argparse
from typing import Any

from azure.cli.core.azclierror import ArgumentUsageError


def _add_configuration_settings(
    settings: dict[str, dict[str, Any]],
    values: Any,
    option_string: str | None,
    setting_type: str,
) -> None:
    for item in values:
        try:
            key, value = item.split("=", 1)
            feature, setting = key.split(".")
        except ValueError as ex:
            raise ArgumentUsageError(
                f"Usage error: {option_string} "
                f"{setting_type}_setting_key={setting_type}_setting_value"
            ) from ex

        feature_key = next(
            (
                existing_feature
                for existing_feature in settings
                if existing_feature.casefold() == feature.casefold()
            ),
            feature,
        )
        feature_settings = settings.setdefault(feature_key, {})
        if any(
            existing_setting.casefold() == setting.casefold()
            for existing_setting in feature_settings
        ):
            raise ArgumentUsageError(
                f"Duplicate {setting_type} setting '{key}' is not allowed."
            )

        feature_settings[setting] = value


# pylint: disable=protected-access
# Access to protected members of argparse is necessary for custom action classes
class AddConfigurationSettings(argparse._AppendAction):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        config_settings = getattr(namespace, self.dest, None)
        if config_settings is None:
            config_settings = {}
        _add_configuration_settings(
            config_settings,
            values,
            option_string,
            "configuration",
        )
        setattr(namespace, self.dest, config_settings)


class AddConfigurationProtectedSettings(argparse._AppendAction):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        prot_settings = getattr(namespace, self.dest, None)
        if prot_settings is None:
            prot_settings = {}
        _add_configuration_settings(
            prot_settings,
            values,
            option_string,
            "configuration_protected",
        )
        setattr(namespace, self.dest, prot_settings)
