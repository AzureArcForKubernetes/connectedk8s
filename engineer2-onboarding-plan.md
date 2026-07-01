# Engineer 2 — Arc K8s Onboarding Improvement Plan

Personal working doc for my three issue areas from the team plan.

---

## My Scope at a Glance

| # | Issue Category | What Customers See | Where in Code |
|---|---|---|---|
| 4 | Onboarding Stuck in Connecting | `az connectedk8s connect` partially completes, resource never reaches "Connected" | `custom.py` — `create_connectedk8s()` flow, `poll_for_agent_state()`, Helm install via `_utils.py:helm_install_release()` |
| 5 | Agent / Pod Health Issues | CrashLoopBackOff, Pending, ContainerCreating, Helm timeout, readiness probe 500s | `_troubleshootutils.py` — pod status checks, `_utils.py` — Helm error handling |
| 6 | CLI / Tooling / Environment Issues | Pre-check failures, Helm/kubectl errors, arch mismatch, version incompatibility | `custom.py` — `install_helm_client()`, `install_kubectl_client()`, `_precheckutils.py` |

---

## Issue 4: Onboarding Stuck in "Connecting"

### What's actually happening in the code

1. `create_connectedk8s()` in `custom.py` runs the full onboarding flow:
   - Pre-flight validations (~line 200–450)
   - Diagnostic pre-checks (~line 320–430)
   - ARM resource PUT (~line 940–1050)
   - Helm chart install via `helm_install_release()` in `_utils.py` (~line 1281)
   - Agent state polling via `poll_for_agent_state()` (~line 1084)

2. `poll_for_agent_state()` polls every 5s for up to 15 minutes (`Agent_State_Timeout`). Only checks for `Succeeded` or `Failed`. If neither arrives → generic `CLIInternalError("Timed out waiting for Agent State to reach terminal state.")`.

3. Helm install uses `--wait --timeout 1200s` (20 min). If Helm itself times out, the error message gets sanitized (RSA keys stripped) but is still often opaque.

### Root causes to investigate

- **RBAC issues**: Helm install completes but agent can't report status back. The error message says nothing about RBAC.
- **Connectivity failures**: Agent pods run but can't reach Arc DP endpoints. No differentiation from other timeout causes.
- **Helm install incomplete**: Some pods start but not all. Partial readiness isn't surfaced.
- **No heartbeat from agent**: `poll_for_agent_state()` only looks at `agent_state` on the ARM resource. It doesn't inspect pod-level health at all — a big diagnostic gap.

### What I think needs fixing (priority order)

1. **Enrich the timeout error message in `poll_for_agent_state()`**
   - When we time out, before raising `CLIInternalError`, query pod statuses in `azure-arc` namespace and include a summary in the error. Example: "Timed out. Pod status: connect-agent=Running, config-agent=CrashLoopBackOff (reason: OOMKilled)."
   - This is the single highest-leverage change — transforms a dead-end error into an actionable one.

2. **Add intermediate progress reporting during polling**
   - Currently silent for up to 15 minutes. Print periodic updates: "Waiting for agent state... (3/15 min elapsed, current state: Connecting, pods: 4/6 ready)."
   - Use `logger.warning()` or `print()` consistent with existing step logging.

3. **Distinguish failure classes on timeout**
   - After timeout, run a mini-diagnostic: check pod events, check if `connect-agent` has outbound connectivity errors in logs, check if Helm release is in `deployed` state.
   - Map to specific suggestions: "Pods are pending — check node capacity", "connect-agent has TLS errors — check proxy config", "Helm release failed — check `helm status azure-arc`."

4. **Consider structured error codes**
   - Per Matt's suggestion, introduce codes like `ARCK8S4001` (timeout — pods not ready), `ARCK8S4002` (timeout — connectivity), etc.
   - Add to `_constants.py` alongside existing fault types.

5. **Telemetry gap**: When `poll_for_agent_state()` times out, we raise an error but don't call `telemetry.set_exception()` with a specific fault type. Add one.

### Code areas to change

| File | Function / Area | Change |
|---|---|---|
| `custom.py` ~1060–1080 | Post-helm-install timeout block | Add pod-level diagnostics before raising error |
| `custom.py` ~1084–1110 | `poll_for_agent_state()` | Add progress logging, capture pod state on timeout |
| `_constants.py` | Fault types | Add `Agent_State_Timeout_Fault_Type`, structured error codes |
| `_troubleshootutils.py` | Pod status helpers | May need to extract reusable pod-summary function |
| `_utils.py` ~1389–1414 | `helm_install_release()` error handling | Better classification of Helm timeout vs. Helm failure |

---

## Issue 5: Agent / Pod Health Issues

### What's actually happening in the code

- `_troubleshootutils.py` has pod health checks: `retrieve_arc_agents_logs()`, checks `pod.status.phase != "Running"`, iterates `container_statuses`.
- Special handling for `kube-aad-proxy` in `ContainerCreating` state (~line 1698–1714).
- `_utils.py` line 1439 has a message about pods stuck in pending state but it's generic advice.
- Helm install with `--wait` will fail if pods don't become ready, but the error is "timed out waiting for the condition" — which gets tagged as `user_fault` in telemetry (line 1396–1414), which is wrong when it's a system issue.

