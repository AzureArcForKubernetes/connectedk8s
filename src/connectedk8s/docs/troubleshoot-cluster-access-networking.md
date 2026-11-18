# Troubleshoot cluster access and networking for Azure Arc-enabled Kubernetes

Use this guide for Azure Arc-enabled Kubernetes errors involving kubeconfig,
Kubernetes API access, DNS, and Azure Arc data-plane connectivity. Return to
the [error-code reference](error-codes.md) to look up every `AZK8Snnnn` code.

## Before troubleshooting

Run all checks from the same computer, shell, network, kubeconfig, and context
used by the failing command. Record the installed versions before changing the
environment:

```azurecli
az version
az extension show --name connectedk8s --query version --output tsv
kubectl version --client
```

Update Azure CLI and the extension if they aren't current, then confirm the
active Azure context:

```azurecli
az upgrade
az extension update --name connectedk8s
az account set --subscription "<subscription-id>"
az account show --query "{subscription:id,tenant:tenantId}" --output yaml
```

### Confirm cluster access

Use the exact kubeconfig and context supplied to Azure CLI:

```console
kubectl --kubeconfig "<path>" config get-contexts "<context>"
kubectl --kubeconfig "<path>" config current-context
kubectl --kubeconfig "<path>" --context "<context>" get --raw=/version
kubectl --kubeconfig "<path>" --context "<context>" auth can-i get namespaces
kubectl --kubeconfig "<path>" --context "<context>" cluster-info
```

The context list must contain the context supplied to Azure CLI. The current
context is the file's saved default and can differ when Azure CLI was given an
explicit `--kube-context` value. `/version` must return JSON containing
`gitVersion`, the authorization check must return `yes`, and `cluster-info`
must list the control plane. A connectivity error from the authorization check
isn't an RBAC denial because the API server didn't answer.

### Check an existing Arc installation

