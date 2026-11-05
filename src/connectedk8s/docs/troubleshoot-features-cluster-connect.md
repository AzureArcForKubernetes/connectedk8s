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

Use this path for `AZK8S0800` through `AZK8S0804`. The command performs these
local phases in order:

1. Select and, if absent, download the proxy for the local operating system,
  processor architecture, and extension-pinned proxy version.
2. Select two local ports and reject a conflict before starting the proxy.
3. Replace the extension-managed `config.yml` beside the proxy executable.
4. Ask the operating system to start the proxy process.
5. Exchange Azure tokens and Cluster Connect credentials, register them with
  the local proxy, and write or merge the generated kubeconfig.
6. Check the child process every 60 seconds and refresh credentials before
  they expire.

That order matters: a later code proves the earlier phases completed. For
example, `AZK8S0802` proves the artifact was prepared and configuration was
written, while `AZK8S0804` proves process creation succeeded. Retry with an
unused local API port:

```azurecli
az connectedk8s proxy --resource-group "<resource-group>" --name "<cluster-name>" --port <unused-port> --debug
```

If the detailed error identifies an occupied port, stop the process that owns
it or choose another `--port`. If the proxy starts and then closes, inspect the
child process output made visible by `--debug`, record the UTC failure time,
and correlate both with endpoint-security or EDR events. `--debug` can include
customer identifiers and request details, so sanitize it before sharing.
Never share the generated kubeconfig or proxy configuration.

## `AZK8S0700`: `CustomLocationsEnableFailed`

Custom Locations depends on Cluster Connect, registration of the
`Microsoft.ExtendedLocation` resource provider, and the tenant-specific object
ID of the Custom Locations service principal. During `enable-features`, the
extension checks these prerequisites before loading kubeconfig, downloading
the chart, or running Helm.

`AZK8S0700` is the fatal aggregate for this prerequisite stage. Version 1.11.5
raises it only when Custom Locations couldn't be enabled and no other requested
feature remains. For a mixed request, the extension removes
`custom-locations`, warns, and continues with the remaining features. A later
Helm failure has a `AZK8S05xx` code instead.

Check the selected account and provider state without changing either:

```azurecli
az account show --query "{subscription:id,tenant:tenantId,userType:user.type}" --output yaml
az provider show --namespace Microsoft.ExtendedLocation --query registrationState --output tsv
```

The account output proves which subscription and tenant the next query uses;
it doesn't prove permission to read Microsoft Graph. The provider query must
return `Registered`. A successful query returning another state is different
from `AZK8S0702`, where the query itself raised an exception.

Only after a successful query proves the provider isn't registered, register
it in the intended subscription and monitor the asynchronous state change:

```azurecli
az provider register --namespace Microsoft.ExtendedLocation
az provider show --namespace Microsoft.ExtendedLocation --query "{namespace:namespace,state:registrationState}" --output yaml
```

Provider registration changes subscription state and requires permission for
the provider registration action. Don't run it to troubleshoot a failed
`show` request; correct authentication, subscription selection, authorization,
proxy, or Azure service availability first.

Then retrieve the tenant-specific object ID. The `--id` value below is the
constant application ID documented for the Custom Locations service app; the
returned `id` is the service-principal object ID for the selected tenant:

```azurecli
az ad sp show --id bc313c14-388c-4e7d-a58e-70017303ee3b --query id --output tsv
```

Expect one GUID. Don't pass the constant application ID as
`--custom-locations-oid`. If a Microsoft Entra administrator retrieves the
object ID for a service-principal workflow, transfer it through an approved
channel and retry with that exact value:

```azurecli
az connectedk8s enable-features --resource-group "<resource-group>" --name "<cluster-name>" --features cluster-connect custom-locations --custom-locations-oid "<object-id>"
```

A manually supplied value is a fallback, not proof: when Graph fails, version
1.11.5 uses it without validation and warns that an invalid value might leave
the feature unusable. Custom Locations also requires Cluster Connect and its
network endpoints. Private-link-enabled connected clusters and provisioned
clusters are rejected earlier by separate validation.