### Root causes to investigate

- **Resource constraints**: Insufficient CPU/memory on nodes → pods stay Pending. We don't check node allocatable resources.
- **Image pull failures**: MCR/ACR unreachable or rate-limited. Not specifically detected.
- **Missing secrets/configmaps**: Dependencies not created by Helm. Pods crash on startup.
- **Readiness probe failures (HTTP 500)**: Agent has internal errors. Currently we don't inspect probe failure reasons.

### What I think needs fixing (priority order)

1. **Classify Helm `--wait` timeout as system fault, not user fault**
   - `_utils.py` line ~1396–1414 currently marks "timed out waiting for the condition" as `set_user_fault()`. This is wrong for most cases (node resource issues, image pull failures). Need to inspect further before classifying.
   - At minimum: check pod events. If `FailedScheduling` or `ImagePullBackOff` → system/infra fault, not user fault.

2. **Add pod health summary to troubleshoot output**
   - After Helm failure, enumerate pods in `azure-arc` namespace with: name, phase, restart count, last event reason, container state reason (OOMKilled, CrashLoopBackOff, etc.).
   - Reusable function that Issue 4 can also call.

3. **Detect common pod failure patterns and surface specific guidance**
   - `Pending` + `FailedScheduling` → "Insufficient resources. Need X CPU / Y memory available on Linux nodes."
   - `ImagePullBackOff` → "Cannot pull agent images. Check network connectivity to mcr.microsoft.com."
   - `CrashLoopBackOff` + `OOMKilled` → "Agent OOM. Consider increasing memory limits."
   - `ContainerCreating` stuck → Check for missing secrets (existing logic for kube-aad-proxy, generalize it).

4. **Structured event collection**
   - Use K8s events API to get recent events in `azure-arc` namespace. Filter for Warning events. Include in error output and telemetry.

5. **Post-connect health check command**
   - Consider enhancing `az connectedk8s show` or adding a `az connectedk8s health` subcommand that reports pod-level health. (Bigger scope — may be a separate feature.)

### Code areas to change

| File | Function / Area | Change |
|---|---|---|
| `_utils.py` ~1389–1414 | Helm error handling | Fix user_fault classification, add pod diagnostics |
| `_troubleshootutils.py` | Pod status checks | Build reusable `get_pod_health_summary()` function |
| `_troubleshootutils.py` ~1698–1714 | kube-aad-proxy check | Generalize to all agent pods |
| `_constants.py` | Error messages | Add pattern-specific error messages and fault types |
| `custom.py` | Post-helm-install | Call pod health summary on failure |

---

## Issue 6: CLI / Tooling / Environment Issues

### What's actually happening in the code

- **Helm install**: `install_helm_client()` in `custom.py` (~line 1388). Downloads from MCR via ORAS. Detects OS/arch. 3 retries with 5s delay. Version: `HELM_VERSION = "v3.20.1"`.
- **Kubectl install**: `install_kubectl_client()` in `custom.py` (~line 4680). Uses `az aks install-cli`.
- **Pre-checks**: `_precheckutils.py` — `fetch_diagnostic_checks_results()` runs DNS, outbound connectivity, cluster diagnostic jobs.
- **Architecture detection**: `platform.machine()` for arm64 vs amd64. Node-level checks via K8s API for `check_arm64_node()` and `check_linux_node()`.
- **Cloud-specific**: AGC (air-gapped) skips Helm/kubectl install, expects pre-installed.

### Root causes to investigate

- **Version incompatibility**: No validation that existing Helm/kubectl versions are compatible. If user has old Helm pre-installed, we just use it.
- **Arch mismatch**: Client arch vs cluster node arch. If I'm on ARM64 Mac but cluster is AMD64 Linux — the *client* tools are fine, but Helm chart images might not match. The `check_arm64_node()` validates node arch, but the error messaging is unclear.
- **Pre-check gaps**: Pre-checks run diagnostic jobs on the cluster but don't validate client-side env (e.g., kubeconfig validity, kubectl version, az CLI version, extension version).
- **exec format error**: Running wrong-arch binary. The code detects arch but if `HELM_CLIENT_PATH` env var is set to wrong binary, no validation happens.

### What I think needs fixing (priority order)

1. **Validate user-provided tool paths**
   - When `HELM_CLIENT_PATH` or `KUBECTL_CLIENT_PATH` is set, run `helm version` / `kubectl version` to verify the binary works. Currently we trust the path blindly.
   - If it fails → clear error: "HELM_CLIENT_PATH points to an invalid binary. Error: exec format error. Your system is {arch} but the binary may be for a different architecture."

