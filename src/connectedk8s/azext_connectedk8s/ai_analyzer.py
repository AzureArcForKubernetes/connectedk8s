# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

"""AI-powered diagnostic log analysis for Connected Kubernetes clusters."""

from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING, Any

from knack.log import get_logger
from knack.util import CLIError

if TYPE_CHECKING:
    from azure.cli.core.commands import CLICommand

logger = get_logger(__name__)

# ── Token-budget constants ──────────────────────────────────────────────────
_MAX_CHARS_SMALL_FILE = 3000     # max chars read from each small structured file
_MAX_CHARS_AGENT_LOG = 4000      # max chars per agent log file after head+errors+tail
_MAX_AGENT_LOG_DIRS = 5          # max agent pod dirs to include in the prompt
_LARGE_FILE_THRESHOLD = 1024 * 1024  # 1 MB – use head/tail strategy above this
_MAX_ERROR_LINES_PER_FILE = 50   # max error/warning lines extracted per log file
_MAX_TOTAL_PROMPT_CHARS = 28000  # hard cap on the whole diagnostic section (~7k tokens)

# Keywords used to identify interesting lines in agent logs
_LOG_ERROR_KEYWORDS = ("error", "warning", "warn", "fail", "exception", "fatal", "critical", "panic")

# Small structured files in the root diagnostic folder that are fully read
_ROOT_STRUCTURED_FILES = [
    "diagnoser_output.txt",
    "agent_state.txt",
    "outbound_network_connectivity_check.txt",
    "dns_check.txt",
    "k8s_cluster_info.txt",
    "helm_values_azure_arc.txt",
    "metadata_cr_snapshot.txt",
    "kube_aad_proxy_cr_snapshot.txt",
    "azure-arc-secrets.txt",
    "connected_cluster_resource_snapshot.txt",
]

# Priority order for agent log dirs (most-likely-to-have-issues first)
_AGENT_PRIORITY_PREFIXES = [
    "clusteridentityoperator",
    "controller-manager",
    "clusterconnect-agent",
    "config-agent",
    "extension-manager",
    "kube-aad-proxy",
]

