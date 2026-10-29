# Troubleshoot features and Cluster Connect for Azure Arc-enabled Kubernetes

Use this guide for Azure Arc-enabled Kubernetes errors involving Custom
Locations, Cluster Connect credentials, and the local client proxy. Return to
the [error-code reference](error-codes.md) to look up every `AZK8Snnnn` code.

## Check Cluster Connect prerequisites

```azurecli
az account show --query "{subscription:id,user:user.name}" --output yaml
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{provisioningState:provisioningState,connectivityStatus:connectivityStatus}" --output yaml
```

Confirm that the selected subscription contains the connected cluster, the
resource provisioning state is `Succeeded`, and the connectivity status is
`Connected`. Then verify that the signed-in identity has an Azure role that
permits Cluster Connect credential retrieval. If the state is disconnected,
run `az connectedk8s troubleshoot` and fix agent or outbound-connectivity
errors before retrying `az connectedk8s proxy`.

## Check client proxy startup

Use this path for `AZK8S0801` through `AZK8S0804`. Retry with an unused local
port:

```azurecli
az connectedk8s proxy --resource-group "<resource-group>" --name "<cluster-name>" --port <unused-port> --debug
```

If the detailed error identifies an occupied port, stop the process that owns
it or choose another `--port`. If the proxy starts and then closes, inspect the
terminal's debug output for the proxy executable path, exit code, and UTC exit
time. Use that path and time to search the endpoint-security or EDR console for
a blocked, quarantined, or terminated process. Don't share the generated
kubeconfig or proxy configuration.

## `AZK8S0700`: `CustomLocationsEnableFailed`

This error occurs while validating Custom Locations prerequisites. It is
separate from a later Helm failure, which reports `AZK8S0500`.

### Diagnose Custom Locations prerequisites

Confirm the resource provider is registered and identify the Azure account
type:

```azurecli
az provider show --namespace Microsoft.ExtendedLocation --query registrationState --output tsv
az account show --query user.type --output tsv
```

The provider must report `Registered`. If it doesn't, register it and wait for
registration to finish:

```azurecli
az provider register --namespace Microsoft.ExtendedLocation
az provider show --namespace Microsoft.ExtendedLocation --query registrationState --output tsv
```

### Resolve Custom Locations prerequisites

If the detailed error says the Custom Locations service-principal object ID
couldn't be read, use a Microsoft Entra identity permitted to read service
principals to retrieve it:

```azurecli
az ad sp show --id bc313c14-388c-4e7d-a58e-70017303ee3b --query id --output tsv
```

The expected result is a GUID. Use that returned object ID, not application ID
`bc313c14-388c-4e7d-a58e-70017303ee3b`, when retrying:

```azurecli
az connectedk8s enable-features --resource-group "<resource-group>" --name "<cluster-name>" --features cluster-connect custom-locations --custom-locations-oid "<object-id>"
```

Custom Locations requires Cluster Connect and its network endpoints. It isn't
supported for private-link-enabled connected clusters or provisioned clusters.
A manually supplied object ID can't be validated during feature enablement, so
copy it directly from the query result.

### Verify Custom Locations enablement

Successful feature enablement completes without an `AZK8S` error. Then retry
creation of the intended custom location.

### Custom Locations support evidence

Provide the provider state, account type, sanitized Microsoft Graph error,
whether an object ID was supplied, connected-cluster provisioning and
connectivity state, and Arc agent status.

## `AZK8S0801`: `ClientProxyPortInUse`

The requested local API port or the proxy's internal port is already in use.
The default ports are `47011` and `47010`, respectively.

### Diagnose the occupied port

On Windows, identify the owning process without stopping it:

```powershell
Get-NetTCPConnection -LocalPort <port-from-error> -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,State,OwningProcess
Get-Process -Id <owning-process-id> | Select-Object Id,ProcessName,Path
```

On Linux or macOS, use an available command:

```console
ss -tanp "sport = :<port-from-error>"
lsof -nP -iTCP:<port-from-error>
```

### Resolve the occupied port

Stop an existing proxy cleanly with `Ctrl+C`, stop the confirmed owning
application, or select an unused API port:

```azurecli
az connectedk8s proxy --resource-group "<resource-group>" --name "<cluster-name>" --port <unused-port>
```

When a custom API port is used, the implementation can use
`<custom-port>-1` as its internal port, so both must be available. Don't kill
an unknown process or a system process merely to free the port.

### Verify the client proxy ports

The command should report `Proxy is listening on port <port>`, remain running,
and listen on both ports. Retrying is useful after freeing or changing the
port; launching concurrent proxy sessions is not.