The issue is fixed when the provider query returns `Registered`, object-ID
retrieval succeeds or the verified value is supplied, and the same command
advances to and completes Helm feature enablement. Creating a custom location
is a separate operation and shouldn't be used to repair this prerequisite
error.

## `AZK8S0701`: `CustomLocationsOidFetchFailed`

This diagnostic has two source paths:

- Microsoft Graph returned no service principal and no manual object ID was
  supplied. The extension records `AZK8S0701`, returns an empty value, and
  disables Custom Locations for this request.
- The Graph client or lookup raised an exception. The extension records
  `AZK8S0701`; it uses a supplied object ID without validation, or returns an
  empty value when none was supplied.

Because this is reported through diagnostic telemetry rather than raised
directly, the visible command can later fail with `AZK8S0700`, or a mixed
feature request can continue without Custom Locations. Start with read-only
identity and Graph checks:

```azurecli
az account show --query "{tenant:tenantId,userType:user.type}" --output yaml
az ad sp show --id bc313c14-388c-4e7d-a58e-70017303ee3b --query "{objectId:id,appId:appId}" --output yaml
```

The first command identifies the tenant and whether Azure CLI is using a user
or service principal. The second asks Microsoft Graph for the tenant's service
principal. `appId` should equal the constant value in the command, while
`objectId` is the tenant-specific value required by feature enablement. An
empty result differs from HTTP `401`, `403`, timeout, or proxy failure; retain
the sanitized Graph status and request ID because their repairs differ.

For `401`, sign in again to the intended tenant. For `403`, use an approved
Microsoft Entra identity permitted to read the service principal, or have an
administrator retrieve its object ID. For timeout, DNS, TLS, or proxy errors,
repair Azure CLI host connectivity to Microsoft Graph rather than changing
cluster networking. Service-principal sign-in commonly requires the documented
manual-object-ID workflow:

```azurecli
az connectedk8s enable-features --resource-group "<resource-group>" --name "<cluster-name>" --features cluster-connect custom-locations --custom-locations-oid "<object-id>"
```

Use only the `objectId` returned for the intended tenant. Don't guess it,
substitute the application ID, or grant broad directory permissions solely to
avoid the manual workflow. The diagnostic is fixed when Graph returns the
tenant-specific object ID or the exact administrator-verified object ID lets
the request advance.

## `AZK8S0702`: `CustomLocationsRegistrationCheckFailed`

This diagnostic means an exception interrupted the outer Custom Locations
prerequisite helper. Most commonly, creation of the resource-provider client or
the `Microsoft.ExtendedLocation` registration query failed. It can also wrap
an unexpected exception from object-ID retrieval. The helper catches the
exception, disables Custom Locations, and returns control to `enable-features`;
it doesn't raise `AZK8S0702` directly and doesn't prove the provider is
unregistered.

Confirm account scope and repeat only the read operation first:

```azurecli
az account show --query "{subscription:id,tenant:tenantId}" --output yaml
az provider show --namespace Microsoft.ExtendedLocation --query "{namespace:namespace,state:registrationState}" --output yaml --debug
```

The account command catches a wrong active subscription. The provider command
distinguishes a valid state response from authentication, authorization,
network, proxy, or Azure service errors. Use `--debug` only for this
reproduction, and remove tokens, headers, tenant and subscription identifiers,
proxy credentials, and request URLs containing customer data before sharing
the output.

If the query succeeds and returns `Registered`, the registration check is
repaired; continue with `AZK8S0701` if object-ID retrieval fails. If it
succeeds with another state, an authorized subscription administrator can run:

```azurecli
az provider register --namespace Microsoft.ExtendedLocation
az provider show --namespace Microsoft.ExtendedLocation --query registrationState --output tsv
```

Wait for `Registered`; repeated registration requests don't accelerate the
operation. If `show` itself fails, don't register blindly. Correct the reported
`401`, `403`, subscription, proxy, TLS, or service condition and retry the
read. The diagnostic is fixed when the provider query succeeds, returns
`Registered`, and the prerequisite helper can continue to object-ID retrieval.