# ── Domain-knowledge system prompt ──────────────────────────────────────────
_ARC_SYSTEM_PROMPT = """\
You are an expert Azure Arc-enabled Kubernetes SRE with deep knowledge of the Arc
onboarding flow, agent architecture, and common failure modes. Always ground your
analysis in evidence from the diagnostic data provided — never guess.

## ARC ONBOARDING FLOW (the sequence that must succeed for a cluster to be Connected)

The `az connectedk8s connect` command executes the following ordered steps. A failure
at any step blocks all subsequent steps:

  Step 1 — ARM resource creation
    The ConnectedCluster resource is registered in Azure. If this fails the cluster
    never appears in the portal.

  Step 2 — Helm chart deployment (azure-arc namespace)
    The Arc Helm chart is applied to the cluster. All Arc agent pods are created here.
    Failures: insufficient RBAC on the deploying identity, Helm version mismatch,
    unreachable container registry (mcr.microsoft.com).

  Step 3 — clusteridentityoperator provisions the MSI certificate
    THIS IS THE MOST CRITICAL STEP. The operator contacts the Azure Identity endpoint
    to obtain a Managed Service Identity (MSI) certificate and stores it as a Kubernetes
    secret. ALL other agents depend on this certificate to authenticate with Azure.
    Failures: outbound HTTPS blocked to login.microsoftonline.com or
    <region>.dp.kubernetesconfiguration.azure.com, RBAC missing on the service principal,
    or the certificate has expired and rotation failed (causes restart loops).

  Step 4 — clusterconnect-agent establishes the outbound relay connection
    Opens a persistent outbound WebSocket to the Arc relay endpoint
    (<cluster-uid>.dp.kubernetesconfiguration.azure.com). This sets connectivity
    status to "Connected" in ARM. Failures: proxy/firewall blocking outbound 443,
    MSI cert not yet provisioned (dependency on Step 3), DNS resolution failure.

  Step 5 — resource-sync-agent syncs cluster state to ARM
    Reports node count, Kubernetes version, agent version back to the ARM resource.
    Failure here causes stale metadata in the portal but does not break connectivity.

  Step 6 — config-agent and controller-manager activate GitOps
    Only relevant if GitOps/Flux configurations are attached. Failures here do not
    affect basic Arc connectivity.

  Step 7 — extension-manager activates installed extensions
    Manages lifecycle of cluster extensions (e.g. monitoring, defender, flux).
    Completely independent of basic Arc connectivity.

## AGENT DEPENDENCY CHAIN (cascade logic)

  clusteridentityoperator (MSI cert)
    └─▶ clusterconnect-agent (relay connection)  ← connectivityStatus gated here
          └─▶ resource-sync-agent (ARM metadata sync)
          └─▶ config-agent + controller-manager (GitOps)
          └─▶ extension-manager (extensions)
    └─▶ kube-aad-proxy (AAD auth for kubectl access)
    └─▶ cluster-metadata-operator (cluster info reporting)

  Rule: If clusteridentityoperator is unhealthy or restarting, ALL downstream agents
  will eventually fail even if they currently show Running.

## KNOWN FAILURE PATTERNS AND THEIR SIGNATURES

  Pattern A — Unsupported agent version
    Signal: diagnoser_output.txt says "older agent version that is not supported"
    or agentAutoUpgrade is Disabled and agentVersion is outside the N-2 support window.
    Impact: Microsoft will not diagnose or fix issues on unsupported versions.
    Fix: `az connectedk8s upgrade` or enable auto-upgrade.

  Pattern B — MSI certificate expired or near expiry
    Signal: managedIdentityCertificateExpirationTime within 30 days, OR
    clusteridentityoperator restart count > 5, OR errors containing
    "certificate" / "x509" / "token" / "unauthorized" in identity operator logs.
    Impact: cluster goes Offline after cert expiry; all agent auth fails.
    Fix: `az connectedk8s update` to force cert rotation, or check outbound
    connectivity to login.microsoftonline.com.

  Pattern C — Connectivity Offline / relay unreachable
    Signal: connectivityStatus = Offline or Expired in connected_cluster_resource_snapshot.txt,
    errors in clusterconnect-agent logs with "dial", "connection refused", "timeout",
    or "TLS handshake".
    Impact: cluster invisible from Azure portal; kubectl proxy and cluster-connect broken.
    Fix: verify outbound HTTPS to *.dp.kubernetesconfiguration.azure.com and
    *.servicebus.windows.net on port 443.

  Pattern D — RBAC / permissions failure
    Signal: "forbidden" errors in controller-manager or config-agent logs,
    "cannot list resource", "User system:serviceaccount:azure-arc:... is not allowed".
    Impact: GitOps configs fail to apply; extension operations blocked.
    Fix: reapply Arc RBAC ClusterRoleBindings via Helm upgrade.

  Pattern E — Outbound network blocked (partial)
    Signal: outbound_network_connectivity_check.txt shows failure, OR DNS errors
    in dns_check.txt, OR "i/o timeout" / "no such host" in agent logs.
    Impact: depends on which endpoint is blocked (see onboarding flow above).
    Fix: whitelist required Arc endpoints per
    https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements

  Pattern F — Pod restart loop
    Signal: Restart_Counts > 3 in agent_state.txt for any container.
    Impact depends on which pod: identity operator restarts → cascade failure.
    Fix: read the pod logs (the agent log files) for the crash reason.

  Pattern G — Helm values / configuration drift
    Signal: helm_values_azure_arc.txt shows wrong subscriptionId, resourceGroupName,
    resourceName, tenantId, or location.
    Impact: agents authenticate to wrong ARM resource; silent connectivity failure.
    Fix: `az connectedk8s delete` and re-onboard, or `az connectedk8s update`.

## LOG ANALYSIS PRIORITY ORDER (read in this sequence)

  1. diagnoser_output.txt       — top-level human-readable verdict, read first
  2. agent_state.txt            — pod health and restart counts for all agents
  3. connected_cluster_resource_snapshot.txt — connectivityStatus, cert expiry, version
  4. outbound_network_connectivity_check.txt — basic reachability
  5. dns_check.txt              — DNS resolution health
  6. clusteridentityoperator logs — MSI cert provisioning errors (most common root cause)
  7. clusterconnect-agent logs  — relay connection errors
  8. controller-manager logs    — RBAC and GitOps errors
  9. config-agent logs          — GitOps config application errors
  10. metadata_cr_snapshot.txt  — cluster CR state as seen from inside the cluster
  11. helm_values_azure_arc.txt — configuration drift
  12. kube_aad_proxy_cr_snapshot.txt — AAD proxy cert status

## RESPONSE RULES

- Always cite the specific file and line content that supports each finding.
- If a finding in one file is contradicted by another, call out the contradiction.
- Severity levels: Critical (cluster offline or cert expired), High (imminent failure
  or restart loop), Medium (degraded function), Low (informational).
- If the root cause is Pattern A (unsupported version), state it first before anything
  else since it invalidates all other analysis.
- Provide exact az CLI commands for every recommended fix where they exist.
"""