2. **Add client-side pre-flight checks**
   - Before running expensive cluster-side diagnostics, validate:
     - `kubectl version` — is it reachable and compatible?
     - `helm version` — is it compatible?
     - `az version` — is CLI version sufficient?
     - `az extension show connectedk8s` — is extension version correct?
   - Fast, local checks that catch obvious issues early.

3. **Improve arch mismatch messaging**
   - Current: `check_arm64_node()` logs a warning. Make it more specific about what will happen (e.g., "Your cluster has ARM64 nodes. Arc agents will deploy ARM64 images. Ensure nodes have sufficient resources for multi-arch deployment.").

4. **Version skew detection**
   - If Helm version < minimum supported → error with upgrade instructions.
   - If kubectl version skew with K8s API server > ±1 minor → warning.

5. **Better ORAS download failure messaging**
   - Currently: 3 retries then generic error. Add: "Failed to download Helm client from MCR. Check network connectivity to {mcr_url}. If behind a proxy, ensure HTTPS_PROXY is set."

### Code areas to change

| File | Function / Area | Change |
|---|---|---|
| `custom.py` ~1388 | `install_helm_client()` | Validate user-provided path, version checks |
| `custom.py` ~4680 | `install_kubectl_client()` | Validate user-provided path |
| `_precheckutils.py` | Pre-checks | Add client-side pre-flight checks |
| `_constants.py` | Error messages | Add version-mismatch, arch-mismatch fault types |
| `custom.py` ~1730–1760 | Arch detection | Improve mismatch messaging |

---

## Cross-Cutting Themes

### Structured Error Codes
Propose a scheme like `ARCK8S-XXXX`:
- `4xxx` — Connecting/timeout issues
- `5xxx` — Pod/agent health issues
- `6xxx` — CLI/tooling/environment issues

Each code maps to a public doc page. Start with top 10 most common failures and expand.

### Telemetry Improvements
- Ensure every error path calls `telemetry.set_exception()` with a specific fault type.
- Fix `set_user_fault()` misclassifications in Helm timeout handling.
- Add pod-state telemetry on failure (which pods are unhealthy, why).
- Track onboarding duration and where time is spent (pre-checks, Helm install, agent polling).

### Reusable Diagnostics
Build a shared `get_pod_health_summary(namespace="azure-arc")` function in `_troubleshootutils.py` that:
- Lists all pods with phase, restart count, container state reason
- Fetches recent Warning events
- Returns a structured object + formatted string
- Used by: Issue 4 (timeout), Issue 5 (pod failures), `az connectedk8s troubleshoot`

### Test Coverage
- Unit tests for `poll_for_agent_state()` with mock responses (timeout, success, failure).
- Unit tests for pod health summary with various pod states.
- Unit tests for tool validation (valid/invalid Helm path, version checks).
- Integration test for onboarding timeout scenario.

---

## Suggested Execution Order

### Phase 1 — Quick wins (high impact, small changes)
1. Add telemetry to `poll_for_agent_state()` timeout path
2. Fix `set_user_fault()` misclassification in Helm timeout
3. Add progress logging during agent state polling
4. Validate user-provided `HELM_CLIENT_PATH` / `KUBECTL_CLIENT_PATH`

### Phase 2 — Core diagnostic improvements
5. Build `get_pod_health_summary()` reusable function
6. Enrich timeout error with pod-level diagnostics
7. Add pattern-specific failure messages (Pending, CrashLoopBackOff, ImagePullBackOff)
8. Add client-side pre-flight checks

### Phase 3 — Structured error codes and docs
9. Define error code scheme, implement for top failures
10. Create/update public docs for each error code
11. Add version skew detection and warnings

### Phase 4 — Advanced
12. Post-connect health check command
13. AI agent integration for automated diagnosis
14. Onboarding duration telemetry breakdown

---

## Questions to Resolve

- [ ] What's the right timeout for `poll_for_agent_state()`? 15 min seems long — should we fail faster and give diagnostics sooner?
- [ ] Should `helm_install_release()` capture pod events *during* the `--wait` phase, or only after failure?
- [ ] Are there existing error code conventions in Azure CLI extensions I should follow, or is `ARCK8S-XXXX` a new pattern?
- [ ] For AI agent integration (success measure #7), what telemetry/signals are available today and what's missing?
- [ ] How do we handle the overlap between my pod health work (Issue 5) and Engineer 1's identity/cert work (Issues 1–3)? E.g., identity operator pods crashing is pod health but root cause is cert/identity.
- [ ] Matt's point about disconnection diagnostics — should I add post-onboarding health monitoring too, or is that a separate workstream?

---

## Key Files Reference

| File | What it does |
|---|---|
| `custom.py` | Main command implementations, Helm/kubectl install, agent state polling |
| `_utils.py` | Helm install orchestration, helm values, error sanitization |
| `_troubleshootutils.py` | Pod health checks, log retrieval, diagnostic utilities |
| `_precheckutils.py` | Pre-onboarding diagnostic checks (DNS, connectivity, cluster jobs) |
| `_constants.py` | All fault types, timeouts, version constants, error messages |
| `commands.py` | CLI command registration |
