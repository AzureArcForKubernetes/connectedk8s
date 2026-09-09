# One Fault per ConnectedK8s Failure

## PR summary (250 words)

ConnectedK8s pre-onboarding diagnostics emit multiple Azure CLI fault events during one failed connect command. Lower-level DNS and outbound-connectivity helpers call telemetry.set_exception when checks fail, and the command-level onboarding flow emits a terminal fault when it stops the operation. Azure CLI preserves every registered exception and uploads one azurecli/fault record per call, so a single command can produce several fault rows sharing the same parent correlation ID.

This behavior inflates dashboards that count fault records instead of unique command correlations. It can also alter the command outcome incorrectly: the optional Cluster Connect endpoint check calls telemetry.set_user_fault even though onboarding may continue successfully. In the seven-day window, 35 commands emitted 47 DNS or outbound component faults. Twenty-six had multiple fault rows, and 23 were marked UserFault without a terminal prediagnostic fault. Those records can reduce success rates despite not representing 23 failed onboarding operations.

The change establishes one terminal fault owner. The prediagnostic orchestrator retains DNS, mandatory outbound, Entra, and CRD results in a connectedk8s extension event. The command-level caller emits the single terminal cluster-diagnostic-prechecks-failed fault and explicitly classifies it as UserFault. Lower-level DNS and mandatory onboarding checks no longer register faults during connect. The optional Cluster Connect failure remains observable as a structured extension diagnostic, including its AZK8S0307 code, endpoint, response code, target, command correlation, and connected-cluster resource ID, but it no longer changes the command result.

Troubleshoot behavior is preserved through the helper mode. This keeps actionable diagnostic detail while making command-level failure counts, user-error rates, and success KPIs reliable.

## Problem

Azure CLI telemetry records command execution separately from exceptions:

- `azurecli/command` represents the command and its final action result.
- `azurecli/fault` represents one exception registered through
  `telemetry.set_exception`.
- `azurecli/extension` carries ConnectedK8s-specific diagnostic properties.

Azure CLI does not collapse multiple calls to `telemetry.set_exception`. Each call
registered during a command can become a separate `azurecli/fault` record.
Consequently, one failed `az connectedk8s connect` invocation can produce several
fault rows even though only one command was executed.

The fault event has two correlation values with different meanings:

| Property | Meaning |
|---|---|
| `reserved.datamodel.correlationid` | Unique ID of the fault event |
| First value in `reserved.datamodel.correlation.1` | Parent command correlation ID |

Queries must use `correlation.1` for fault-to-command correlation. Using
`coalesce(correlationid, correlation.1)` is incorrect because a fault normally
contains both values and `coalesce` selects the fault event ID.

```kusto
| extend CorrelationId = iff(
    EventName == "azurecli/fault",
    tostring(split(tostring(
        CustomProperties["reserved.datamodel.correlation.1"]), ",")[0]),
    tostring(CustomProperties["reserved.datamodel.correlationid"])
)
```

## Where duplicate faults were emitted

The pre-onboarding diagnostic job evaluates DNS, optional Cluster Connect
connectivity, mandatory onboarding connectivity, Entra connectivity, and CRD
ownership. Before this change, multiple layers reported the same command
failure.

| Layer | Location | Previous telemetry effect |
|---|---|---|
| DNS parser | `_utils.py :: check_cluster_DNS` | Registered `dns-resolution-failed` |
| Optional Cluster Connect parser | `_utils.py :: check_cluster_outbound_connectivity` | Registered a fault and called `set_user_fault` |
| Mandatory onboarding parser | `_utils.py :: check_cluster_outbound_connectivity` | Registered an outbound-connectivity fault and called `set_user_fault` |
| Prediagnostic orchestrator | `_precheckutils.py :: fetch_diagnostic_checks_results` | Reported aggregate component details |
| Command owner | `custom.py :: create_connectedk8s` | Registered the terminal `cluster-diagnostic-prechecks-failed` fault |

A DNS-disabled test produced one command event and these four fault events:

1. `dns-resolution-failed`
2. `outbound-network-connectivity-check-failed-for-cluster-connect`
3. `outbound-network-connectivity-check-failed-for-onboarding`
4. `cluster-diagnostic-prechecks-failed`

All four faults shared one parent command correlation, but each fault had its own
event correlation ID.