def analyze_diagnostics_with_ai(
    cmd: CLICommand,
    diagnostic_folder: str,
    diagnostic_checks: dict[str, str],
    cluster_name: str,
    resource_group: str,
    model: str | None = None,
    api_key: str | None = None,
    no_interactive: bool = False,
) -> None:
    """
    Analyze collected diagnostic logs using AI/LLM.
    
    Args:
        cmd: Azure CLI command context
        diagnostic_folder: Path to folder containing collected diagnostic logs
        diagnostic_checks: Dictionary of diagnostic check results
        cluster_name: Name of the connected cluster
        resource_group: Resource group name
        model: LLM model to use (e.g., 'azure/gpt-4o', 'gpt-4o')
        api_key: Optional API key for LLM provider
        no_interactive: Run in non-interactive mode
    """
    logger.warning(
        "[AI Analysis] Args: cluster_name=%s, resource_group=%s, diagnostic_folder=%s, "
        "model=%s, no_interactive=%s, api_key_provided=%s, diagnostic_checks_count=%d",
        cluster_name,
        resource_group,
        diagnostic_folder,
        model,
        no_interactive,
        api_key is not None,
        len(diagnostic_checks),
    )

    # Check Python version
    if sys.version_info < (3, 9):
        logger.warning(
            "[AI Analysis] Skipped: Requires Python 3.9 or higher. Current version: %s.%s",
            sys.version_info.major,
            sys.version_info.minor,
        )
        return

    # Validate model is provided
    if not model:
        logger.warning(
            "[AI Analysis] Skipped: --model parameter is required for AI analysis. "
            "Example: --model azure/gpt-4o or --model gpt-4o"
        )
        return

    try:
        # Import LiteLLM
        try:
            import litellm
            from rich.console import Console
            from rich.panel import Panel
        except ImportError as e:
            logger.warning(
                "[AI Analysis] Skipped: Required packages not available. "
                "This may occur if the extension was installed with an older Python version. "
                "Error: %s",
                str(e),
            )
            return

        # Suppress LiteLLM debug logs
        logging.getLogger("LiteLLM").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

        console = Console()

        logger.warning("\n[AI Analysis] Analyzing diagnostics with AI...\n")

        # Set API key if provided
        if api_key:
            if model.startswith("azure/"):
                os.environ["AZURE_API_KEY"] = api_key
            else:
                os.environ["OPENAI_API_KEY"] = api_key

        # Validate environment variables based on model type
        _validate_environment_variables(model)

        # Prepare diagnostic summary
        summary = _prepare_diagnostic_summary(diagnostic_folder, diagnostic_checks)

        # Auto-deduce incident context from the collected data
        incident_context = _deduce_incident_context(diagnostic_folder, diagnostic_checks)

        # Build prompt
        prompt = _build_analysis_prompt(
            cluster_name, resource_group, summary, diagnostic_checks, incident_context
        )

        # Call LLM
        console.print("[yellow]Sending diagnostics to LLM for analysis...[/yellow]")
        
        try:
            response = litellm.completion(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": _ARC_SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
            )

            analysis = response.choices[0].message.content

            # Display results
            console.print()
            console.print(
                Panel(
                    analysis,
                    title="[bold blue]🤖 AI Analysis Results[/bold blue]",
                    border_style="blue",
                    padding=(1, 2),
                )
            )
            console.print()

            # Save analysis to file
            _save_analysis_to_file(diagnostic_folder, analysis)

            logger.warning("[AI Analysis] Analysis completed and saved to: %s/ai_analysis.txt\n", diagnostic_folder)

        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api" in error_msg.lower():
                logger.error(
                    "[AI Analysis] Authentication error: %s\n"
                    "Please check your environment variables:\n"
                    "  - For Azure OpenAI: AZURE_API_BASE, AZURE_API_VERSION, AZURE_API_KEY\n"
                    "  - For OpenAI: OPENAI_API_KEY\n"
                    "  - For Ollama: OLLAMA_API_BASE (e.g., http://localhost:11434)",
                    error_msg,
                )
            else:
                logger.error("[AI Analysis] Error during analysis: %s", error_msg)
            raise

    except Exception as e:
        logger.error("[AI Analysis] Failed: %s", str(e))
        logger.warning(
            "[AI Analysis] The diagnostic logs have been collected successfully. "
            "AI analysis failed but you can still use the collected logs for manual troubleshooting."
        )