For update, delete, proxy, or feature operations, inspect Azure and Helm state
before retrying:

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{id:id,provisioningState:provisioningState,agentState:arcAgentProfile.agentState}" --output yaml
```

```console
helm list --kubeconfig "<path>" --kube-context "<context>" --all-namespaces --deployed --failed --pending --uninstalling --uninstalled --superseded --filter "^azure-arc$"
```

The Azure result identifies the connected-cluster resource and its latest
state. The Helm result identifies whether an Arc release exists and its
namespace and status. Don't install Helm only for this check when the failing
environment doesn't otherwise require a local Helm client; follow the
operation-specific procedure instead.

For an existing connected cluster, run the supported self-diagnostic command:

```azurecli
az connectedk8s troubleshoot --resource-group "<resource-group>" --name "<cluster-name>" --kube-config "<path>" --kube-context "<context>"
```

This command creates an `arc_diagnostic_logs` folder and prints its path. The
folder can contain Kubernetes descriptions, events, logs, Helm values, and
Azure resource identifiers. Keep it private. Before sharing it through an
approved support channel, remove credentials and replace customer identifiers,
internal names, addresses, and proxy details with descriptive placeholders.
Delete the local copy when it is no longer needed.

During first-time onboarding, `connect` runs pre-onboarding diagnostics. Keep
the specific `AZK8S0300`-series DNS or outbound result together with the
`AZK8S0600`-series orchestration result. The specific code identifies the
failed check; the `AZK8S0600`-series code identifies why the diagnostic stage
stopped. Don't replace both with a generic connection failure.

Don't display or share kubeconfig contents, tokens, certificates, private
keys, proxy credentials, or customer-identifying API server URLs.

## Restore Kubernetes API access

Use this path for `AZK8S0200` and `AZK8S0202`:

If the context is wrong, pass `--kube-context "<context-name>"` to the Azure
CLI command, or run `kubectl --kubeconfig "<path>" config use-context
"<context-name>"`. If `kubectl cluster-info` fails, reconnect through the
organization's approved VPN or private-network method, then verify the API
server host's DNS resolution and TCP port. If the authorization check returns
`no`, ask the cluster administrator to grant the operation-specific
permissions to the kubeconfig identity. Retry only after the authorization
check returns `yes`.

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
  can get namespace resources. `yes` confirms that permission; `no` means the
  identity needs additional authorization. If the API server is unreachable,
  this command can't evaluate authorization and instead reports the same
  connectivity error. It might also warn that the server doesn't have a
  `namespaces` resource type because API discovery failed. Don't interpret
  either result as an RBAC denial.
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
  isn't an RBAC failure. Confirm that the URL still matches the cluster's
  current API endpoint by using the cluster provider's supported management
  tool or asking the cluster administrator. If it doesn't match, obtain or
  regenerate the kubeconfig through the provider's supported access flow;
  don't guess at the server URL or edit credential data. If it does match,
  restore the required VPN, private route, firewall path, load balancer, or API
  server availability. Repeat the TCP test, then rerun `/version` with the
  same kubeconfig and context. To obtain current access information, use the
  cluster provider's portal or documentation and look for its **Connect**,
  **Get credentials**, or **Download kubeconfig** workflow. Ask the cluster
  administrator when credentials are centrally managed. Save a new kubeconfig
  to a private path instead of overwriting or displaying the old file.
- Local tunnel endpoint: if the kubeconfig server is `127.0.0.1`, `localhost`,
  or another loopback address, API access depends on a listener on the same
  host where Azure CLI runs. That listener might belong to a provider tunnel,
  port-forward, or local Kubernetes cluster. Confirm which process the
  provider expects and whether it is running on the kubeconfig port. Restart
  that process through its supported command. If the provider no longer uses
  that loopback address or port, obtain a current kubeconfig instead. Rerun
  `/version` before retrying onboarding.
- Host proxy interception: if `HTTPS_PROXY` is set and `/version` reports a
  proxy connection, `502`, TLS, or certificate error, add only the exact API
  server host to both `NO_PROXY` and `no_proxy` for the Azure CLI process. For
  a loopback endpoint, include `127.0.0.1` and `localhost`. For example:

  ```powershell
  $env:NO_PROXY = "$env:NO_PROXY,<api-host>"
  $env:no_proxy = $env:NO_PROXY
  ```

  ```bash
  export NO_PROXY="${NO_PROXY:+$NO_PROXY,}<api-host>"
  export no_proxy="$NO_PROXY"
  ```

  Don't bypass the proxy for unrelated hosts or broad address ranges. Rerun
  `/version` in the same process environment before retrying Azure CLI.
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
helm list --all-namespaces --deployed --failed --pending --uninstalling --uninstalled --superseded --filter "^azure-arc$"
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

## `AZK8S0203`: `KubernetesDistributionDetectionFailed`

During `az connectedk8s connect`, the extension lists the cluster's nodes and
uses labels, annotations, and provider IDs to recognize distributions such as
AKS, EKS, GKE, OpenShift, kind, and Rancher. `AZK8S0203` means the node-list
request returned, but an unexpected or incomplete node field prevented those
heuristics from finishing. It doesn't mean that a known distribution wasn't
recognized: a valid but unknown distribution is classified as `generic`
without this warning.

`AZK8S0203` is non-fatal. The extension warns, uses `generic`, and continues
onboarding. Therefore, a later error belongs to the later step named by that
error and doesn't make `AZK8S0203` fatal.

### Diagnose distribution detection

Use the exact kubeconfig and context supplied to the failing `connect` command:

```console
kubectl --kubeconfig "<path>" --context "<context>" get --raw=/version
kubectl --kubeconfig "<path>" --context "<context>" get nodes -o custom-columns="NAME:.metadata.name,OS:.metadata.labels.kubernetes\.io/os,ARCH:.metadata.labels.kubernetes\.io/arch,PROVIDER-ID:.spec.providerID"
```

The first command confirms that the Kubernetes API is reachable. The second
uses the same node-list API that supplies distribution detection but displays
only the fields useful for this diagnosis. It doesn't display kubeconfig
credentials or complete node annotations.

Interpret the results as follows:

- An authentication, TLS, DNS, timeout, or connection error means API access
  must be restored; follow
  [`AZK8S0202`](#azk8s0202-kubernetesconnectivityfailed).
- A `Forbidden` node-list response means the kubeconfig identity needs
  permission to list nodes. Check it with `kubectl --kubeconfig "<path>"
  --context "<context>" auth can-i list nodes`; this must return `yes`.
- A successful node list proves discovery works, but doesn't prove that every
  returned field can be parsed by the detector. Missing values appear as
  `<none>`. Don't edit Node objects merely to satisfy the heuristic.

### Resolve distribution detection

List the accepted values without guessing a spelling:

```azurecli
az connectedk8s connect --help
```

If the cluster's actual distribution appears in the `--distribution` allowed
values, add that value to the original `connect` command. An explicit value
bypasses automatic distribution detection. Keep the original kubeconfig,
context, resource group, name, location, and other settings unchanged.

If the actual distribution isn't listed, don't supply a different platform.
Because the extension already falls back to `generic`, allow the command to
continue. If onboarding later fails, troubleshoot the later error code. If
correct platform classification is required or the same warning repeats with
the latest extension, collect sanitized debug output and contact support.

### Verify distribution detection

Retry the original `connect` command after adding the correct explicit
`--distribution` value. The issue is fixed when `AZK8S0203` is absent and the
command advances beyond `Determining Cluster Distribution and Infrastructure`.
The command can still stop on an independent ownership, Azure, Helm, or
diagnostic error; handle that error separately.

Provide support with the sanitized `AZK8S0203` text, CLI and extension
versions, actual Kubernetes distribution and version, aliased node names, and
whether the displayed OS, architecture, or provider ID fields were missing.
Don't provide kubeconfig contents, tokens, certificates, private keys, complete
node annotations, or customer-identifying API server URLs.

## `AZK8S0204`: `KubernetesNamespaceGetFailed`

This code applies specifically to the `azure-arc` namespace. Its severity and
the expected namespace state depend on the operation:

- During `az connectedk8s connect`, the extension reads `azure-arc` before it
  adds Helm ownership metadata and creates or updates the onboarding private-key
  Secret. A non-`404` read failure stops the command with `AZK8S0204`. A `404`
  doesn't produce this code; onboarding proceeds to create the namespace.
- During `az connectedk8s delete`, Helm removal can delete `azure-arc`. The
  extension then lists namespaces until `azure-arc` disappears. If every
  lookup fails for three minutes, the extension reports `AZK8S0204` as a
  warning and continues cleanup. By then, Azure or Helm state can already have
  changed, so don't blindly rerun the delete.

### Diagnose an onboarding namespace read

Use the exact kubeconfig and context supplied to `connect`:

```console
kubectl --kubeconfig "<path>" --context "<context>" get --raw=/version
kubectl --kubeconfig "<path>" --context "<context>" auth can-i get namespace/azure-arc --all-namespaces
kubectl --kubeconfig "<path>" --context "<context>" get namespace azure-arc -o name
```

The `/version` request separates general API connectivity from this namespace
operation. The authorization review predicts whether the identity can perform
the read, but it doesn't perform the read itself. The final command is the
decisive check: it must return `namespace/azure-arc`, or `NotFound` when this is
a new onboarding and the namespace hasn't been created yet.

Interpret other results as follows:

- `Forbidden`: grant the kubeconfig identity `get` access to the cluster-scoped
  `namespaces` resource. If `auth can-i` says `yes` but the read is still
  forbidden, inspect the detailed API authorization-webhook or access-proxy
  error; the successful authorization review doesn't override the failed read.
- An authentication, TLS, DNS, timeout, or connection error: follow
  [`AZK8S0202`](#azk8s0202-kubernetesconnectivityfailed).
- Any other API error: correct the API server, authorization-webhook, or proxy
  failure named in the response. Don't create, delete, or relabel `azure-arc`
  merely to make this read succeed.

After correcting access, retry the original `connect` command with the same
arguments. `AZK8S0204` is fixed when the command passes the namespace read. A
later `AZK8S0208` means the read succeeded but a separate namespace or Secret
write failed; troubleshoot that code instead.

### Diagnose namespace lookup after delete

First determine what the original delete already changed:

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{id:id,state:provisioningState}" --output yaml
```