For support, provide the code, extension version, account type, provider state
or sanitized query error, Graph status when relevant, whether a manual object
ID was supplied, and UTC request or correlation IDs. Don't include access
tokens, proxy credentials, or the tenant-specific object ID in public logs.

## `AZK8S0800`: `ClientProxyDownloadFailed`

This code covers local artifact preparation, not only network download. If the
versioned proxy executable is absent, version 1.11.5 creates or reuses
`~/.clientproxy`, removes older `arcProxy*` files, pulls the OS- and
architecture-specific archive from Microsoft Artifact Registry (MCR), accepts
only the expected proxy and license files from that archive, extracts them,
adds owner-execute permission, and confirms the expected executable exists.
Failure in any of those operations is reported as `AZK8S0800`.

The selected artifact uses the local OS (`windows`, `linux`, or `darwin`), an
architecture derived from the machine (`amd64`, `arm64`, or `386`), and the
proxy version pinned by the extension. Therefore, a successful HTTPS request
to MCR proves only network reachability; it doesn't prove that Azure CLI could
create the directory, extract the archive, or prepare the executable.

### Diagnose proxy preparation

First capture versions and the platform value used to select the artifact:

```azurecli
az version
```

On Windows:

```powershell
$env:PROCESSOR_ARCHITECTURE
[System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
Test-Path -LiteralPath "$HOME\.clientproxy"
Get-PSDrive -PSProvider FileSystem | Select-Object Name,Free
Resolve-DnsName mcr.microsoft.com
Test-NetConnection mcr.microsoft.com -Port 443
```

The architecture values explain which artifact family is needed.
`Test-Path` checks only whether the default installation directory exists,
`Get-PSDrive` checks capacity, and the final two commands separately test DNS
resolution and TCP access to public-cloud MCR. They don't download or execute
the proxy.

On Linux or macOS:

```console
uname -s
uname -m
test -d "$HOME/.clientproxy" && test -w "$HOME/.clientproxy"; echo $?
df -h "$HOME/.clientproxy"
curl -I https://mcr.microsoft.com/v2/
```

Exit code `0` from the directory test means the current identity can write to
an existing directory. `df` checks its filesystem capacity. The `curl` result,
including an HTTP response that requires registry authentication, proves DNS,
TCP, and TLS reached MCR; it doesn't prove the artifact pull or extraction.
If the directory doesn't exist yet, check its parent instead.

Run the original command once with `--debug` to identify whether the failure
occurred during directory cleanup, MCR pull, archive handling, permission
change, or expected-file validation. If MCR access fails, repair the host DNS,
TLS trust, authenticated outbound proxy, or firewall rule according to the
[network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements).
If local preparation fails, correct access for the current identity, free
space, or a lock or quarantine recorded by endpoint security. Don't grant
world-writable permissions, disable endpoint security, or substitute a proxy
binary from another machine.

### Verify proxy preparation

Retry the same `az connectedk8s proxy` command. Reaching `Proxy is listening
on port <port>` or a later-phase error proves the extension prepared its
pinned proxy artifact and `AZK8S0800` is fixed. It doesn't by itself prove
Cluster Connect credential exchange or Kubernetes access succeeded.

For support, provide the sanitized error and debug phase, OS and architecture,
CLI and extension versions, MCR host and connectivity result, free-space
result, endpoint-security event reason, and UTC time. Remove usernames and
profile paths, proxy credentials, tokens, and request headers.

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

The internal port normally remains `47010`, even when `--port` selects a custom
API port. If `47010` is already occupied and a custom API port was supplied,
version 1.11.5 instead selects `<custom-port>-1` for the internal port. For
example, `--port 55000` uses internal port `54999` only when `47010` is already
occupied; otherwise it uses `47010`. The selected API and internal ports must
be different and both must be available. Don't kill an unknown process or a
system process merely to free a port.

### Verify the client proxy ports

The command should report `Proxy is listening on port <port>`, remain running,
and listen on both ports. Retrying is useful after freeing or changing the
port; launching concurrent proxy sessions is not.

### Port conflict support evidence

Provide the sanitized error, requested and internal ports, connection state,
owning process name, UTC timestamp, operating system, and CLI versions. Remove
usernames and profile directories from executable paths.

