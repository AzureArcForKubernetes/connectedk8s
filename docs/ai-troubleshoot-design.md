# AI-Powered Troubleshooting for Azure Arc-enabled Kubernetes Onboarding Failures

**Feature**: `az connectedk8s troubleshoot --analyze-with-ai`  
**Component**: `src/connectedk8s/azext_connectedk8s/ai_analyzer.py`  
**Status**: In development  

---

## 1. Problem Statement

### The onboarding failure gap

When `az connectedk8s connect` fails — or a cluster that was previously healthy transitions to **Offline** or **Expired** in the Azure portal — the user is presented with a diagnostic log folder containing dozens of files across multiple subdirectories:

```
~/.azure/arc_diagnostic_logs/<cluster>-<timestamp>/
  diagnoser_output.txt
  agent_state.txt
  connected_cluster_resource_snapshot.txt
  arc_agents_logs/
    clusteridentityoperator-.../manager.txt          (100 KB – 30 MB)
    clusterconnect-agent-.../clusterconnect-agent.txt
    config-agent-.../config-agent.txt                (up to 35 MB)
    ...10 more agent pod directories
  arc_deployment_logs/
    ...12 deployment status files
```

**The problem is threefold:**

1. **Volume**: Agent logs can collectively exceed 100 MB. No engineer reads 100 MB of JSON-structured logs manually during an incident.

2. **Dependency knowledge required**: Arc agents have a strict dependency chain — a failure in `clusteridentityoperator` (MSI certificate) cascades silently to every downstream agent. Without knowing this chain, an engineer may spend hours debugging `clusterconnect-agent` when the actual root cause is a blocked HTTPS endpoint preventing certificate provisioning.

3. **Pattern recognition**: There are ~7 well-known failure patterns (unsupported version, cert expiry, RBAC, network, restart loop, Helm drift, relay unreachable), each with specific log signatures. This knowledge currently lives only in the heads of senior team members and scattered documentation.

The result: onboarding failures take **hours to days** to diagnose, require senior engineers, and the same patterns are re-diagnosed repeatedly.

### Goal

Enable any engineer — regardless of Arc expertise — to get a **precise, evidence-grounded, actionable diagnosis within seconds** of collecting diagnostic logs, by embedding Arc domain knowledge and log analysis intelligence into the CLI itself.

---

## 2. Solution Overview

The solution adds an AI analysis phase to the existing `az connectedk8s troubleshoot` command. After the command finishes collecting diagnostic data, it:

1. Reads and selectively extracts content from the diagnostic files
2. Auto-deduces the incident context (connectivity state, cert expiry, restart counts, etc.)
3. Constructs a structured prompt that includes both the extracted data and Arc domain knowledge
4. Sends the prompt to an LLM (any OpenAI-compatible provider via LiteLLM)
5. Displays a formatted analysis report and saves it to `ai_analysis.txt` in the diagnostic folder

The LLM behaves as a configured Arc SRE — it knows the onboarding flow, the agent dependency chain, and the named failure patterns before it ever sees a log line.

---