```console
helm list --all-namespaces --deployed --failed --pending --uninstalling --uninstalled --superseded --filter "^azure-arc$"
kubectl --kubeconfig "<path>" --context "<context>" auth can-i list namespaces --all-namespaces
kubectl --kubeconfig "<path>" --context "<context>" get namespace azure-arc -o name
```

For delete cleanup, `NotFound` from the final command is the expected result:
the namespace is gone. If the namespace remains, inspect its status with
`kubectl get namespace azure-arc`; correct the access or controller failure
named by the API response, but don't clear finalizers generically. If Azure
reports `ResourceNotFound`, Helm has no `azure-arc` row, and the namespace is
absent, deletion is already complete and must not be retried.

Provide support with the sanitized `AZK8S0204` text, operation name, CLI and
extension versions, aliased context name, `/version`, authorization, namespace
read, Azure resource state, and Helm status results. Don't provide kubeconfig
contents, tokens, certificates, private keys, Secret data, or
customer-identifying API server URLs.

## `AZK8S0205`: `LinuxNodeNotFound`

Azure Arc agents run as Kubernetes workloads and require a Linux node on which
they can be scheduled. During `connect`, the extension checks the
`kubernetes.io/os` label returned for every Node. If none equals `linux`, it
reports `AZK8S0205` as a warning and continues. Continuing doesn't make the
capacity problem harmless: Helm can install the workloads, but their pods can
remain Pending when no usable Linux node exists.

