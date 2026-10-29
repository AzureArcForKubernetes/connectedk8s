# Troubleshoot cluster access and networking for Azure Arc-enabled Kubernetes

Use this guide for Azure Arc-enabled Kubernetes errors involving kubeconfig,
Kubernetes API access, DNS, and Azure Arc data-plane connectivity. Return to
the [error-code reference](error-codes.md) to look up every `AZK8Snnnn` code.

## Prepare to troubleshoot

Update Azure CLI and the `connectedk8s` extension:

```azurecli
az upgrade
az extension update --name connectedk8s
```

Confirm the active Azure subscription:

```azurecli
az account set --subscription "<subscription-id>"
az account show
```

Confirm that `kubectl` uses the intended cluster and identity:

```console
kubectl config current-context
kubectl cluster-info
kubectl auth can-i get pods --all-namespaces
```

Use the same kubeconfig and context for these checks that you supplied to
Azure CLI. Don't display or share kubeconfig contents, tokens, certificates,
private keys, or customer-identifying API server URLs.

## Check Kubernetes API access

Use this path for `AZK8S0200` and `AZK8S0202`:

```console
kubectl config current-context
kubectl cluster-info
kubectl auth can-i get namespaces
```

If the context is wrong, select the intended context with `kubectl config
use-context <context-name>`. If `kubectl cluster-info` fails, restore VPN or
private-network access and verify API server DNS and firewall rules. If the
authorization check returns `no`, use a kubeconfig identity with the required
cluster permissions before retrying the Azure CLI command.

## Determine whether DNS is blocking connectivity

Use the hostname in the detailed error or diagnostic result. Test it from a
temporary pod so the query uses the cluster DNS path rather than the DNS
configuration on your local computer:

```console
kubectl run arc-dns-check --rm -it --restart=Never --image=registry.k8s.io/e2e-test-images/dnsutils:1.3 --command -- nslookup <hostname>
```

Interpret the result as follows:

- An address is returned: DNS isn't blocking this endpoint. Continue with
  firewall, proxy, TLS, authentication, or service-health checks.
- `NXDOMAIN`: verify the hostname from the error, DNS forwarding zones, and
  private DNS configuration. A public Azure Arc endpoint shouldn't resolve to
  `NXDOMAIN`.
- A timeout or `no servers could be reached`: DNS traffic is likely blocked or
  the configured resolver is unavailable. Check the DNS service, routes,
  network policies, and firewall rules for both UDP and TCP port 53.
- `SERVFAIL`: the resolver was reached but couldn't complete the query. Check
  its upstream forwarders, conditional forwarding rules, and DNSSEC behavior.

If the pod can't be created or its image can't be pulled, run the lookup from
an existing troubleshooting pod that has `nslookup`, or ask the cluster
administrator to run the equivalent query from a node. This failure alone
doesn't prove that DNS is blocked.

After changing DNS configuration, repeat the lookup until it returns an
address, rerun `az connectedk8s troubleshoot`, and then retry the original
command. Delete a retained test pod with `kubectl delete pod arc-dns-check`.

## `AZK8S0200`: `KubeconfigLoadFailed`

The extension couldn't open or parse the kubeconfig file. Use the exact file
passed to `--kube-config`. If that option wasn't supplied, Kubernetes tools use
the paths in `KUBECONFIG`, or the default file at `$HOME/.kube/config` when the
environment variable isn't set.

### Diagnose kubeconfig loading

On Linux or macOS, verify that a single kubeconfig file exists and is readable:

```console
KUBECONFIG_PATH="<path>"
test -f "$KUBECONFIG_PATH" && echo "file exists" || echo "file not found"
test -r "$KUBECONFIG_PATH" && echo "file is readable" || echo "file is not readable"
```

On Windows PowerShell, run:

```powershell
$KubeconfigPath = "<path>"
Test-Path -LiteralPath $KubeconfigPath -PathType Leaf
Get-Item -LiteralPath $KubeconfigPath | Select-Object FullName,Length
$Stream = [System.IO.File]::OpenRead($KubeconfigPath)
$Stream.Dispose()
"file is readable"
```

The checks should find a nonempty, readable file. Next, ask `kubectl` to parse
that file and report its contexts without displaying credentials:

```console
kubectl --kubeconfig "<path>" config get-contexts
kubectl --kubeconfig "<path>" config current-context
```

The first command should list at least one context, and the second should
return the intended context name. A YAML parsing, missing-file, permission,
certificate-file, or missing-current-context error identifies what must be
corrected.

### Resolve kubeconfig loading

