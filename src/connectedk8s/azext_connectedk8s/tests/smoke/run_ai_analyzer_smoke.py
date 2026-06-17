# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

r"""Smoke runner for invoking the real ConnectedK8s AI analyzer.

Example:
    python C:\repos\git\connectedk8s\src\connectedk8s\azext_connectedk8s\tests\smoke\run_ai_analyzer_smoke.py ^
      --diagnostic-folder "C:\Users\atchub\.azure\arc_diagnostic_logs\finetune14-Wed-Mar-11-13.26.56-2026" ^
      --cluster-name finetune14 ^
      --resource-group rg-finetune14 ^
      --model azure/gpt-4.1

This runner calls the real `analyze_diagnostics_with_ai()` implementation.
Required environment variables depend on the chosen model. For Azure OpenAI, set:
- AZURE_API_BASE
- AZURE_API_VERSION
- AZURE_API_KEY (unless passed with --api-key)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from azext_connectedk8s.ai_analyzer import analyze_diagnostics_with_ai


def _parse_checks(values: list[str] | None) -> dict[str, str]:
    if not values:
        return {"SmokeTest": "Passed"}

    checks: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Invalid --check value '{item}'. Expected format: CheckName=Status")
        name, status = item.split("=", 1)
        checks[name.strip()] = status.strip()
    return checks


def _latest_diagnostic_folder() -> str | None:
    """Return the most recently modified folder under ~/.azure/arc_diagnostic_logs/, or None."""
    base = os.path.join(os.path.expanduser("~"), ".azure", "arc_diagnostic_logs")
    if not os.path.isdir(base):
        return None
    candidates = [
        os.path.join(base, d)
        for d in os.listdir(base)
        if os.path.isdir(os.path.join(base, d))
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def _read_arm_snapshot(folder: str) -> dict:
    """Parse connected_cluster_resource_snapshot.txt if present, return empty dict on failure."""
    path = os.path.join(folder, "connected_cluster_resource_snapshot.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the real ConnectedK8s AI analyzer against a diagnostic folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "When run with no arguments, the runner auto-discovers the most recent diagnostic\n"
            "folder under ~/.azure/arc_diagnostic_logs/ and reads cluster name / resource group\n"
            "from the ARM snapshot inside it.  Set AZURE_API_BASE, AZURE_API_VERSION, and\n"
            "AZURE_API_KEY (or --api-key) before running against Azure OpenAI."
        ),
    )
    parser.add_argument("--diagnostic-folder", default=None, help="Path to the collected diagnostic logs folder. Defaults to the most recent folder under ~/.azure/arc_diagnostic_logs/.")
    parser.add_argument("--cluster-name", default=None, help="Connected cluster name. Defaults to value from ARM snapshot in the diagnostic folder.")
    parser.add_argument("--resource-group", default=None, help="Azure resource group name. Defaults to value from ARM snapshot in the diagnostic folder.")
    parser.add_argument("--model", default="azure/gpt-4.1", help="Model name, e.g. azure/gpt-4.1 or ollama/llama3.1. (default: azure/gpt-4.1)")
    parser.add_argument("--api-key", help="Optional API key. If omitted, analyzer uses environment variables.")
    parser.add_argument("--no-interactive", action="store_true", help="Pass through to analyzer.")
    parser.add_argument(
        "--check",
        action="append",
        dest="checks",
        help="Diagnostic check in the form CheckName=Status. Repeat to add more checks.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    # ── Auto-discover diagnostic folder ──────────────────────────────────
    if not args.diagnostic_folder:
        args.diagnostic_folder = _latest_diagnostic_folder()
        if not args.diagnostic_folder:
            parser.error(
                "No diagnostic folder found under ~/.azure/arc_diagnostic_logs/. "
                "Run 'az connectedk8s troubleshoot' first, or pass --diagnostic-folder."
            )
        print(f"[Smoke Test] Auto-discovered diagnostic folder: {args.diagnostic_folder}")

    if not os.path.isdir(args.diagnostic_folder):
        parser.error(f"Diagnostic folder not found: {args.diagnostic_folder}")

    # ── Auto-fill cluster-name and resource-group from ARM snapshot ───────
    if not args.cluster_name or not args.resource_group:
        snapshot = _read_arm_snapshot(args.diagnostic_folder)
        props = snapshot.get("properties", {})
        rg_from_id = ""
        arm_id = snapshot.get("id", "")
        # Extract resource group from ARM id: .../resourceGroups/<rg>/...
        parts = arm_id.split("/")
        try:
            rg_from_id = parts[parts.index("resourceGroups") + 1]
        except (ValueError, IndexError):
            pass

        if not args.cluster_name:
            args.cluster_name = snapshot.get("name") or os.path.basename(args.diagnostic_folder).split("-")[0]
            print(f"[Smoke Test] Auto-detected cluster-name: {args.cluster_name}")
        if not args.resource_group:
            args.resource_group = rg_from_id or "unknown-rg"
            print(f"[Smoke Test] Auto-detected resource-group: {args.resource_group}")

    if not args.cluster_name:
        parser.error("Could not determine cluster name. Pass --cluster-name explicitly.")
    if not args.resource_group:
        parser.error("Could not determine resource group. Pass --resource-group explicitly.")

    diagnostic_checks = _parse_checks(args.checks)

    print("[Smoke Test] Invoking analyze_diagnostics_with_ai with:")
    print(f"  diagnostic_folder={args.diagnostic_folder}")
    print(f"  cluster_name={args.cluster_name}")
    print(f"  resource_group={args.resource_group}")
    print(f"  model={args.model}")
    print(f"  api_key_provided={bool(args.api_key)}")
    print(f"  no_interactive={args.no_interactive}")
    print(f"  diagnostic_checks={diagnostic_checks}")

    analyze_diagnostics_with_ai(
        cmd=None,  # type: ignore[arg-type]
        diagnostic_folder=args.diagnostic_folder,
        diagnostic_checks=diagnostic_checks,
        cluster_name=args.cluster_name,
        resource_group=args.resource_group,
        model=args.model,
        api_key=args.api_key,
        no_interactive=args.no_interactive,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