### Diagnose Linux scheduling capacity

Use the same kubeconfig and context as the failing `connect` command:

```console
kubectl --kubeconfig "<path>" --context "<context>" auth can-i list nodes
kubectl --kubeconfig "<path>" --context "<context>" get nodes -l kubernetes.io/os=linux -o custom-columns="NAME:.metadata.name,READY:.status.conditions[?(@.type=='Ready')].status,UNSCHEDULABLE:.spec.unschedulable,ARCH:.metadata.labels.kubernetes\.io/arch"
```

The first command asks Kubernetes whether this identity can list the
cluster-scoped Node resource; it must return `yes`. The second performs the
actual list and filters for the same label and value that the extension tests.
It doesn't display node annotations or credentials.

Interpret the result as follows:

- `Forbidden`: grant this kubeconfig identity permission to list Nodes, then
  retry the list. An unseen Linux node can't satisfy the extension's check.
- No rows: add a supported Linux worker node or repair its kubelet-reported OS
  label. Don't relabel a Windows node as Linux; the label must describe the
  node's real operating system.
- A row with `READY` other than `True`: repair that node before relying on it
  for Arc agents.
- `UNSCHEDULABLE` equal to `true`: uncordon an appropriate node only after
  confirming that doing so matches the cluster operator's intent.

Retry the original `connect` command. The warning is fixed when `AZK8S0205` is
absent. For an existing installation, also run `kubectl get pods -n azure-arc`
and confirm the Arc pods aren't Pending because of node selection, taints, or
insufficient capacity.

## `AZK8S0206`: `ClusterRoleBindingCreateForbidden`

Arc onboarding installs cluster-scoped RBAC objects through Helm. Before doing
that work, the extension submits a Kubernetes `SelfSubjectAccessReview` asking
whether the current kubeconfig identity may `create` the
`clusterrolebindings` resource in the `rbac.authorization.k8s.io` API group.
This review is predictive and doesn't create, modify, or reserve a
ClusterRoleBinding.

### Diagnose the authorization result

Use the same kubeconfig and context as `connect`:

```console
kubectl --kubeconfig "<path>" --context "<context>" auth can-i create clusterrolebindings.rbac.authorization.k8s.io
```

Expected output is `yes`. `no` means Kubernetes evaluated the identity and
denied the requested verb. An API, authentication, TLS, or timeout error means
the review couldn't be completed; fix that underlying access problem rather
than treating it as an explicit RBAC denial.

Because ClusterRoleBindings are cluster-scoped, a RoleBinding within one
namespace can't grant this operation. Ask a cluster administrator to grant the
onboarding identity the permission required by the Azure Arc prerequisites,
following the organization's least-privilege process. Don't create an
unrelated binding merely to make `auth can-i` return `yes`, and don't grant
permanent `cluster-admin` access when the organization's approved onboarding
role is narrower.

Retry the same `auth can-i` command and then the original `connect` command.
`AZK8S0206` is fixed when the answer is `yes` and onboarding advances beyond
`Checking if user can create ClusterRoleBindings`. Helm can still encounter a
later, independent admission-policy or RBAC write failure; troubleshoot that
later error separately.

## `AZK8S0207`: `KubernetesConfigurationLoadFailed`

This code belongs to the local credential-merge path used by
`az connectedk8s proxy`. After Cluster Connect returns a temporary kubeconfig,
the extension loads both that kubeconfig and the local merge target. A local
read or parsing failure can produce `AZK8S0207` before the new context is
written. This differs from `AZK8S0200`, which occurs when a lifecycle command
initially loads the kubeconfig it will use to contact Kubernetes.

### Diagnose the merge target

Identify the output path supplied to the failing proxy command. Don't print or
share the file because kubeconfigs can contain credentials and certificates.
On Linux or macOS, check the file and parent directory:

```console
test -r "<merge-target>" && echo readable
test -w "<merge-target>" && echo writable
test -w "$(dirname "<merge-target>")" && echo parent-writable
kubectl --kubeconfig "<merge-target>" config get-contexts
kubectl --kubeconfig "<merge-target>" config current-context
```

On Windows PowerShell, use:

```powershell
Test-Path -LiteralPath "<merge-target>" -PathType Leaf
kubectl --kubeconfig "<merge-target>" config get-contexts
kubectl --kubeconfig "<merge-target>" config current-context
```

An existing target must be readable, writable, and valid kubeconfig YAML. The
parent directory must be writable when the target needs to be created or
replaced. Correct file ownership or permissions using the operating system's
approved administration process, repair malformed YAML from a trusted backup,
or select a new private output path owned by the current user. Don't weaken
permissions on a shared kubeconfig and don't paste its contents into a ticket.