- File not found: correct the path or obtain a new kubeconfig from the cluster
  administrator.
- Permission denied: grant the current user read access without making the
  file public.
- YAML parsing error: restore or regenerate the kubeconfig instead of guessing
  at credential or certificate data.
- No current context: select one of the listed contexts with `kubectl
  --kubeconfig "<path>" config use-context "<context>"`.
- Referenced certificate or key file missing: restore the referenced file or
  regenerate the kubeconfig through the cluster's supported credential flow.

### Verify kubeconfig recovery

Run these commands with the same file and context that Azure CLI will use:

```console
kubectl --kubeconfig "<path>" --context "<context>" get --raw=/version
kubectl --kubeconfig "<path>" --context "<context>" cluster-info
```

The `/version` request should return JSON containing `gitVersion`, and
`cluster-info` should list the control plane. If the file now parses but these
commands report an authentication, TLS, DNS, timeout, or connection error,
kubeconfig loading is fixed; continue with
[`AZK8S0202`](#azk8s0202-kubernetesconnectivityfailed).

### Kubeconfig support evidence

Provide the sanitized `AZK8S0200` text, whether the path exists and is
readable, the parsing error category, an aliased context name, operating
system, UTC timestamp, and CLI versions. Never provide the kubeconfig, tokens,
certificates, private keys, or customer-identifying API server URLs.

## `AZK8S0202`: `KubernetesConnectivityFailed`

The extension couldn't complete a Kubernetes `/version` request. The cause can
be authentication, an exec credential plug-in, TLS, DNS, timeout, connection
refusal, VPN, or API server health.

### Diagnose Kubernetes connectivity

Use the same kubeconfig and context supplied to Azure CLI:

```console
kubectl --kubeconfig "<path>" config current-context
kubectl --kubeconfig "<path>" --context "<context>" get --raw=/version
kubectl --kubeconfig "<path>" --context "<context>" auth can-i get namespaces
kubectl --kubeconfig "<path>" --context "<context>" cluster-info
```

Interpret each command as follows:

- `config current-context` reads the kubeconfig locally and prints the context
  that `kubectl` uses by default. It should print the intended context name. If
  it prints another name, pass the intended context explicitly or select it
  before retrying Azure CLI. This command doesn't contact the API server.
- `get --raw=/version` makes the same lightweight Kubernetes API request that
  the extension uses for this connectivity check. JSON containing
  `gitVersion` proves that the client reached the API server and completed TLS
  and authentication. If it fails, use the innermost error, such as
  `Unauthorized`, `x509`, a DNS error, a timeout, or `connection refused`, to
  select the matching resolution below.
- `auth can-i get namespaces` asks the API server whether the current identity
  can list cluster namespaces. `yes` confirms that permission; `no` means the
  identity needs additional authorization. If the API server is unreachable,
  this command can't evaluate authorization and instead reports the same
  connectivity error; don't interpret that result as an RBAC denial.
- `cluster-info` performs an additional API check and should list the
  Kubernetes control plane without an error. A DNS, TLS, authentication,
  timeout, or refused-connection error confirms the corresponding access
  problem; the displayed endpoint alone doesn't prove that it is reachable.

### Resolve Kubernetes connectivity

- `Unauthorized`: obtain a fresh kubeconfig or credentials through the
  cluster provider's supported access flow; don't paste a token into the
  kubeconfig. Rerun `/version` with the refreshed file and context.
- Exec plug-in errors: run `kubectl --kubeconfig "<path>" --context
  "<context>" config view --minify -o
  jsonpath="{.users[0].user.exec.command}{'\n'}"` to identify the configured
  executable without displaying credentials. Install or sign in through that
  plug-in and ensure it is on `PATH`, then rerun `/version`.
- `x509` errors: run `kubectl --kubeconfig "<path>" --context "<context>"
  config view --minify -o
  jsonpath="{.clusters[0].cluster.certificate-authority}{'\n'}"`. If it prints
  a path, confirm that the file exists and is readable. For an expired,
  untrusted, or wrong-server-name certificate, regenerate the kubeconfig
  through the cluster provider instead of disabling TLS verification.
- Timeout or refused connection: read the API server URL with `kubectl
  --kubeconfig "<path>" --context "<context>" config view --minify -o
  jsonpath="{.clusters[0].cluster.server}{'\n'}"`. Test its host and port with
  `Test-NetConnection -ComputerName "<api-host>" -Port <api-port>` on Windows
  or `nc -vz "<api-host>" <api-port>` on Linux or macOS. A failed TCP test
  means VPN, private routing, firewall, load balancer, or API server
  availability must be restored; it isn't an RBAC failure.
- DNS errors: run `Resolve-DnsName "<api-host>"` on Windows or `nslookup
  "<api-host>"` on Linux or macOS. Empty output, `NXDOMAIN`, `SERVFAIL`, or a
  timeout identifies a local or private DNS problem. Correct the applicable
  DNS zone, forwarding rule, resolver route, or VPN-provided DNS settings,
  then repeat the lookup before `/version`.
- Authorization returns `no`: use an identity with the permissions required by
  the original operation.

### Verify Kubernetes connectivity

Retry only after `/version` succeeds with the exact kubeconfig and context used
by Azure CLI. For update, delete, or feature operations, first inspect whether
an earlier stage already changed Azure or Helm state:

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{id:id,provisioningState:provisioningState,agentState:arcAgentProfile.agentState}" --output yaml
```

```console
helm list --all --all-namespaces --filter "^azure-arc$"
helm status azure-arc --namespace "<release-namespace>"
helm get values azure-arc --namespace "<release-namespace>"
```

Interpret the results before retrying:

- The Azure command shows whether the connected-cluster resource still exists
  and whether its latest resource operation succeeded. A `404` during a delete
  means that the Azure resource is already gone; don't retry the deletion just
  to reproduce the original error.
- `helm list` shows whether the `azure-arc` release remains, its namespace, and
  its state. Run `helm status` and `helm get values` only when the list contains
  a release, using the namespace from that row. Status shows release health and
  managed resources; saved values show whether an update or feature setting
  was applied.
- If the Azure resource reports `Succeeded` and Helm reports `deployed`, check
  whether the setting or feature requested by the original command is already
  present. If it is, don't repeat the operation.
- If only one side changed, or Helm reports `failed`, `pending-*`, or
  `uninstalling`, treat the operation as partially completed. Follow the
  procedure for that operation or contact support instead of repeatedly
  retrying or manually deleting Azure or Kubernetes resources.

Don't share unsanitized command output; resource IDs, user names, proxy
settings, and other customer-specific values can appear in diagnostics.

### Kubernetes connectivity support evidence

Provide the sanitized `AZK8S0202` text, exception category, an aliased context
name, `/version` and authorization results, UTC timestamp, and whether VPN or
private networking was active. Never provide kubeconfig, tokens, certificates,
private keys, or customer-identifying API URLs.

## `AZK8S0300`: `DataPlaneHealthCheckFailed`

This check sends an authenticated request from the computer running Azure CLI
to the regional Azure Arc data-plane endpoint. It doesn't test connectivity
from the cluster nodes.

### Diagnose the data-plane check

First confirm the active cloud, subscription, and connected-cluster region:

```azurecli
az account show --query "{subscription:id,cloud:environmentName,user:user.name}" --output yaml
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{location:location,provisioningState:provisioningState}" --output yaml
```

Rerun the failing command with `--debug` and locate the data-plane hostname and
HTTP status or transport error. From the same computer, resolve the reported
hostname:

```console
nslookup <data-plane-hostname>
```

### Resolve the data-plane failure

Use the result to choose the correction:

- DNS failure: repair DNS or proxy DNS resolution on the Azure CLI computer.
- Timeout or refused connection: allow outbound TCP 443 to the regional Azure
  Arc data-plane endpoint listed in the [network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements).
- TLS or certificate error: add the required issuing certificate chain to the
  local trust store or the intercepting proxy. Don't use
  `--skip-ssl-verification` as a permanent correction.
- HTTP `401` or `403`: run `az login` again if needed, select the correct tenant
  and subscription, and verify Azure RBAC access to the connected cluster.
- HTTP `429` or `5xx`: retry with backoff and check Azure service health if the
  response persists.

### Verify data-plane recovery

An unauthenticated browser or `curl` response doesn't reproduce this health
check. Verify the correction by retrying the original command, then run:

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{provisioningState:provisioningState,connectivityStatus:connectivityStatus}" --output yaml
```

Expect `provisioningState: Succeeded`. A newly connected cluster can briefly
report `Connecting`; it should progress to `Connected`.

### Data-plane support evidence

Provide the sanitized debug output, UTC timestamp, hostname, HTTP status or
transport error, cloud and region, DNS result, and whether a proxy performs TLS
inspection.

## Related content

- [Azure Arc-enabled Kubernetes error-code reference](error-codes.md)
- [Azure Arc-enabled Kubernetes network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements)
- [Diagnose connection issues for Azure Arc-enabled Kubernetes clusters](https://learn.microsoft.com/azure/azure-arc/kubernetes/diagnose-connection-issues)