## `AZK8S0802`: `ClientProxyStartFailed`

This code is raised only when the operating system process-creation call
fails. By this point Azure CLI has selected or prepared the proxy executable,
written `config.yml`, and built the process arguments. It doesn't cover a
proxy that starts and later exits; the 60-second monitor reports that as
`AZK8S0804`.

### Diagnose process creation

Retry once with `--debug` and retain the exact operating-system error, such as
file not found, access denied, invalid executable format, or a security block:

```azurecli
az connectedk8s proxy --resource-group "<resource-group>" --name "<cluster-name>" --port <unused-port> --debug
```

Use the reported executable path only to inspect file metadata. On Windows:

```powershell
Get-Item -LiteralPath "<proxy-executable-path>" |
  Select-Object FullName,Length,LastWriteTime,Attributes
[System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
```

On Linux or macOS:

```console
ls -l "<proxy-executable-path>"
file "<proxy-executable-path>"
uname -m
```

`Get-Item` and `ls` establish that the current identity can see the exact file;
`file` and the architecture commands expose an obvious binary/platform
mismatch without running it. On Unix, the owner execute bit must be present.
On Windows, use the failure time and path to query the organization's
endpoint-security console. Don't invoke the proxy executable directly with
the generated configuration: Azure CLI owns its startup and credential flow.

Correct the specific OS condition. Restore access for the current user rather
than granting broad permissions. If endpoint security quarantined or blocked
the signed artifact, use the approved review and allow process rather than
disabling protection. If the file is truncated, has the wrong architecture,
or is no longer present, stop any proxy session and let the extension retrieve
its pinned artifact again; don't copy or rename a binary from another host.

### Verify process startup

Retry `az connectedk8s proxy`. The line `Proxy is listening on port <port>`
shows that process creation returned successfully, but final verification is
stronger: keep the command running beyond 60 seconds and verify `/version`
through the generated kubeconfig as described under `AZK8S0804`.

For support, provide the sanitized OS error, executable metadata, local OS and
architecture, UTC time, security event reason, and CLI, extension, and proxy
versions. Don't provide `config.yml`, kubeconfig, tokens, or profile paths.

## `AZK8S0803`: `ClientProxyConfigCreateFailed`

Before process startup, version 1.11.5 writes an extension-managed
`config.yml` beside the proxy executable, normally under `~/.clientproxy`. If
the file already exists, Azure CLI removes it first. Therefore this code can
mean either the old file couldn't be removed or its replacement couldn't be
opened and written. The detailed error distinguishes those phases.

The file contains local proxy, cloud, tenant, and identity configuration.
Inspect its metadata, never its contents. Stop an earlier proxy with `Ctrl+C`
before investigating because it may still be using files in the same folder.

### Diagnose configuration replacement

On Windows:

```powershell
Test-Path -LiteralPath "$HOME\.clientproxy"
Test-Path -LiteralPath "$HOME\.clientproxy\config.yml"
Get-Item -LiteralPath "$HOME\.clientproxy" |
  Select-Object FullName,Attributes,LastWriteTime
Get-PSDrive -PSProvider FileSystem | Select-Object Name,Free
```

On Linux or macOS:

```console
test -d "$HOME/.clientproxy" && test -w "$HOME/.clientproxy"; echo $?
test -e "$HOME/.clientproxy/config.yml"; echo $?
ls -ld "$HOME/.clientproxy"
df -h "$HOME/.clientproxy"
```

These commands distinguish a missing or non-writable parent, an existing
configuration that must be replaced, and a full filesystem. They intentionally
don't print the file. The directory needs write permission because replacing
a file is a directory operation; write permission on an existing file alone
isn't sufficient on Unix. A read-only profile, ownership mismatch, active file
lock, filesystem error, or endpoint-security rule can each block replacement.

Correct only the reported condition: stop the confirmed process holding the
file, restore the current user's access to the extension-owned directory, free
space, or use the approved security exception process. Don't use broad
permissions, edit `config.yml`, or publish it in a support bundle. Retry the
Azure CLI command so the extension, rather than a manual editor, regenerates
the complete configuration.

