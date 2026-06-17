# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
from __future__ import annotations

import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from azext_connectedk8s.ai_analyzer import analyze_diagnostics_with_ai


class _FakeConsole:
    def __init__(self) -> None:
        self.messages: list[object] = []

    def print(self, *args, **kwargs) -> None:  # noqa: ANN003
        self.messages.append(args[0] if args else None)


class _FakePanel:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN003
        self.args = args
        self.kwargs = kwargs


class _FakeChoiceMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeChoiceMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeLiteLLMModule:
    def __init__(self) -> None:
        self.last_call = None

    def completion(self, **kwargs):  # noqa: ANN003
        self.last_call = kwargs
        return _FakeResponse("Mock AI summary for connectedk8s diagnostics")


def test_analyze_diagnostics_with_ai_direct_invocation(monkeypatch):
    diagnostic_folder = r"C:\Users\atchub\.azure\arc_diagnostic_logs\finetune14-Wed-Mar-11-13.26.56-2026"
    fake_litellm = _FakeLiteLLMModule()
    fake_console_module = types.ModuleType("rich.console")
    fake_console_module.Console = _FakeConsole
    fake_panel_module = types.ModuleType("rich.panel")
    fake_panel_module.Panel = _FakePanel

    monkeypatch.setenv("AZURE_API_BASE", "https://atchubtest.cognitiveservices.azure.com")
    monkeypatch.setenv("AZURE_API_VERSION", "2024-05-01-preview")
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    monkeypatch.setitem(sys.modules, "rich.console", fake_console_module)
    monkeypatch.setitem(sys.modules, "rich.panel", fake_panel_module)
    monkeypatch.setattr("azext_connectedk8s.ai_analyzer.os.path.exists", lambda path: path == diagnostic_folder)
    monkeypatch.setattr(
        "azext_connectedk8s.ai_analyzer.os.listdir",
        lambda path: ["cluster-info.txt", "config-agent.log", "diagnoser_output.txt"],
    )

    saved = {}

    def _fake_save_analysis_to_file(folder: str, analysis: str) -> None:
        saved["folder"] = folder
        saved["analysis"] = analysis

    monkeypatch.setattr(
        "azext_connectedk8s.ai_analyzer._save_analysis_to_file",
        _fake_save_analysis_to_file,
    )

    analyze_diagnostics_with_ai(
        cmd=object(),
        diagnostic_folder=diagnostic_folder,
        diagnostic_checks={
            "Fetch_Connected_Cluster_Resource": "Passed",
            "Retrieve_Arc_Agents_Logs": "Incomplete",
            "Diagnoser_Check": "Passed",
        },
        cluster_name="finetune14",
        resource_group="rg-finetune14",
        model="azure/gpt-4.1",
        api_key=None,
        no_interactive=False,
    )

    assert fake_litellm.last_call is not None
    assert fake_litellm.last_call["model"] == "azure/gpt-4.1"
    assert saved["folder"] == diagnostic_folder
    assert "Mock AI summary" in saved["analysis"]