## 3. Architecture and Component Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  az connectedk8s troubleshoot                                            │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Existing diagnostic collection (unchanged)                      │    │
│  │                                                                  │    │
│  │  • Cluster connectivity checks    • Agent state snapshot         │    │
│  │  • DNS / outbound network check   • Helm values export           │    │
│  │  • ARM resource snapshot          • Agent pod log collection     │    │
│  │  • CR snapshots (metadata, AAD)   • Deployment status            │    │
│  │                                                                  │    │
│  │  Output → arc_diagnostic_logs/<cluster>-<timestamp>/            │    │
│  └─────────────────────┬───────────────────────────────────────────┘    │
│                        │  diagnostic_folder path + check results         │
│                        ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  ai_analyzer.py  (NEW)                                           │    │
│  │                                                                  │    │
│  │  ┌──────────────────────┐   ┌───────────────────────────────┐   │    │
│  │  │ _prepare_diagnostic_ │   │ _deduce_incident_context()    │   │    │
│  │  │ summary()            │   │                               │   │    │
│  │  │                      │   │ Reads structured files and    │   │    │
│  │  │ • Reads all root      │   │ extracts:                     │   │    │
│  │  │   structured files   │   │ • connectivityStatus          │   │    │
│  │  │ • Reads deployment   │   │ • agentVersion + support flag │   │    │
│  │  │   status logs        │   │ • MSI cert expiry + countdown │   │    │
│  │  │ • For each agent log │   │ • Pod restart counts          │   │    │
│  │  │   (top 5 priority):  │   │ • Diagnoser verdict           │   │    │
│  │  │   head + errors +    │   │ • Network/DNS check status    │   │    │
│  │  │   tail               │   │ • Failed automated checks     │   │    │
│  │  └──────────┬───────────┘   └──────────────┬────────────────┘   │    │
│  │             │                               │                    │    │
│  │             └──────────────┬────────────────┘                   │    │
│  │                            ▼                                     │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │  _build_analysis_prompt()                                │    │    │
│  │  │                                                          │    │    │
│  │  │  Assembles the USER message:                             │    │    │
│  │  │  [1] Auto-deduced incident context  (synthesized state)  │    │    │
│  │  │  [2] Automated check results        (pass/fail table)    │    │    │
│  │  │  [3] Full diagnostic data           (file contents)      │    │    │
│  │  │  [4] Structured analysis request    (5 output sections)  │    │    │
│  │  └──────────────────────────────┬──────────────────────────┘    │    │
│  │                                 │                                │    │
│  │  ┌──────────────────────────────┴──────────────────────────┐    │    │
│  │  │  LiteLLM  (model-agnostic routing layer)                 │    │    │
│  │  │                                                          │    │    │
│  │  │  SYSTEM message: _ARC_SYSTEM_PROMPT                      │    │    │
│  │  │  (Arc domain knowledge — always sent, never changes)     │    │    │
│  │  │                                                          │    │    │
│  │  │  USER message:   assembled prompt above                  │    │    │
│  │  └──────────┬───────────────────────────────────────────────┘    │    │
│  └────────────-│────────────────────────────────────────────────────┘    │
└────────────────│─────────────────────────────────────────────────────────┘
                 │  API call
    ┌────────────┴──────────────────────────────────┐
    │  LLM Provider (user's choice)                  │
    │                                                │
    │  azure/gpt-4o   →  Azure OpenAI               │
    │  gpt-4o         →  OpenAI                     │
    │  ollama/llama3  →  Local Ollama (air-gapped)  │
    │  any other model supported by LiteLLM         │
    └────────────┬──────────────────────────────────┘
                 │  response
                 ▼
    ┌────────────────────────────────────────────────┐
    │  Output                                        │
    │                                                │
    │  • Rich-formatted panel in terminal            │
    │  • Saved to  ai_analysis.txt  in diag folder  │
    └────────────────────────────────────────────────┘
```

---

## 4. Inputs and Context Layers

The prompt sent to the LLM is built from four distinct layers. Understanding the layers helps you tune what the LLM sees and how it responds.

### Layer 1 — System Prompt: Arc Domain Knowledge (static, permanent)

**File**: `_ARC_SYSTEM_PROMPT` constant in `ai_analyzer.py`  
**Sent as**: `role: system` message  
**Changes**: Never changes per-run; encodes team expertise permanently  

| Section | What it encodes |
|---|---|
| Onboarding flow | 7 ordered steps from ARM resource creation to extension activation; which step each agent corresponds to |
| Dependency chain | `clusteridentityoperator → clusterconnect → resource-sync / config-agent / extension-manager`; cascade failure logic |
| Failure patterns | 7 named patterns (A–G) with exact log signatures, impact, and fix for each |
| Log analysis order | Priority sequence: diagnoser → agent_state → ARM snapshot → network → identity logs → clusterconnect → controller-manager → config-agent |
| Response rules | Always cite the file and line; fix blockers before downstream; severity definitions |

This layer ensures the LLM behaves as an Arc SRE by default, without any user input.

### Layer 2 — Auto-Deduced Incident Context (dynamic, extracted per-run)

**Function**: `_deduce_incident_context()`  
**Sent as**: `## AUTO-DEDUCED INCIDENT CONTEXT` section at the top of the user message  
**Source**: Parsed from the collected diagnostic files — no user input required  

| Signal | Source file | Example output |
|---|---|---|
| Connectivity status | `connected_cluster_resource_snapshot.txt` | `Connected` / `Offline` / `Expired` |
| Agent version + support | `connected_cluster_resource_snapshot.txt` | `0.2.4204-dev (auto-upgrade: Disabled)` |
| Kubernetes version | `connected_cluster_resource_snapshot.txt` | `1.33.7 on 4 node(s)` |
| Last connected time | `connected_cluster_resource_snapshot.txt` | `2026-03-11T20:26:24Z` |
| MSI cert expiry + countdown | `connected_cluster_resource_snapshot.txt` | `65 days — 🟢 OK` / `6 days — 🔴 CRITICAL` |
| Diagnoser verdict | `diagnoser_output.txt` | First line of the file |
| Pod restart counts | `agent_state.txt` | `manager (restarts=14, ready=True)` |
| Pods not ready | `agent_state.txt` | Any container with `Ready = False` |
| Failed automated checks | `diagnostic_checks` dict | `AgentVersion, OutboundConnectivity` |
| Outbound connectivity | `outbound_network_connectivity_check.txt` | `PASSED` / `FAILED` |
| DNS check | `dns_check.txt` | `PASSED` / `FAILED` |

This layer replaces what a senior engineer would verbally brief to the team at the start of a war room.

### Layer 3 — Diagnostic File Contents (dynamic, file-based)

**Function**: `_prepare_diagnostic_summary()`  
**Sent as**: `## FULL DIAGNOSTIC DATA` section  

| Sub-section | Files included | Strategy |
|---|---|---|
| Root structured files | `diagnoser_output.txt`, `agent_state.txt`, `outbound_network_connectivity_check.txt`, `dns_check.txt`, `k8s_cluster_info.txt`, `helm_values_azure_arc.txt`, `metadata_cr_snapshot.txt`, `kube_aad_proxy_cr_snapshot.txt`, `azure-arc-secrets.txt`, `connected_cluster_resource_snapshot.txt` | Full content up to 3,000 chars each |
| Deployment status logs | All files in `arc_deployment_logs/` | Full content up to 2,000 chars each |
| Agent runtime logs | Top 5 agent pod dirs by priority | Head (20 lines) + error/warning lines (up to 50) + tail (30 lines); skips `fluent-bit.txt` (noise) |

**Large file strategy**: Files over 1 MB are handled with byte-seek for the tail and scan-limited to the first 5,000 lines for error extraction — preventing memory spikes from 30 MB logs.

**Agent priority order** (most likely root cause first):
1. `clusteridentityoperator` — MSI cert provisioning
2. `controller-manager` — RBAC and GitOps
3. `clusterconnect-agent` — relay connectivity
4. `config-agent` — GitOps config application
5. `extension-manager` — extension lifecycle

### Layer 4 — Automated Check Results (dynamic, from troubleshoot run)

**Source**: `diagnostic_checks` dict passed from `troubleshoot()` in `custom.py`  
**Sent as**: `## AUTOMATED CHECK RESULTS` section  

Checks are classified into Passed / Failed / Incomplete and listed. The LLM uses these to prioritise its analysis — a failed check is a confirmed symptom rather than a hypothesis.

---

## 5. Token Budget

| Layer | Approximate size |
|---|---|
| System prompt (domain knowledge) | ~1,800 tokens |
| Auto-deduced incident context | ~100–200 tokens |
| Automated check results | ~50–150 tokens |
| Diagnostic file contents | ~6,000–7,000 tokens (capped at 28,000 chars) |
| Analysis request instructions | ~200 tokens |
| **Total input** | **~9,000–10,000 tokens** |
| LLM response (`max_tokens`) | 4,096 tokens |

Well within the 128k context window of GPT-4o. For smaller models (8k–16k context), reduce `_MAX_TOTAL_PROMPT_CHARS` and `_MAX_AGENT_LOG_DIRS`.

---

## 6. Customisation Options

### 6.1 Model selection — any OpenAI-compatible provider

```bash
# Azure OpenAI
az connectedk8s troubleshoot \
  --name mycluster --resource-group myrg \
  --analyze-with-ai \
  --model azure/gpt-4o

# OpenAI
az connectedk8s troubleshoot ... --model gpt-4o

# Local Ollama (air-gapped environments)
az connectedk8s troubleshoot ... --model ollama/llama3
```

Required environment variables per provider:

| Provider | Variables |
|---|---|
| Azure OpenAI | `AZURE_API_BASE`, `AZURE_API_VERSION`, `AZURE_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Ollama | `OLLAMA_API_BASE` (default: `http://localhost:11434`) |

### 6.2 Tuning the system prompt (team expertise)

Edit `_ARC_SYSTEM_PROMPT` in `ai_analyzer.py` to:
- Add new failure patterns as they are discovered
- Add region-specific known issues
- Adjust severity thresholds (e.g. cert expiry warning at 90 days instead of 60)
- Add links to internal runbooks per failure pattern

This is the highest-leverage customisation — it permanently improves the analysis for all users.

### 6.3 Tuning which files are read

| Constant | Default | Effect of changing |
|---|---|---|
| `_ROOT_STRUCTURED_FILES` | 10 files | Add/remove files read in full |
| `_AGENT_PRIORITY_PREFIXES` | 6 prefixes | Change which agent logs are prioritised |
| `_MAX_AGENT_LOG_DIRS` | 5 | Include more/fewer agent pod log dirs |
| `_MAX_CHARS_SMALL_FILE` | 3,000 | Read more/less of each structured file |
| `_MAX_CHARS_AGENT_LOG` | 4,000 | More/less content per agent log |
| `_MAX_ERROR_LINES_PER_FILE` | 50 | More/fewer error lines extracted |
| `_MAX_TOTAL_PROMPT_CHARS` | 28,000 | Hard cap; reduce for smaller context models |

### 6.4 Future: per-run incident context (planned)

A `--context-file` flag would allow an operator to provide a markdown or YAML file with situation-specific context before running the command:

```yaml
# troubleshoot_context.yaml (not yet implemented)
symptom: "cluster offline since 2026-03-10 17:00 UTC"
already_tried:
  - "az connectedk8s update"
  - "restarted clusteridentityoperator pod"
focus_on: [certificate_issues, connectivity]
custom_instructions: "Format output as a P1 incident summary"
```

This would be injected between Layer 2 and Layer 3, after the auto-deduced context, giving the LLM both the objective machine-extracted state and the engineer's subjective observations.

---

## 7. Output Format

The LLM is instructed to always produce five sections:

| Section | Content |
|---|---|
| **Health Summary** | One paragraph: connectivity status, agent version support, MSI cert days remaining, pod restart counts |
| **Issues Found** | Bulleted list with symptom, affected component (and its position in the onboarding flow), severity |
| **Root Cause Analysis** | For top 1–3 issues: root cause mapped to the dependency chain with specific log citations |
| **Recommended Actions** | Numbered and ordered by dependency (blockers first); exact `az` and `kubectl` commands |
| **Verification Steps** | What to check after each fix to confirm resolution |

Output is displayed in a Rich-formatted panel in the terminal and saved to `ai_analysis.txt` in the diagnostic folder.

---

## 8. Dependencies

| Package | Version | Purpose |
|---|---|---|
| `litellm` | `>=1.40.0` | Model-agnostic LLM routing (OpenAI, Azure OpenAI, Ollama, 100+ providers) |
| `rich` | `>=13.0.0` | Formatted terminal output (panels, colours) |

Both are declared as optional dependencies in `setup.py` gated on `python_version >= '3.9'`. If not installed, AI analysis is skipped with a warning and the rest of the troubleshoot command is unaffected.

---

## 9. Running Without a Live Cluster (smoke test)

A standalone smoke test runner is available for testing the analyzer against a previously collected diagnostic folder without re-running the full troubleshoot command:

```bash
python src/connectedk8s/azext_connectedk8s/tests/smoke/run_ai_analyzer_smoke.py \
  --diagnostic-folder ~/.azure/arc_diagnostic_logs/<cluster>-<timestamp> \
  --cluster-name mycluster \
  --resource-group myrg \
  --model azure/gpt-4.1
```

Required environment variables must be set before running (see section 6.1).