Retry the same `az connectedk8s proxy` command with the repaired path. The
issue is fixed when the context merge succeeds without `AZK8S0207` and
`kubectl --kubeconfig "<merge-target>" config get-contexts` lists the new
context. A later proxy connection error is independent of the local merge.

## `AZK8S0208`: `KubernetesPrivateKeyInjectionFailed`

Newer Arc agents receive the onboarding private key through the
`azure-arc-connect-privatekey` Secret instead of a Helm value. Before Helm
installation, `connect` performs these operations:

1. Read `namespace/azure-arc`.
2. Create the namespace when it is absent, or patch an existing namespace with
   Helm ownership labels and annotations.
3. Create `secret/azure-arc-connect-privatekey`, or replace it when it already
   exists.

The detailed error identifies which stage failed. The private key is generated
for onboarding; don't reconstruct it, print it, or manually put it in a
command.

### Diagnose the named write

Use the same kubeconfig and context as `connect`:

```console
kubectl --kubeconfig "<path>" --context "<context>" get namespace azure-arc -o name
kubectl --kubeconfig "<path>" --context "<context>" auth can-i create namespaces
kubectl --kubeconfig "<path>" --context "<context>" auth can-i patch namespace/azure-arc
kubectl --kubeconfig "<path>" --context "<context>" get secret azure-arc-connect-privatekey -n azure-arc -o name
kubectl --kubeconfig "<path>" --context "<context>" auth can-i create secrets -n azure-arc
kubectl --kubeconfig "<path>" --context "<context>" auth can-i update secret/azure-arc-connect-privatekey -n azure-arc
```

Use only the checks that match the detailed failure:

- Namespace `NotFound`: `create namespaces` must return `yes`.
- Existing namespace adoption failed: `patch namespace/azure-arc` must return
  `yes`.
- Secret `NotFound`: `create secrets` in `azure-arc` must return `yes`.
- Existing Secret replacement failed: `update` on that Secret must return
  `yes`.

The `auth can-i` checks predict authorization but don't perform the write. If
the applicable check says `yes`, use the API response in the detailed error to
correct the named quota, admission policy, access proxy, or namespace state.
Don't delete the namespace or Secret as a generic repair; either can belong to
an existing or interrupted Arc installation. The `-o name` reads above prove
existence without displaying Secret data.

Retry the original `connect` command. The issue is fixed when the command
passes the exact namespace or Secret stage named in the original error. A
later error is independent and doesn't invalidate that repair.

## `AZK8S0209`: `ConfigMapWriteFailed`

The connectedk8s extension uses
`configmap/container-azm-ms-agentconfig` in `kube-system` for the Container
Insights proxy bypass. This isn't the Arc `azure-clusterconfig` ConfigMap.
When a command adds or clears the `Microsoft.AzureMonitor.Containers` bypass,
the extension reads the ConfigMap, then:

- creates it when absent and a bypass must be enabled; or
- replaces it to enable, update, or remove the CLI-owned bypass setting while
  retaining unrelated settings.

The operation word in `AZK8S0209` states whether `create`, `update`, or bypass
removal failed. Explicit connect and update paths stop on this error. Some
cleanup paths can report removal failure diagnostically and continue, so check
the final command result as well as the code.

### Diagnose the ConfigMap write

Use the same kubeconfig and context as the failing command:

```console
kubectl --kubeconfig "<path>" --context "<context>" auth can-i get configmap/container-azm-ms-agentconfig -n kube-system
kubectl --kubeconfig "<path>" --context "<context>" get configmap container-azm-ms-agentconfig -n kube-system -o name
kubectl --kubeconfig "<path>" --context "<context>" auth can-i create configmaps -n kube-system
kubectl --kubeconfig "<path>" --context "<context>" auth can-i update configmap/container-azm-ms-agentconfig -n kube-system
```

`get` permission is required to preserve existing settings. If the read returns
`NotFound` and the error says `create`, the create check must return `yes`. If
the ConfigMap exists, or the error says `update` or remove, the update check
must return `yes` because the Kubernetes client replaces the ConfigMap. If the
required checks say `yes`, correct the quota, admission-policy, access-proxy,
or resource-version conflict named in the API response.

Use `-o name` because only existence and access are needed. If local inspection
of the ConfigMap data is necessary, don't share it without replacing
customer-specific values. Don't delete or overwrite the entire ConfigMap: the
Container Insights agent or cluster operator can own settings unrelated to the
proxy bypass.