### Verify configuration replacement

The issue is fixed when the retry advances to `Proxy is listening on port
<port>` or a later phase. Verify by process behavior, not by opening
`config.yml`. For support, provide whether removal or write failed, sanitized
path metadata, free-space result, lock or security event, OS, versions, and
UTC time. Redact usernames and never include file contents.

## `AZK8S0804`: `ClientProxyClosed`

The child proxy process exited while `az connectedk8s proxy` was monitoring
it. Version 1.11.5 sleeps for 60 seconds between checks and determines liveness
from the child process status, so the error can appear up to one monitor
interval after the actual exit. The code doesn't distinguish a proxy fault
from endpoint-security or process-management termination.

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

In debug mode, the child process inherits the terminal instead of having its
standard output and error suppressed. If it exits again, retain its final
sanitized output and record the UTC time yourself; `AZK8S0804` doesn't include
an exit code or the original exit time. Correlate that evidence with
endpoint-security or process-management events. Check local capacity on
Windows with:

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

The proxy should remain running beyond at least one 60-second monitoring
interval, both ports should stay in `Listen`, and `/version` should return
`gitVersion`. One retry is reasonable for a transient exit; further retries
aren't useful until the termination cause is identified.

### Proxy exit support evidence

Provide the sanitized error, proxy start and observed-failure UTC times,
ports, process name, child output and exit code if independently available,
endpoint-security event reason, CLI version, and proxy version. Remove tokens,
kubeconfig, proxy configuration, usernames, and credential-bearing URLs.

## `AZK8S0805`: `ClusterCredentialsGetFailed`

This standardized definition is reserved for migration and isn't directly
emitted by the version 1.11.5 credential-retrieval path. That path starts the
proxy and requests hybrid-connection credentials asynchronously. If the ARM
request fails, it terminates the child process, records the legacy
`GetCredentialsFailed` fault type, and lets the ARM exception helper raise an
unnumbered typed Azure CLI error. Authentication and expired-token failures,
HTTP response failures, server failures, and other client failures can
therefore have different legacy error classes even though they occurred at the
same phase. The following fallback `Failed to get credentials` statement isn't
normally reached because the helper raises first.

If a released extension displays `AZK8S0805`, include its extension version
when following this procedure. For 1.11.5, use the same procedure when the
legacy error says the ARM request couldn't list cluster user credentials.

### Diagnose Cluster Connect credentials

```azurecli
az account show --query "{subscription:id,tenant:tenantId,userType:user.type}" --output yaml
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{provisioningState:provisioningState,connectivityStatus:connectivityStatus}" --output yaml
az connectedk8s troubleshoot --resource-group "<resource-group>" --name "<cluster-name>"
```

Expect the correct account scope, `provisioningState: Succeeded`,
`connectivityStatus: Connected`, and passing Cluster Connect diagnostics.
The account query explains which subscription and identity Azure RBAC will
evaluate. The cluster query proves control-plane state but doesn't retrieve
credentials. Troubleshoot checks Arc agents and network prerequisites without
printing the credential response.

### Resolve Cluster Connect credentials

- HTTP `401`: sign in again and select the intended tenant and subscription.
- HTTP `403`: ask an administrator to verify effective Azure permission for
  `Microsoft.Kubernetes/connectedClusters/listClusterUserCredential/action` at
  the connected-cluster resource scope.
- Disconnected state: repair Arc agents and outbound connectivity first.
- Disabled Cluster Connect: enable it with:

```azurecli
az connectedk8s enable-features --resource-group "<resource-group>" --name "<cluster-name>" --features cluster-connect
```

Don't reproduce the credential operation with `az rest`; a successful response
contains credentials that must not be displayed or shared.

### Verify Cluster Connect credentials

Run `az connectedk8s proxy`, keep it running beyond one 60-second monitor
interval, and verify `/version` through its generated context. This proves the
credential request, local registration, and proxied Kubernetes request all
completed; merely seeing the local process start does not. Retry after
transient ARM `5xx`, reconnection, RBAC propagation, or feature enablement.
Repeated retries won't fix persistent `401`, `403`, disconnected state, or a
disabled feature.

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