def _validate_environment_variables(model: str) -> None:
    """Validate that required environment variables are set for the specified model."""
    if model.startswith("azure/"):
        if not os.getenv("AZURE_API_BASE"):
            raise CLIError(
                "Azure OpenAI requires AZURE_API_BASE environment variable. "
                "Example: export AZURE_API_BASE='https://your-resource.openai.azure.com/'"
            )
        if not os.getenv("AZURE_API_VERSION"):
            logger.warning(
                "AZURE_API_VERSION not set, using default. "
                "Recommended: export AZURE_API_VERSION='2025-01-01-preview'"
            )
    elif model.startswith("ollama/"):
        if not os.getenv("OLLAMA_API_BASE"):
            logger.warning(
                "OLLAMA_API_BASE not set, using default http://localhost:11434. "
                "Set it if your Ollama is running elsewhere."
            )
    elif not model.startswith("ollama/"):
        # Likely OpenAI or other provider
        if not os.getenv("OPENAI_API_KEY") and not os.getenv("AZURE_API_KEY"):
            raise CLIError(
                "API key required. Set OPENAI_API_KEY environment variable or use --api-key parameter."
            )


# ── File reading helpers ────────────────────────────────────────────────────

def _read_file_safely(path: str, max_chars: int = _MAX_CHARS_SMALL_FILE) -> str:
    """Read a file up to *max_chars*, appending a truncation note if needed."""
    try:
        size = os.path.getsize(path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
        if size > max_chars:
            content += f"\n[... truncated — total file size: {size:,} bytes ...]"
        return content
    except Exception as e:  # noqa: BLE001
        return f"[Could not read: {e}]"


def _read_tail_lines(path: str, n: int) -> list[str]:
    """Return the last *n* non-empty lines from *path* without loading the whole file."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
            chunk_size = min(file_size, max(n * 300, 8192))
            f.seek(max(0, file_size - chunk_size))
            chunk = f.read()
        lines = chunk.decode("utf-8", errors="replace").splitlines()
        return [l for l in lines[-n:] if l.strip()]
    except Exception:  # noqa: BLE001
        return []


def _extract_error_and_tail_from_log(
    path: str,
    head_lines: int = 20,
    tail_lines: int = 30,
    max_error_lines: int = _MAX_ERROR_LINES_PER_FILE,
    max_chars: int = _MAX_CHARS_AGENT_LOG,
) -> str:
    """
    Build a compact summary of a potentially large log file:
      - first *head_lines* lines
      - up to *max_error_lines* lines matching error/warning keywords
      - last *tail_lines* lines

    For files above *_LARGE_FILE_THRESHOLD*, error scanning is limited to the
    first 5 000 lines so we avoid loading dozens of megabytes into memory.
    """
    try:
        size = os.path.getsize(path)
        parts: list[str] = []

        if size > _LARGE_FILE_THRESHOLD:
            head: list[str] = []
            error_lines: list[str] = []
            more_errors = False

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    stripped = line.rstrip()
                    if i < head_lines:
                        head.append(stripped)
                    if len(error_lines) < max_error_lines and any(
                        k in line.lower() for k in _LOG_ERROR_KEYWORDS
                    ):
                        error_lines.append(stripped)
                    elif len(error_lines) >= max_error_lines:
                        more_errors = True
                        break
                    if i >= 5000:
                        break  # stop scanning large files after 5k lines

            tail = _read_tail_lines(path, tail_lines)
            total_desc = f"size: {size:,} bytes (large file — errors scanned in first 5 000 lines)"
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            total = len(all_lines)
            head = [l.rstrip() for l in all_lines[:head_lines]]
            tail = [l.rstrip() for l in all_lines[max(head_lines, total - tail_lines):]]
            error_lines = []
            more_errors = False
            for line in all_lines:
                if any(k in line.lower() for k in _LOG_ERROR_KEYWORDS):
                    error_lines.append(line.rstrip())
                    if len(error_lines) >= max_error_lines:
                        more_errors = True
                        break
            total_desc = f"{total} lines, {size:,} bytes"

        header = f"(File: {os.path.basename(path)}, {total_desc})"
        if head:
            parts.append(f"[First {len(head)} lines]\n" + "\n".join(head))
        if error_lines:
            suffix = " — more exist, limit reached" if more_errors else ""
            parts.append(
                f"[Error/Warning lines: {len(error_lines)} found{suffix}]\n"
                + "\n".join(error_lines)
            )
        if tail:
            parts.append(f"[Last {len(tail)} lines]\n" + "\n".join(tail))

        result = header + "\n" + "\n\n".join(parts)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n[... content truncated to fit context window ...]"
        return result
    except Exception as e:  # noqa: BLE001
        return f"[Could not read {os.path.basename(path)}: {e}]"


# ── Diagnostic summary (feeds the LLM prompt) ───────────────────────────────

def _prepare_diagnostic_summary(diagnostic_folder: str, diagnostic_checks: dict[str, str]) -> str:
    """
    Build a rich, content-filled diagnostic summary to send to the LLM.

    Sections produced (in order):
      1. Root structured files  (diagnoser output, agent state, connectivity, etc.)
      2. Arc deployment logs    (one per agent deployment, each ~1 KB)
      3. Arc agent runtime logs (head + error lines + tail for each agent pod)
    """
    sections: list[str] = []

    # ── 1. Root structured files ──────────────────────────────────────────
    root_parts: list[str] = []
    for fname in _ROOT_STRUCTURED_FILES:
        fpath = os.path.join(diagnostic_folder, fname)
        if os.path.exists(fpath):
            content = _read_file_safely(fpath, max_chars=_MAX_CHARS_SMALL_FILE)
            root_parts.append(f"### {fname}\n{content}")
    if root_parts:
        sections.append("## ROOT DIAGNOSTIC FILES\n\n" + "\n\n".join(root_parts))

    # ── 2. Deployment logs ────────────────────────────────────────────────
    deploy_dir = os.path.join(diagnostic_folder, "arc_deployment_logs")
    if os.path.isdir(deploy_dir):
        deploy_parts: list[str] = []
        for fname in sorted(os.listdir(deploy_dir)):
            fpath = os.path.join(deploy_dir, fname)
            if os.path.isfile(fpath):
                content = _read_file_safely(fpath, max_chars=2000)
                deploy_parts.append(f"### {fname}\n{content}")
        if deploy_parts:
            sections.append("## ARC DEPLOYMENT STATUS LOGS\n\n" + "\n\n".join(deploy_parts))

    # ── 3. Agent runtime logs ─────────────────────────────────────────────
    agents_dir = os.path.join(diagnostic_folder, "arc_agents_logs")
    if os.path.isdir(agents_dir):
        agent_dirs = [
            d for d in os.listdir(agents_dir)
            if os.path.isdir(os.path.join(agents_dir, d))
        ]

        def _agent_priority(d: str) -> int:
            for i, prefix in enumerate(_AGENT_PRIORITY_PREFIXES):
                if d.startswith(prefix):
                    return i
            return len(_AGENT_PRIORITY_PREFIXES)

        agent_dirs_sorted = sorted(agent_dirs, key=_agent_priority)[:_MAX_AGENT_LOG_DIRS]
        agent_sections: list[str] = []

        for agent_dir in agent_dirs_sorted:
            agent_path = os.path.join(agents_dir, agent_dir)
            log_parts: list[str] = []

            for fname in sorted(os.listdir(agent_path)):
                if fname == "fluent-bit.txt":
                    continue  # fluent-bit logs are mostly infra noise
                fpath = os.path.join(agent_path, fname)
                if os.path.isfile(fpath):
                    content = _extract_error_and_tail_from_log(fpath)
                    log_parts.append(f"#### {fname}\n{content}")

            if log_parts:
                agent_sections.append(f"### Agent pod: {agent_dir}\n\n" + "\n\n".join(log_parts))

        if agent_sections:
            sections.append("## ARC AGENT RUNTIME LOGS\n\n" + "\n\n".join(agent_sections))

    result = "\n\n".join(sections)

    if len(result) > _MAX_TOTAL_PROMPT_CHARS:
        result = (
            result[:_MAX_TOTAL_PROMPT_CHARS]
            + "\n\n[DIAGNOSTIC CONTENT TRUNCATED — size exceeded context budget]"
        )

    return result


def _deduce_incident_context(diagnostic_folder: str, diagnostic_checks: dict[str, str]) -> str:
    """
    Auto-deduce the incident context from the diagnostic data so the user does not
    need to provide it manually. Extracts:
      - connectivity status and agent version from the ARM snapshot
      - cert expiry countdown
      - pod restart summary
      - any warning from diagnoser_output
      - which automated checks failed
    Returns a markdown-formatted string to embed in the prompt.
    """
    import json
    import re
    from datetime import datetime, timezone

    lines: list[str] = []

    # ── 1. ARM resource snapshot ──────────────────────────────────────────
    snapshot_path = os.path.join(diagnostic_folder, "connected_cluster_resource_snapshot.txt")
    if os.path.exists(snapshot_path):
        try:
            with open(snapshot_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            props = data.get("properties", {})

            connectivity = props.get("connectivityStatus", "Unknown")
            agent_version = props.get("agentVersion", "Unknown")
            k8s_version = props.get("kubernetesVersion", "Unknown")
            node_count = props.get("totalNodeCount", "?")
            auto_upgrade = props.get("arcAgentProfile", {}).get("agentAutoUpgrade", "Unknown")
            last_connected = props.get("lastConnectivityTime", "")
            cert_expiry_str = props.get("managedIdentityCertificateExpirationTime", "")

            lines.append(f"- **Connectivity status**: {connectivity}")
            lines.append(f"- **Agent version**: {agent_version} (auto-upgrade: {auto_upgrade})")
            lines.append(f"- **Kubernetes version**: {k8s_version} on {node_count} node(s)")
            if last_connected:
                lines.append(f"- **Last connected time**: {last_connected}")

            if cert_expiry_str:
                try:
                    # Parse ISO 8601 with or without fractional seconds
                    cert_expiry_str_clean = re.sub(r"\.\d+", "", cert_expiry_str.rstrip("Z")) + "+00:00"
                    expiry_dt = datetime.fromisoformat(cert_expiry_str_clean)
                    now = datetime.now(timezone.utc)
                    days_left = (expiry_dt - now).days
                    severity = (
                        "🔴 CRITICAL" if days_left < 7
                        else "🟠 HIGH" if days_left < 30
                        else "🟡 MEDIUM" if days_left < 60
                        else "🟢 OK"
                    )
                    lines.append(
                        f"- **MSI cert expiry**: {cert_expiry_str} "
                        f"({days_left} days from now — {severity})"
                    )
                except Exception:
                    lines.append(f"- **MSI cert expiry**: {cert_expiry_str} (could not parse date)")
        except Exception as e:
            lines.append(f"- ARM snapshot could not be parsed: {e}")

    # ── 2. Diagnoser verdict ──────────────────────────────────────────────
    diag_path = os.path.join(diagnostic_folder, "diagnoser_output.txt")
    if os.path.exists(diag_path):
        try:
            with open(diag_path, "r", encoding="utf-8", errors="replace") as f:
                diag_text = f.read().strip()
            if diag_text:
                lines.append(f"- **Diagnoser verdict**: {diag_text.splitlines()[0]}")
        except Exception:
            pass

    # ── 3. Pod restart summary ────────────────────────────────────────────
    state_path = os.path.join(diagnostic_folder, "agent_state.txt")
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8", errors="replace") as f:
                state_text = f.read()
            restart_hits = re.findall(r"(\S+)\s*:\s*Ready\s*=\s*(\w+),\s*Restart_Counts\s*=\s*(\d+)", state_text)
            restarting = [
                f"{container} (restarts={count}, ready={ready})"
                for container, ready, count in restart_hits
                if int(count) > 0
            ]
            not_ready = [
                f"{container} (ready={ready})"
                for container, ready, count in restart_hits
                if ready.lower() != "true"
            ]
            if restarting:
                lines.append(f"- **Pods with restarts**: {', '.join(restarting)}")
            if not_ready:
                lines.append(f"- **Pods not ready**: {', '.join(not_ready)}")
            if not restarting and not not_ready:
                lines.append("- **Pod health**: all containers ready, zero restarts")
        except Exception:
            pass

    # ── 4. Automated check failures ───────────────────────────────────────
    failed = [k for k, v in diagnostic_checks.items() if v not in ("Passed", "passed")]
    passed_count = len(diagnostic_checks) - len(failed)
    if failed:
        lines.append(f"- **Failed checks ({len(failed)})**: {', '.join(failed)}")
    elif diagnostic_checks:
        lines.append(f"- **All {passed_count} automated checks passed**")

    # ── 5. Network checks ─────────────────────────────────────────────────
    net_path = os.path.join(diagnostic_folder, "outbound_network_connectivity_check.txt")
    if os.path.exists(net_path):
        try:
            with open(net_path, "r", encoding="utf-8", errors="replace") as f:
                net_text = f.read().strip()
            status = "PASSED" if "passed" in net_text.lower() else "FAILED"
            lines.append(f"- **Outbound connectivity**: {status}")
        except Exception:
            pass

    dns_path = os.path.join(diagnostic_folder, "dns_check.txt")
    if os.path.exists(dns_path):
        try:
            with open(dns_path, "r", encoding="utf-8", errors="replace") as f:
                dns_text = f.read().strip()
            status = "PASSED" if "passed" in dns_text.lower() else "FAILED"
            lines.append(f"- **DNS check**: {status}")
        except Exception:
            pass

    if not lines:
        return "(No auto-deduced context available — diagnostic files may be missing.)"

    return "\n".join(lines)


def _build_analysis_prompt(
    cluster_name: str,
    resource_group: str,
    summary: str,
    diagnostic_checks: dict[str, str],
    incident_context: str = "",
) -> str:
    """Build the LLM prompt embedding real diagnostic content."""
    # Classify check results
    passed_checks: list[str] = []
    failed_checks: list[str] = []
    incomplete_checks: list[str] = []

    for check_name, status in diagnostic_checks.items():
        if status == "Passed":
            passed_checks.append(check_name)
        elif status == "Failed":
            failed_checks.append(check_name)
        else:
            incomplete_checks.append(check_name)

    checks_section = ""
    if passed_checks:
        checks_section += f"\n✅ Passed ({len(passed_checks)}):\n"
        for c in passed_checks[:8]:
            checks_section += f"  - {c}\n"
        if len(passed_checks) > 8:
            checks_section += f"  ... and {len(passed_checks) - 8} more\n"
    if failed_checks:
        checks_section += f"\n❌ Failed ({len(failed_checks)}):\n"
        for c in failed_checks:
            checks_section += f"  - {c}\n"
    if incomplete_checks:
        checks_section += f"\n⚠️ Incomplete ({len(incomplete_checks)}):\n"
        for c in incomplete_checks[:8]:
            checks_section += f"  - {c}\n"
        if len(incomplete_checks) > 8:
            checks_section += f"  ... and {len(incomplete_checks) - 8} more\n"
    if not diagnostic_checks:
        checks_section = "\n(No automated checks were recorded.)\n"

    incident_section = ""
    if incident_context:
        incident_section = f"""\n## AUTO-DEDUCED INCIDENT CONTEXT\n(Extracted from diagnostic files — no user input required)\n{incident_context}\n"""

    prompt = f"""Analyze the complete diagnostic data below for Azure Arc-enabled Kubernetes cluster '{cluster_name}' (resource group: '{resource_group}') and produce an actionable troubleshooting report.

Use the Arc onboarding flow, agent dependency chain, and known failure patterns from your system instructions to interpret the evidence.
{incident_section}
## AUTOMATED CHECK RESULTS
{checks_section}

## FULL DIAGNOSTIC DATA
The following sections contain the actual content of diagnostic files and log excerpts collected from the cluster. Each agent log section shows: the first lines (startup context), any error/warning lines found, and the last lines (most recent activity).

{summary}

---

## ANALYSIS REQUEST

Based on ALL of the data above and your knowledge of the Arc onboarding flow:

1. **Health Summary** — one-paragraph assessment: connectivity status, agent version support status, MSI cert days remaining, and pod restart counts.

2. **Issues Found** — bulleted list of every distinct problem. For each:
   - Symptom (cite the exact file and content)
   - Affected component and where it sits in the onboarding flow
   - Severity: Critical / High / Medium / Low

3. **Root Cause Analysis** — for the top 1-3 issues, explain the root cause using the dependency chain. State which onboarding step is blocked and why.

4. **Recommended Actions** — numbered, ordered by dependency (fix blockers first). Include exact `az` commands or `kubectl` commands for each fix.

5. **Verification Steps** — what to check after each fix to confirm it worked.
"""
    return prompt


def _save_analysis_to_file(diagnostic_folder: str, analysis: str) -> None:
    """Save AI analysis to a text file in the diagnostic folder."""
    try:
        analysis_file = os.path.join(diagnostic_folder, "ai_analysis.txt")
        with open(analysis_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("AI-POWERED DIAGNOSTIC ANALYSIS\n")
            f.write("=" * 80 + "\n\n")
            f.write(analysis)
            f.write("\n\n" + "=" * 80 + "\n")
            f.write("Note: This analysis is generated by AI and should be reviewed by experts.\n")
            f.write("=" * 80 + "\n")
    except Exception as e:
        logger.warning("Could not save AI analysis to file: %s", str(e))