### Port conflict support evidence

Provide the sanitized error, requested and internal ports, connection state,
owning process name, UTC timestamp, operating system, and CLI versions. Remove
usernames and profile directories from executable paths.

## `AZK8S0804`: `ClientProxyClosed`

The child proxy process exited while `az connectedk8s proxy` was monitoring
it. The code doesn't distinguish a crash from endpoint-security or
process-management termination.

### Diagnose the proxy exit

Retry once with an unused port and debug logging:

```azurecli
az connectedk8s proxy --resource-group "<resource-group>" --name "<cluster-name>" --port <unused-port> --debug
```

While it runs, confirm both ports are listening. On Windows:

```powershell
Get-NetTCPConnection -LocalPort <api-port>,<internal-port> -State Listen |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

Then test the generated context without displaying its credentials:

```console
kubectl --kubeconfig "<generated-path>" --context "<generated-context>" get --raw=/version
```

### Resolve the proxy exit

If the process exits again, use the executable path, exit code, and UTC time
from debug stderr to correlate the exit with endpoint-security or
process-management events. Check local capacity on Windows with:

```powershell
Get-PSDrive -PSProvider FileSystem
Get-CimInstance Win32_OperatingSystem |
  Select-Object FreePhysicalMemory,TotalVisibleMemorySize
```

On Linux, run:

```console
df -h "$HOME/.azure"
free -h
```

On macOS, run `df -h "$HOME/.azure"` and inspect memory pressure in Activity
Monitor. A full filesystem or exhausted memory identifies a local capacity
problem. If capacity is available but the security product records a block or
termination for the same signed binary and time, request an approved exception
through the organization's security process. Don't disable endpoint security,
run parallel proxy sessions, or share the generated kubeconfig.

### Verify the client proxy process

The proxy should remain running beyond the monitoring interval, both ports
should stay in `Listen`, and `/version` should return `gitVersion`. One retry is
reasonable for a transient exit; further retries aren't useful until the
termination cause is identified.

### Proxy exit support evidence

Provide the sanitized error, proxy start and exit UTC times, ports, process
name and exit code if available, endpoint-security event reason, CLI version,
and proxy version. Remove tokens, kubeconfig, proxy configuration, usernames,
and credential-bearing URLs.

## `AZK8S0805`: `ClusterCredentialsGetFailed`

This code is reserved for migration and isn't emitted by the current
credential-retrieval path. If a released extension displays it, include the
extension version when following this intended procedure.

### Diagnose Cluster Connect credentials

```azurecli
az account show --query "{subscription:id,tenant:tenantId,userType:user.type}" --output yaml
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{provisioningState:provisioningState,connectivityStatus:connectivityStatus}" --output yaml
az connectedk8s troubleshoot --resource-group "<resource-group>" --name "<cluster-name>"
```

Expect the correct account scope, `provisioningState: Succeeded`,
`connectivityStatus: Connected`, and passing Cluster Connect diagnostics.

### Resolve Cluster Connect credentials

- HTTP `401`: sign in again and select the intended tenant and subscription.
- HTTP `403`: ask an administrator to verify effective Azure permission for
  the connected-cluster credential action at the resource scope.
- Disconnected state: repair Arc agents and outbound connectivity first.
- Disabled Cluster Connect: enable it with:

```azurecli
az connectedk8s enable-features --resource-group "<resource-group>" --name "<cluster-name>" --features cluster-connect
```

Don't reproduce the credential operation with `az rest`; a successful response
contains credentials that must not be displayed or shared.

### Verify Cluster Connect credentials

Run `az connectedk8s proxy`, keep it running, and verify `/version` through its
generated context. Retry after transient ARM `5xx`, reconnection, RBAC
propagation, or feature enablement. Repeated retries won't fix persistent
`401`, `403`, disconnected state, or a disabled feature.

### Cluster credential support evidence

Provide the legacy exception or `AZK8S0805` text, sanitized ARM and HTTP status,
correlation or request IDs, provisioning and connectivity states,
authentication type, UTC timestamp, and versions. Never include returned
credentials, kubeconfig, tokens, tenant or subscription IDs, or hybrid
connection data without redaction.

## Related content

- [Azure Arc-enabled Kubernetes error-code reference](error-codes.md)
- [Create and manage custom locations on Azure Arc-enabled Kubernetes](https://learn.microsoft.com/azure/azure-arc/kubernetes/custom-locations)
- [Azure Arc-enabled Kubernetes network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements)