Retry the same add or clear operation. `AZK8S0209` is fixed when that operation
completes the ConfigMap write and the code is absent. If the original command
was cleanup and continued after a diagnostic warning, first inspect the final
Azure, Helm, and namespace state before deciding whether any retry is needed.

## `AZK8S0300`: `DataPlaneHealthCheckFailed`

This check sends an authenticated request from the computer running Azure CLI
to the regional Azure Arc data-plane endpoint. `connect`, `update`, and the
gateway-related update path perform this check before retrieving Helm values
and the chart location. The request is an HTTP POST to
`azure-arc-k8sagents/healthCheck?api-version=2024-07-01-preview`; only HTTP
`200` passes. It doesn't test connectivity from the cluster nodes.

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
  response persists. If the same status continues after the client-side DNS,
  proxy, TLS, and identity checks pass, contact support with the sanitized
  request or correlation ID, UTC timestamp, Azure cloud, region, and status.

### Verify data-plane recovery

An unauthenticated browser or `curl` response doesn't reproduce this health
check. Verify the correction by retrying the original command, then run:

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{provisioningState:provisioningState,connectivityStatus:connectivityStatus}" --output yaml
```

Expect `provisioningState: Succeeded`. A newly connected cluster can briefly
report `Connecting`; it should progress to `Connected`.

The resource query verifies Azure state but doesn't repeat the data-plane
POST. The decisive verification is that the original command passes its
health-check step and advances to Helm metadata retrieval without
`AZK8S0300`.

### Data-plane support evidence

Provide the sanitized debug output, UTC timestamp, hostname, HTTP status or
transport error, cloud and region, DNS result, and whether a proxy performs TLS
inspection.

## Diagnose `AZK8S0301` through `AZK8S0305`

These codes classify output from a diagnostic workload running inside the
cluster. The workload resolves the built-in Kubernetes service name, and the
extension uses the latest recognized DNS failure or later valid address in the
captured output. This tests pod-to-cluster-DNS service discovery. It doesn't by
itself prove that every external Azure hostname resolves.

Use the same kubeconfig and context as the failing command:

```console
kubectl --kubeconfig "<path>" --context "<context>" get service kubernetes -n default -o custom-columns="NAME:.metadata.name,CLUSTER-IP:.spec.clusterIP"
kubectl --kubeconfig "<path>" --context "<context>" get pods -n kube-system -l k8s-app=kube-dns -o wide
kubectl --kubeconfig "<path>" --context "<context>" run arc-dns-check --rm -it --restart=Never --image=registry.k8s.io/e2e-test-images/dnsutils:1.3 --command -- nslookup kubernetes.default.svc.cluster.local
```

The first command confirms that the name being resolved still has a Kubernetes
Service and ClusterIP. The second shows common CoreDNS or kube-dns pods; some
distributions use another label, so no rows means the administrator must find
the cluster's DNS deployment rather than that DNS is necessarily absent. The
temporary pod makes the lookup use pod DNS policy and the same in-cluster path
as the diagnostic. It is removed when the command exits.

If the test pod can't be admitted or its image can't be pulled, use an existing
approved troubleshooting pod with `nslookup`, or ask the cluster administrator
to run the equivalent lookup. Don't change DNS merely because the test image
couldn't start. After repair, rerun the lookup and the original `connect` or
`az connectedk8s troubleshoot` operation. The DNS check is fixed when the
lookup returns one or more valid IPv4 or IPv6 addresses and the diagnostic
reports `Passed`.

## `AZK8S0301`: `DnsNxDomain`

`NXDOMAIN` is an authoritative statement that the queried name doesn't exist
from the resolver's point of view. For the diagnostic's
`kubernetes.default.svc.cluster.local` lookup, first confirm that
`service/kubernetes` exists. Then inspect the cluster DNS deployment,
Kubernetes DNS plug-in configuration, cluster-domain setting, and any rewrite
or forwarding rule that can incorrectly return `NXDOMAIN` for the cluster
domain. A public upstream resolver shouldn't be asked to resolve the internal
Kubernetes service name.

Run the [common in-cluster DNS procedure](#diagnose-azk8s0301-through-azk8s0305)
after correction. A later valid address in the diagnostic output clears the
earlier `NXDOMAIN` classification.

## `AZK8S0302`: `DnsTimeout`

A single generic timeout, such as `query timed out`, is treated as transient:
the diagnostic reports `NotApplicable`, warns, and continues onboarding.
`AZK8S0302` requires repeated generic timeouts or explicit timeout evidence.
An explicit timeout means no usable DNS response arrived before the client
deadline. It can result from an overloaded DNS deployment, packet loss, an
unreachable upstream, or UDP/TCP port 53 policy. Check DNS pod readiness and
recent events, then repeat the lookup several times:

```console
kubectl --kubeconfig "<path>" --context "<context>" get events -n kube-system --sort-by=.lastTimestamp
kubectl --kubeconfig "<path>" --context "<context>" get networkpolicy --all-namespaces
```

Use the events to identify DNS pod scheduling, restart, or resource-pressure
failures. Review NetworkPolicies rather than deleting them: pod DNS normally
requires egress to the configured resolver on both UDP and TCP port 53. Run
the [common in-cluster DNS procedure](#diagnose-azk8s0301-through-azk8s0305)
until repeated lookups return an address without timing out.

## `AZK8S0303`: `DnsServerFailure`

`SERVFAIL` means a DNS server received the query but couldn't complete it. For
the internal Kubernetes service name, inspect the DNS deployment logs and its
configuration for a broken Kubernetes plug-in, invalid zone or rewrite,
forwarding loop, unavailable upstream, or DNSSEC failure:

```console
kubectl --kubeconfig "<path>" --context "<context>" logs -n kube-system -l k8s-app=kube-dns --all-containers --tail=200
```

Logs can contain customer-specific names and addresses; inspect them locally
and replace those values before sharing. Correct the first current resolver
error, then run the
[common in-cluster DNS procedure](#diagnose-azk8s0301-through-azk8s0305).

## `AZK8S0304`: `DnsNoServersReachable`

This result means the pod couldn't contact any resolver in its DNS
configuration. Inspect that configuration from an approved temporary pod:

```console
kubectl --kubeconfig "<path>" --context "<context>" run arc-dns-config --rm -it --restart=Never --image=registry.k8s.io/e2e-test-images/dnsutils:1.3 --command -- cat /etc/resolv.conf
```

Verify locally that at least one nameserver address is the intended cluster DNS
service, then check that service's endpoints, kube-proxy or CNI routing, and
NetworkPolicies. Restore both UDP and TCP port 53 access from workloads to the
resolver. Resolver addresses and search domains can identify the customer
environment, so don't include unmodified output in a public issue. Run the
[common in-cluster DNS procedure](#diagnose-azk8s0301-through-azk8s0305) after
repair.

## `AZK8S0305`: `DnsCommunicationsError`

This code identifies a communications error while contacting the configured
resolver. Unlike `NXDOMAIN` or `SERVFAIL`, it doesn't represent a completed DNS
answer. Check DNS pod restarts, node-to-service routing, CNI health, packet
loss, and policy changes around the diagnostic timestamp. Repeat the
[common in-cluster DNS procedure](#diagnose-azk8s0301-through-azk8s0305)
several times; recovery requires reliable valid answers, not one result among
continuing communications errors.

## Diagnose `AZK8S0306` through `AZK8S0308`

The diagnostic workload records a three-digit response for each outbound
endpoint. `000` isn't an HTTP status: it means the client received no HTTP
response because DNS, routing, a firewall, proxy negotiation, TCP connection,
or TLS failed first. Any actual HTTP status proves basic transport reachability
far enough to receive a response, even though the related product operation
can still reject the request.

Use the exact hostname named in the diagnostic and compare it with the
[Azure Arc network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements).
For an existing resource, rerun:

```azurecli
az connectedk8s troubleshoot --resource-group "<resource-group>" --name "<cluster-name>"
```

When a manual in-cluster probe is approved, test only the hostname without
copying a credential-bearing URL from debug output:

```console
kubectl --kubeconfig "<path>" --context "<context>" run arc-egress-check --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -sS -o /dev/null -w "%{http_code}\n" --connect-timeout 10 "https://<hostname>/"
```

The root path can legitimately return `401`, `403`, or `404`; those statuses
still prove basic reachability. Failure to create or pull the temporary pod is
not proof that the named endpoint is blocked. Use an existing approved
diagnostic pod or the supported troubleshoot command instead.

## `AZK8S0306`: `OnboardingOutboundConnectivityFailed`

At least one mandatory onboarding endpoint returned `000`, so the extension
marks the pre-onboarding outbound check `Failed`. Use the endpoint list in the
detailed diagnostic to select the firewall, proxy, private-link, DNS, or TLS
path. Allow only the hostname, protocol, and port documented for the active
Azure cloud; don't broadly disable egress controls.

After correction, run the
[outbound diagnostic](#diagnose-azk8s0306-through-azk8s0308) and retry
`connect`. The issue is fixed when every mandatory endpoint produces an HTTP
response, no mandatory result is `000`, and the pre-onboarding check reports
`Passed`. A 4xx or 5xx can additionally produce `AZK8S0308`, but it doesn't
make this transport check fail.

## `AZK8S0307`: `ClusterConnectOutboundConnectivityFailed`

The optional Cluster Connect endpoint returned `000`. During pre-onboarding,
the extension records `AZK8S0307` and warns that Cluster Connect will be
affected, but the outbound check still passes when mandatory onboarding
endpoints are reachable. No action is required when the feature won't be used.

When Cluster Connect is required, allow its documented outbound HTTPS or
WebSocket route through the applicable firewall and proxy, then rerun the
[outbound diagnostic](#diagnose-azk8s0306-through-azk8s0308). Finally retry
`az connectedk8s proxy` and make a Kubernetes `/version` request through the
generated context. The issue is fixed when the endpoint returns an HTTP
response and proxy traffic succeeds.

## `AZK8S0308`: `OutboundEndpointNonSuccessResponse`

This is an informational classification for an HTTP 4xx or 5xx response. The
connectivity check treats it as reachable and continues because DNS, TCP, TLS,
and the server response path worked. Don't open firewall routes, weaken TLS,
or change credentials for `AZK8S0308` alone.

If the related operation also fails, use that operation's own response:

- `401`: refresh the credential used by that operation.
- `403`: verify the operation's Azure or Kubernetes authorization.
- `429`: honor retry guidance and back off.
- `5xx`: retry with backoff and check Azure service health if it persists.

There is no required network repair or retry for this diagnostic by itself.
An HTTP 2xx response clears the informational code, but a root-path probe can
legitimately remain 4xx while the authenticated product operation succeeds.

## `AZK8S0309`: `CertificatePulldownFailed`

This code is selected only after an Arc Helm install or upgrade times out.
The extension then performs read-only checks of `azure-arc` pods, warning
events, and Secret metadata. Missing `azure-identity-certificate`, a missing
`kube-aad-proxy-certificate` named by a `FailedMount` event, or related
clusteridentityoperator evidence selects `AZK8S0309`. Image-pull evidence is
classified as `AZK8S0513`, and scheduling evidence as `AZK8S0512`, before the
identity classification is considered.

### Diagnose identity certificate synchronization

Use the same kubeconfig and context as the timed-out command:

```console
kubectl --kubeconfig "<path>" --context "<context>" get pods -n azure-arc -o wide
kubectl --kubeconfig "<path>" --context "<context>" get pods -n azure-arc -o name
kubectl --kubeconfig "<path>" --context "<context>" get events -n azure-arc --field-selector type=Warning --sort-by=.lastTimestamp
kubectl --kubeconfig "<path>" --context "<context>" get secret azure-identity-certificate -n azure-arc -o name
```

The first two commands identify non-ready agents and the pod whose name starts
with `clusteridentityoperator`. The event list explains current mount,
container, DNS, or connectivity failures. The Secret command requests only
its name: `NotFound` confirms that identity-certificate synchronization hasn't
completed, while `secret/azure-identity-certificate` confirms presence without
displaying certificate data.

If a current warning specifically names `kube-aad-proxy-certificate`, test
only its existence:

```console
kubectl --kubeconfig "<path>" --context "<context>" get secret kube-aad-proxy-certificate -n azure-arc -o name
```

Read the responsible agent's recent logs locally when events aren't enough:

```console
kubectl --kubeconfig "<path>" --context "<context>" logs -n azure-arc "<clusteridentityoperator-pod>" --all-containers --tail=200
```

Correct the current pod, mount, DNS, proxy, TLS, or required-endpoint error
shown by those reads. Don't manually create either certificate Secret, copy
certificate data into Kubernetes, delete the Arc release, or delete the Azure
resource as a generic repair. Those actions can replace ownership state or
credentials without fixing the synchronization path.

Retry the original supported `connect` or `update` once after correcting the
identified cause. `AZK8S0309` is fixed when the required Secret metadata
exists, the responsible agents become ready, and Helm completes. If the pods
are ready but `azure-identity-certificate` remains absent after one retry,
collect sanitized events and logs and contact support without deleting the
resource or release.

## Related content

- [Azure Arc-enabled Kubernetes error-code reference](error-codes.md)
- [Azure Arc-enabled Kubernetes network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements)
- [Diagnose connection issues for Azure Arc-enabled Kubernetes clusters](https://learn.microsoft.com/azure/azure-arc/kubernetes/diagnose-connection-issues)
