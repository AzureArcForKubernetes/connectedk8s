# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from azext_connectedk8s._utils import (
    get_mcr_path,
    process_helm_error_detail,
    redact_sensitive_fields_from_string,
    remove_rsa_private_key,
    scrub_proxy_url,
    should_use_secret_injection_flow,
)


def test_remove_rsa_private_key():
    input_text = "Error: -----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA7\n-----END RSA PRIVATE KEY-----"
    expected_output = "Error: [RSA PRIVATE KEY REMOVED]"
    assert remove_rsa_private_key(input_text) == expected_output

    input_text_no_key = "Error: No RSA key here"
    assert remove_rsa_private_key(input_text_no_key) == input_text_no_key


def test_scrub_proxy_url_with_url():
    input_text = "text with proxy URL http://proxy:pass@example.com:8080 in it"
    expected_output = (
        "text with proxy URL http://[REDACTED]:[REDACTED]@example.com:8080 in it"
    )
    assert scrub_proxy_url(input_text) == expected_output


def test_scrub_proxy_url_without_url():
    input_text = "text without proxy URL"
    assert scrub_proxy_url(input_text) == input_text


def test_process_helm_error_detail():
    input_text = (
        "Some text\n-----BEGIN RSA PRIVATE KEY-----\nkey\n-----END RSA PRIVATE KEY-----\n"
        "with proxy URL http://proxy:pass@example.com:8080 in it"
    )
    expected_output = (
        "Some text\n[RSA PRIVATE KEY REMOVED]\n"
        "with proxy URL http://[REDACTED]:[REDACTED]@example.com:8080 in it"
    )
    assert process_helm_error_detail(input_text) == expected_output


def test_process_helm_error_detail_no_changes():
    input_text = "Some text without RSA key or proxy URL"
    assert process_helm_error_detail(input_text) == input_text


def test_redact_sensitive_fields_from_string():
    input_text = "username: admin\npassword: secret\ntoken: abc123"
    expected_output = "username: [REDACTED]\npassword: [REDACTED]\ntoken: [REDACTED]"
    assert redact_sensitive_fields_from_string(input_text) == expected_output

    input_text_no_sensitive = "No sensitive data here"
    assert (
        redact_sensitive_fields_from_string(input_text_no_sensitive)
        == input_text_no_sensitive
    )

    input_text_partial = "username: user1\nhello_data: safe\npassword: mypass"
    expected_output_partial = (
        "username: [REDACTED]\nhello_data: safe\npassword: [REDACTED]"
    )
    assert (
        redact_sensitive_fields_from_string(input_text_partial)
        == expected_output_partial
    )


def test_get_mcr_path():
    input_active_directory = "login.microsoftonline.com"
    expected_output = "mcr.microsoft.com"
    assert get_mcr_path(input_active_directory) == expected_output

    input_active_directory = "login.microsoftonline.us"
    expected_output = "mcr.microsoft.com"
    assert get_mcr_path(input_active_directory) == expected_output

    input_active_directory = "login.chinacloudapi.cn"
    expected_output = "mcr.microsoft.com"
    assert get_mcr_path(input_active_directory) == expected_output

    input_active_directory = "https://login.microsoftonline.microsoft.foo"
    expected_output = "mcr.microsoft.foo"
    assert get_mcr_path(input_active_directory) == expected_output

    input_active_directory = "https://login.microsoftonline.some.cloud.bar"
    expected_output = "mcr.microsoft.some.cloud.bar"
    assert get_mcr_path(input_active_directory) == expected_output


@pytest.mark.parametrize(
    "release_train,agent_version,expected",
    [
        # Stable train, agents older than 1.35.3 must use the legacy flow
        # (helm value injection) to avoid zeroing out the secret.
        ("stable", "1.35.2", False),
        ("stable", "1.34.9", False),
        ("stable", "1.20.0", False),
        ("STABLE", "1.14.0", False),
        # Stable train at or above the cutoff uses the secure flow.
        ("stable", "1.35.3", True),
        ("stable", "1.36.2", True),
        ("stable", "2.0.0", True),
        # Preview train uses 1.35.3-preview as the cutoff (same scheme).
        ("preview", "1.34.0", False),
        ("preview", "1.35.2-preview", False),
        ("preview", "1.35.3-preview", True),
        ("preview", "1.36.0-preview", True),
        ("PREVIEW", "1.20.0", False),
        # Dev-suffixed agent versions always use the secure flow, regardless of
        # the release train DP attributed them to.
        ("preview", "0.2.5738-dev", True),
        ("stable", "0.2.6689-dev", True),
        ("STABLE", "1.34.0-DEV", True),
        (None, "0.2.5738-dev", True),
        # Missing version on a gated train -> safe default (legacy flow).
        ("stable", None, False),
        ("preview", "", False),
        # Missing release train defaults to "stable".
        (None, "1.34.0", False),
        (None, "1.35.3", True),
        # Unparseable version on a gated train -> safe default (legacy flow).
        ("stable", "not-a-version", False),
    ],
)
def test_should_use_secret_injection_flow(release_train, agent_version, expected):
    assert (
        should_use_secret_injection_flow(release_train, agent_version) is expected
    )


if __name__ == "__main__":
    pytest.main()
