# End-to-End Correlation for `az connectedk8s proxy`

**Status:** Proposal
**Owner:** Arc-enabled Kubernetes (CLI extension + AzureArc-GuestProxy)
**Audience:** PMs, on-call, support, partner teams (Relay, ConnectedProxyAgent, Geneva)

---

## 1. The problem in one sentence

When a customer runs `az connectedk8s proxy` and something goes wrong, **we cannot follow a single request across the five components it touches**, so triage takes hours and often ends in "please re-run with `--debug` and send us the logs."

## 2. What `az connectedk8s proxy` actually does

```
Customer  ─►  az CLI extension  ─►  ARM (list_cluster_user_credential)
                   │
                   ├─►  arcProxy.exe  (local Go binary, started by the CLI)
                   │         │
                   │         ├─►  /identity/poppublickey       (localhost)
                   │         ├─►  /identity/at                 (localhost)
                   │         └─►  /…/register?api-version=…    (localhost)
                   │
                   └─►  arcProxy ─► Azure Relay rendezvous WS ─► ConnectedProxyAgent (in cluster) ─► Geneva
```

One user command = one logical operation, but it fans out to ARM, a local sub-process, Azure Relay, an in-cluster agent, and Geneva telemetry.

## 3. What's broken today

Verified empirically by running `az connectedk8s proxy --debug` against a real cluster and inspecting the live log:

| Hop | Has a tracking id? | Same id as previous hop? |
|---|---|---|
| Customer → CLI | n/a (azure-core mints `x-ms-client-request-id` per HTTP call) | — |
| CLI → ARM `list_cluster_user_credential` outbound headers | **No** `x-ms-correlation-request-id` on the request — az-cli core does not stamp it | — |
| ARM response | Yes (ARM mints `x-ms-correlation-request-id` server-side and returns it) | Different id every invocation |
| CLI → arcProxy localhost calls (3 of them) | **No header at all** | **No** |
| arcProxy → Relay rendezvous WS | No correlation header stamped | **No** |
| ConnectedProxyAgent → Geneva | Logs an `ActivityId`, but it's the agent's own internal id | **No** |

**Two separate problems:**
1. The id ARM uses is invisible to the customer until *after* the ARM response — and is not threaded into the 3 subsequent localhost calls into arcProxy.
2. Nothing the CLI does today causes ARM, arcProxy, Relay, and the agent to log the **same** id.

**Net effect:** five components, five different ids (or no id). When a `proxy` session fails, the support engineer has to hand-stitch timestamps across CLI logs, ARM logs, arcProxy logs, Relay logs, and Geneva — manually. There is no single search term that returns the full path of one customer session.

## 4. What we are fixing

**Mint one correlation id at the top of `az connectedk8s proxy`, stamp it on the outbound ARM request, and forward the same value to all 3 localhost calls into arcProxy.** ARM honors a client-supplied `x-ms-correlation-request-id` and echoes it back, so the same GUID flows through every component (CLI `--debug`, ARM Geneva, arcProxy, Relay, ConnectedProxyAgent `ConnectAgentTraces`).

**Result after fix:** support pastes one id into Kusto / Geneva / arcProxy logs and gets the complete story for one customer session.

## 5. The fix (CLI side — this PR)

1. **Mint one `uuid.uuid4()` at the top of `client_side_proxy_wrapper`.** [`ensure_correlation_id(cmd)`](../azext_connectedk8s/_utils.py) checks `cmd.cli_ctx.data["headers"]["x-ms-correlation-request-id"]`; if absent (the normal case — az-cli core does not stamp it), it mints a fresh uuid4 and writes it back into the header bag. Idempotent within a session: subsequent calls return the same id.
2. **Stamp the id on the outbound ARM `list_cluster_user_credential` request.** [`get_cluster_user_credentials`](../azext_connectedk8s/clientproxyhelper/_proxylogic.py) accepts an optional `correlation_id` and forwards it via `headers={...}` kwarg. The vendored azure-core SDK pops `kwargs["headers"]` and merges them into the request. ARM honors and echoes the value back unchanged, so it appears in both the request and response headers in `--debug` output.
3. **Forward the same id to all 3 localhost calls into arcProxy** by threading it into the single chokepoint [`make_api_call_with_retries`](../azext_connectedk8s/clientproxyhelper/_utils.py). The header dict is built **once** before the retry loop so all retries of one logical attempt share the same id (one logical operation = one id in Kusto, not one per retry).
4. **Log it once at WARNING level** so the customer sees it in console output and can quote it in support tickets. Also emit telemetry under the same key.

That's it on the CLI side. ~30 lines of net logic across 3 files (plus tests). No new dependencies. The wire-level change on the ARM call is additive (a new request header that ARM accepts and echoes); the wire-level change on the 3 localhost calls is additive (arcProxy already ignores unknown headers and, with the matching downstream patch, will read this one).

Downstream changes (separate PRs, owned by the Go team and agent team):
- arcProxy reads `x-ms-correlation-request-id` from the `/register` (and `/identity/at`) handlers and stamps it on every Relay rendezvous WS handshake. **Already merged.**
- ConnectedProxyAgent reads the same header from the WS handshake and writes it into Geneva `ConnectAgentTraces.correlationId`.

## 6. Why we chose this design