## Observed KPI impact

For the seven days ending September 8, 2026, the three component fault types
affected 35 connect commands:

| Measurement | Value |
|---|---:|
| Commands with a DNS or outbound component fault | 35 |
| DNS or outbound component fault rows | 47 |
| All fault rows attached to those commands | 96 |
| Commands with more than one fault row | 26 |
| Maximum fault rows for one command | 5 |
| Commands marked `UserFault` without a terminal prediagnostic fault | 23 |

The last row is especially important. The Cluster Connect endpoint is optional
for onboarding, but its failure path called `telemetry.set_user_fault`. A connect
operation could therefore continue while the command telemetry was classified
as `UserFault`. A dashboard using the command action result would count that
operation as a failed command even without a terminal prediagnostic failure.

Fault-row-based calculations are also inflated because they treat contributing
causes as separate failed operations. This can distort:

- Failure counts and failure rates.
- User-error counts and user-error rates.
- Fault-type rankings.
- Month-over-month and version-over-version comparisons.
- Success rate excluding user errors.

The reliable denominator is the number of unique command correlations. Fault
and extension records should enrich those commands, not become additional
command outcomes.

## Corrected telemetry ownership

The command-terminating layer now owns the only fault:

```text
az connectedk8s connect
    |
    +-- DNS result -----------------------+
    +-- mandatory outbound result --------+--> aggregate extension diagnostic
    +-- Entra result ---------------------+
    +-- CRD result -----------------------+
    |
    +-- optional Cluster Connect failure ----> standalone extension diagnostic
    |
    +-- command cannot continue ------------> one terminal Azure CLI fault
```

The behavior is:

- DNS and mandatory onboarding failures append actionable details to
  `diagnoser_output`.
- `_precheckutils.py` emits one structured `prediagnostics-failure` extension
  event containing each component name, result, and available error detail.
- `custom.py` emits one terminal `cluster-diagnostic-prechecks-failed` fault and
  explicitly marks that terminal outcome as a user fault.
- Optional Cluster Connect failure emits AZK8S0307 as an extension diagnostic.
  It includes the endpoint, response code, target, command correlation, and
  connected-cluster ARM resource ID, but it does not register a fault or change
  the command result.
- The `troubleshoot` command retains its existing fault behavior because it is a
  separate command flow where the helper result can be terminal.

## Diagnostic data retained

Removing component fault calls does not remove root-cause information. Failed
connect commands retain:

- DNS classification such as `NXDOMAIN`, `SERVFAIL`, timeout, unreachable DNS
  server, or communications error.
- Failed onboarding endpoint and response code `000`.
- The distinction between mandatory onboarding and optional Cluster Connect
  connectivity.
- Entra and CRD check results.
- Stable AZK8S error metadata.
- The connected-cluster ARM resource ID.
- The command correlation used to join command, fault, and extension events.

The resource ID enables side-by-side tests with unique cluster names:

```kusto
| extend CustomProperties = parse_json(Properties)
| extend ResourceId = tostring(
    CustomProperties["context.default.azurecli.resourceid"])
| where ResourceId endswith "/connectedClusters/<cluster-name>"
```

## KPI query guidance

Start with one row per command correlation and join telemetry to it:

```kusto
let Commands =
    RawEventsAzCli
    | where EventName == "azurecli/command"
    | extend CustomProperties = parse_json(Properties)
    | extend CorrelationId = tostring(
        CustomProperties["reserved.datamodel.correlationid"])
    | where tostring(
        CustomProperties["context.default.azurecli.rawcommand"])
        has_all ("connectedk8s", "connect")
    | summarize arg_max(StartTime, *) by CorrelationId;
let Faults =
    RawEventsAzCli
    | where EventName == "azurecli/fault"
    | extend CustomProperties = parse_json(Properties)
    | extend CorrelationId = tostring(split(tostring(
        CustomProperties["reserved.datamodel.correlation.1"]), ",")[0])
    | summarize FaultTypes = make_set(tostring(
        CustomProperties["context.default.azurecli.faulttype"]))
        by CorrelationId;
Commands
| join kind=leftouter Faults on CorrelationId
```

Success and failure KPIs should use the command action result once per
correlation. Fault arrays and extension diagnostics should only explain that
outcome.