| Option considered | Why we rejected / picked it |
|---|---|
| **A. CLI mints uuid4, stamps on ARM request, ARM echoes back, forward to localhost** ✅ chosen | One GUID end-to-end, available *before* any HTTP call so every hop including the first localhost call carries it. Verified live: same value in CLI WARNING, ARM request header, ARM response header, and arcProxy `ActivityId` for all 3 operations. |
| B. Capture the ARM-minted `x-ms-correlation-request-id` from the ARM response and forward it to localhost calls | Doesn't unify ARM and CLI: ARM still picks the id and our WARNING log can't print it until *after* the ARM call returns. If the ARM call itself fails before the response, we have no id at all. (`with ThreadPoolExecutor()` blocks until the future completes, so there is no race today, but option A is strictly simpler and more robust.) |
| C. Forward whatever az-cli core already set in `cmd.cli_ctx.data["headers"]`; sentinel on gap | Verified empirically: az-cli core does **not** populate this header bag with `x-ms-correlation-request-id` on outbound ARM requests today (it only reads the value from ARM error responses). The "happy path" assumed by this option doesn't exist, so the sentinel would fire 100% of the time. Rejected. |
| D. Reuse `x-ms-client-request-id` | That header is per-HTTP-request by definition; azure-core regenerates it on each call. Wrong semantic, breaks on retries and across the 3 localhost calls. |
| E. Invent a custom header (`x-arc-trace-id`) | ARM and Azure Activity Log would not parse it, so the value would never appear in Kusto's `correlationId` column. We'd lose platform-wide correlation for free. |
| F. Build a new tracing pipeline (OpenTelemetry, App Insights, etc.) | Months of work, multi-team coordination, requires customer egress to a new endpoint. Out of scope for the actual problem. |

**Choice A** is the only one that gets us platform-wide correlation (ARM → Azure Activity → Geneva → Relay) using only headers already understood by every component, with a patch small enough to ship in one sprint, and a single id available from the very first log line.

## 7. What the customer / support engineer sees after the fix

```
$ az connectedk8s proxy -n my-cluster -g my-rg --debug
WARNING: Arc proxy session correlationId: 7fdbe5bb-d3f1-4606-b9a0-3589d93dbe15
...
DEBUG: cli.azure.cli.core.sdk.policies:     'x-ms-correlation-request-id': '7fdbe5bb-d3f1-4606-b9a0-3589d93dbe15'   ← ARM request (we stamped it)
DEBUG: cli.azure.cli.core.sdk.policies:     'x-ms-correlation-request-id': '7fdbe5bb-d3f1-4606-b9a0-3589d93dbe15'   ← ARM response (echoed back)
...
level=info msg="ProxyPopPublicKeyComplete"           ActivityId=7fdbe5bb-d3f1-4606-b9a0-3589d93dbe15   ← arcProxy
level=info msg="ProxyPostIdentityAccessTokenComplete" ActivityId=7fdbe5bb-d3f1-4606-b9a0-3589d93dbe15   ← arcProxy
level=info msg="ProxyRegisterSucceeded"              ActivityId=7fdbe5bb-d3f1-4606-b9a0-3589d93dbe15   ← arcProxy
Proxy is listening on port 47011
```

All one GUID. (Captured from a real run against a live cluster on 2026-06-10.)

When something breaks, the engineer runs **one** Kusto query:

```kusto
union AzureActivity, ConnectAgentTraces, ArcProxyLogs
| where correlationId == "7fdbe5bb-d3f1-4606-b9a0-3589d93dbe15"
| order by TimeGenerated asc
```

…and gets the complete request flow: ARM → arcProxy → Relay → ConnectedProxyAgent — in chronological order, no hand-stitching.

### Sentinel constants (still defined, not used by this PR's code path)

[`_constants.py`](../azext_connectedk8s/_constants.py) defines `Missing_Correlation_Id_Sentinel_Prefix = "00000000-0000-0000-miss-"` and `Missing_Correlation_Id_CLI_Extension = "00000000-0000-0000-miss-connectedk8s"`. These remain as a documented convention for **other** services or future code paths that genuinely cannot mint an id (e.g. a downstream component receiving a request with no header and unable to fall back). The `connectedk8s` extension itself never stamps a sentinel today — `uuid.uuid4()` always succeeds — but the constants give the org a consistent, GUID-shaped, non-hex-marker convention if a real gap is ever introduced.

## 8. Risk and rollback

- **Wire change on the ARM call:** additive — adds `x-ms-correlation-request-id: <uuid>` to the outbound request. ARM's documented contract is to honor a client-supplied value and echo it back; if the header had been absent (today's behaviour) ARM mints one server-side. Either way, ARM accepts the request.
- **Wire change on the 3 localhost calls:** additive — arcProxy ignores unknown headers today and, with the matching downstream patch, will read this one.
- **Customer-visible change:** one new WARNING line per session printing the GUID. No new flags, no new permissions, no new endpoints.
- **Rollback:** revert the CLI patch — every downstream component falls back to its current behaviour automatically (ARM mints server-side, arcProxy logs without the ActivityId join).

## 9. Out of scope (future work)

- Surfacing the correlation id in `az --debug` output formatting (already in CLI logs at WARNING level).
- arcProxy and ConnectedProxyAgent stamping changes (separate repos, separate PRs).
- Backfilling correlation into `az connectedk8s connect` and other commands (same `ensure_correlation_id` helper, ~3-line diff per entrypoint).

---

**Bottom line:** mint one uuid at the top of the command, stamp it on ARM (which echoes it back) and on every localhost call, ~30 lines across 3 files, end-to-end visibility for support. Verified live. Ship it.
