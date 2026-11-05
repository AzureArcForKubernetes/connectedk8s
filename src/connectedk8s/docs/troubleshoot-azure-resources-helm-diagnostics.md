# Troubleshoot Azure resources, Helm, and diagnostics for Azure Arc-enabled Kubernetes

Use this guide for Azure Arc-enabled Kubernetes errors involving Azure
resources, Helm releases, Arc agents, and pre-onboarding diagnostics. Return
to the [error-code reference](error-codes.md) to look up every `AZK8Snnnn`
code.

## Collect diagnostic information

### Reproduce the error with debug logging

Rerun the failing `az connectedk8s` command with `--debug`. Use debug logging
only while reproducing the issue. Review the output and remove credentials,
tokens, certificates, private keys, and proxy details before sharing it.

### Run connected cluster diagnostics

For an existing Arc-enabled cluster, collect the resource state and run the
built-in diagnostics:

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --output yaml
az connectedk8s troubleshoot --resource-group "<resource-group>" --name "<cluster-name>"
```

### Inspect the Azure Arc agents

For agent installation or upgrade failures, inspect the `azure-arc` namespace:

```console
kubectl get pods -n azure-arc -o wide
kubectl get events -n azure-arc --sort-by=.lastTimestamp
kubectl describe pod -n azure-arc <pod-name>
kubectl logs -n azure-arc <pod-name> --all-containers
```

Use the commands in order:

- `get pods` provides the namespace-wide summary. In the `READY` column, the
  first number should equal the second, and `STATUS` should normally be
  `Running`. Note the name of each pod that is pending, restarting, or not
  ready.
- `get events` shows cluster-level reasons that can prevent those pods from
  starting, such as `FailedScheduling`, `FailedMount`, or image-pull errors.
  Because the output is sorted by time, the newest events are at the end.
- `describe pod` shows the selected pod's container states, conditions, node
  assignment, and related events. Use it for each pod identified by the first
  command to determine whether the failure is scheduling, mounting, image
  retrieval, or container startup.
- `logs` shows application output from the selected pod's containers. Use it
  when the pod starts but a container exits, restarts, or reports not ready;
  correct the first concrete error in the output.

Do not include kubeconfig contents, tokens, certificates, private keys, proxy
credentials, or Kubernetes Secrets in support requests.

## Decide whether to retry

Retry once when the detailed error indicates a transient timeout, HTTP `429`
or `5xx`, temporary API unavailability, or an unexpected proxy exit. Use
backoff for Azure service responses.

Correct the cause before retrying when the error identifies invalid input, an
unsupported location or operation, HTTP `401` or `403`, failed Kubernetes
authorization, a certificate error, an occupied port, or a disconnected
cluster. Repeating the same command and values won't correct these conditions.

Inspect current Azure, Helm, and Kubernetes state before retrying a failed
create, update, delete, upgrade, or feature operation. An earlier stage might
already have changed state:

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{id:id,provisioningState:provisioningState,agentState:arcAgentProfile.agentState}" --output yaml
```

```console
helm list --all-namespaces --deployed --failed --pending --uninstalling --uninstalled --superseded --filter "^azure-arc$"
kubectl get deployments,pods -n azure-arc -o wide
```

The Azure query shows whether the resource exists and whether its latest
operation succeeded. A `404` is expected only when a delete already completed.
The Helm row shows the release namespace and state; if a row appears, use that
namespace with `helm status azure-arc --namespace "<release-namespace>"`.
Deployments should have all desired replicas available, and pods should be
running and ready. If only one layer changed, or Azure, Helm, or Kubernetes
reports a failed or pending state, use the matching error procedure instead of
repeating the operation. Unless the specific procedure directs it, don't:

- Use force deletion to bypass identity or resource mismatches.
- Delete Helm releases, namespaces, ConfigMaps, or Secrets manually.
- Disable TLS verification as a permanent certificate workaround.
- Stop an unknown local process to free a proxy port.
- Display or share credential responses, kubeconfig, tokens, certificates, or
  private keys.

Escalate after the documented verification still fails, after the same
transient error repeats with backoff, or when the procedure identifies state
that only support can reconcile. Collect evidence before cleanup or another
retry.

## `AZK8S0104`: `InvalidLocation`

The requested location didn't match a location returned for
`Microsoft.Kubernetes/connectedClusters` in the active cloud and subscription.

In `connectedk8s` version 1.11.5, `connect` runs pre-onboarding diagnostics
before validating the location. Resolve any earlier precheck error first. A
diagnostic Cluster Connect failure can also contain the unsupported location
in its endpoint hostname; correct the location before changing network rules
for that endpoint.

### Diagnose the location

```azurecli
az account show --query "{subscription:id,cloud:environmentName}" --output yaml
az provider show --namespace Microsoft.Kubernetes --query "resourceTypes[?resourceType=='connectedClusters'].locations | [0][]" --output table
az account list-locations --query "[?displayName=='<supported-display-name>'].name | [0]" --output tsv
```

The account query identifies the subscription and Azure cloud used for the
location lookup; confirm that both are the intended targets. The provider
query should return at least one location for that cloud and subscription.
The final command converts a displayed name such as `East US` to the canonical
name `eastus`; empty output means the supplied display name didn't match.

### Resolve the location

Retry with a canonical name returned by the commands, for example
`--location eastus`. If the provider list is empty or unexpected, verify the
active cloud and subscription before changing regions. Don't select another
region without checking data-residency, Private Link, and architecture
requirements.

### Verify the location

The original command should advance beyond location validation without
`AZK8S0104`. Repeating the same rejected value isn't useful.

### Location support evidence

Provide the sanitized error text, requested and canonical locations, active
cloud, supported-location output, UTC timestamp, and `az version`. Replace
subscription and resource names with stable placeholders.

## `AZK8S0400`: `ConnectedClusterCreateFailed`

This error occurs while Azure Resource Manager creates the
`Microsoft.Kubernetes/connectedClusters` resource, before Arc agents finish
installing in the cluster. Version 1.11.5 uses an ARM create-or-replace request
and doesn't automatically retry a failed request. A recognized ARM `409` name
conflict is reported as `AZK8S0404`, not `AZK8S0400`.

### Diagnose resource creation

Check the selected scope, resource group, provider registration, and region:

```azurecli
az account show --query "{subscription:id,tenant:tenantId,user:user.name}" --output yaml
az group show --name "<resource-group>" --query "{name:name,location:location,state:properties.provisioningState}" --output yaml
az provider show --namespace Microsoft.Kubernetes --query registrationState --output tsv
az provider show --namespace Microsoft.Kubernetes --query "resourceTypes[?resourceType=='connectedClusters'].locations | [0][]" --output table
```

The account output must identify the intended subscription, tenant, and user.
The resource-group query must return the requested group with `state:
Succeeded`; a `404` means that the group isn't present in that subscription.
The provider state must be `Registered`, and the requested location must
appear in the location list. If the provider isn't registered, run:

```azurecli
az provider register --namespace Microsoft.Kubernetes
az provider show --namespace Microsoft.Kubernetes --query registrationState --output tsv
```

Wait for `Registered` before retrying.

### Resolve resource creation

Interpret the detailed ARM response as follows:

- HTTP `401` or `403`: select the intended tenant and subscription and grant
  the identity the **Kubernetes Cluster - Azure Arc Onboarding** role at the
  required scope, or equivalent least-privilege permissions.
- `MissingSubscriptionRegistration`: register the provider named in the error
  and wait for registration to finish.
- Resource group `404`: correct the resource-group name or create it in the
  selected subscription.
- Unsupported location: choose a value from the location query output.
- Policy denial: review the policy assignment named in the response and obtain
  an appropriate exemption or use compliant settings.
- HTTP `429`, `5xx`, or a timeout: retry with backoff and check Azure service
  health if the failure continues.

Don't delete an existing connected cluster based only on a name-conflict
message. Compare the Azure resource ID with the registration names stored in
the cluster without displaying other ConfigMap data:

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query id --output tsv
```

```console
kubectl get configmap azure-clusterconfig -n azure-arc -o jsonpath="{.data.AZURE_RESOURCE_GROUP}{'\n'}{.data.AZURE_RESOURCE_NAME}{'\n'}"
```

The resource ID contains its subscription, resource group, and name. If the
ConfigMap names match, treat the Azure resource as belonging to this cluster.
If they differ or the registration state is incomplete, contact support before
deleting either side.

### Verify the connected cluster resource

After correction, retry the original command, and then run:

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{id:id,provisioningState:provisioningState}" --output yaml
```

Expect a nonempty resource ID and `provisioningState: Succeeded`.

### Resource creation support evidence

Provide the sanitized ARM error code and message, HTTP status, correlation ID,
UTC timestamp, provider state, requested region, applicable policy assignment,
and the scope of the identity's Azure role.

## `AZK8S0401`: `ConnectedClusterUpdateFailed`

This code wraps Azure Resource Manager failures while `update` gets, patches,
or replaces the connected cluster resource. The detailed ARM status determines
whether the cause is authorization, policy, concurrency, throttling, or service
availability. A recognized connected-cluster `404` becomes `AZK8S0405`.

### Diagnose resource update

Read the current resource and applicable locks without changing it:

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{id:id,state:provisioningState,tags:tags,distribution:distribution,version:distributionVersion}" --output yaml
az lock list --resource-group "<resource-group>" --resource-type Microsoft.Kubernetes/connectedClusters --resource-name "<cluster-name>" --output table
```

The first command proves that the resource exists in the active subscription
and shows whether an earlier update is still pending or failed. The second
lists locks at the resource scope; a `ReadOnly` lock can reject updates. Empty
lock output doesn't rule out RBAC, policy, or an inherited lock, so use the
detailed ARM error and scope to identify the controlling condition.

Correct `401` or `403` authentication and RBAC, an applicable lock, the policy
assignment named by a denial, or an ETag/concurrent-operation conflict before
retrying. For `408`, `429`, or `5xx`, wait according to any `Retry-After`
guidance and retry once with backoff. Don't repeatedly submit updates while
`provisioningState` is still changing.

Retry the same `az connectedk8s update` arguments. Then query the exact
property that was changed in addition to `provisioningState`; command success
alone doesn't prove that the intended value was retained. The error is fixed
when the update succeeds, state is `Succeeded`, and the requested property has
the expected value.

## `AZK8S0402`: `ConnectedClusterDeleteFailed`

This code wraps an ARM get or delete failure in the supported delete workflow.
The workflow can also remove Arc agents, so inspect both Azure and cluster
state before retrying. A recognized connected-cluster `404` is reported as
`AZK8S0405`.

### Diagnose resource deletion

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{id:id,state:provisioningState}" --output yaml
az lock list --resource-group "<resource-group>" --resource-type Microsoft.Kubernetes/connectedClusters --resource-name "<cluster-name>" --output table
```

```console
helm list --all-namespaces --filter "^azure-arc$"
kubectl get namespace azure-arc -o name
```

The Azure query distinguishes a failed delete from one whose ARM side already
completed. `CanNotDelete` and `ReadOnly` locks can block deletion. The Helm and
namespace reads show whether cluster-side Arc state remains; they don't remove
it. Correct the exact permission, policy, lock, or dependency named by ARM.
Only the owner of an applicable lock should remove it under the organization's
change process.

Retry the supported `az connectedk8s delete` once after correction. Don't use
force deletion to bypass an identity mismatch, and don't manually delete the
Helm release, namespace, ConfigMaps, or Secrets. Force deletion changes ARM
semantics and can leave cluster state behind; use it only when the product's
documented recovery path or Azure support explicitly requires it.

Deletion is complete when `az connectedk8s show` returns resource not found and
the supported workflow has removed the Arc release and namespace as expected.
If the Azure resource is absent but Arc state remains, stop retrying and contact
support with the sanitized state instead of recreating the resource merely to
delete it.

## `AZK8S0403`: `ClusterAlreadyOnboarded`

During `connect`, version 1.11.5 found an existing Arc Helm release, read
`azure-clusterconfig`, and confirmed that its saved Azure resource still
exists. The saved resource group or resource name differs from the values in
the new command. This guard prevents one Kubernetes cluster from silently
changing Azure ownership.

Read only the selected context and registration identity:

```console
kubectl --kubeconfig "<path>" config current-context
kubectl --kubeconfig "<path>" --context "<context>" get configmap azure-clusterconfig -n azure-arc -o jsonpath="{.data.AZURE_SUBSCRIPTION_ID}{'\n'}{.data.AZURE_RESOURCE_GROUP}{'\n'}{.data.AZURE_RESOURCE_NAME}{'\n'}"
```

Use those values through a secure channel to locate the existing resource:

```azurecli
az account set --subscription "<saved-subscription-id>"
az connectedk8s show --resource-group "<saved-resource-group>" --name "<saved-resource-name>" --query "{id:id,state:provisioningState}" --output yaml
```

The ConfigMap query deliberately reads only registration fields, not arbitrary
data. If this is the intended cluster, rerun `connect` with its existing
resource group and name. If the command intended another Kubernetes cluster,
switch to that cluster's kubeconfig and context. If ownership is disputed or
the saved resource can't be verified, contact support before offboarding or
deleting either side. The guard is fixed when the selected cluster and the
requested Azure registration agree case-insensitively.

## `AZK8S0404`: `ConnectedClusterResourceAlreadyExists`

The requested name already identifies a connected cluster resource. Version
1.11.5 can detect this before creation when no local Arc release exists, or map
a recognized ARM `409` from create-or-replace to this code. A matching name
doesn't establish that the resource belongs to the selected Kubernetes
cluster.

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{id:id,state:provisioningState}" --output yaml
```

When the selected cluster already has Arc state, compare only its saved
registration identity:

```console
kubectl --kubeconfig "<path>" --context "<context>" get configmap azure-clusterconfig -n azure-arc -o jsonpath="{.data.AZURE_SUBSCRIPTION_ID}{'\n'}{.data.AZURE_RESOURCE_GROUP}{'\n'}{.data.AZURE_RESOURCE_NAME}{'\n'}"
```

If the identities match, use the existing resource rather than creating a
duplicate. If the Azure resource belongs to another cluster, choose a distinct
approved resource name for the new cluster. If ownership is unclear, stop and
contact support. Don't delete the existing resource based only on the conflict.
The issue is fixed when `connect` uses an unambiguous resource identity and
advances beyond the existing-resource check.

## `AZK8S0405`: `ConnectedClusterResourceNotFound`

Version 1.11.5 reports this code when `show` receives HTTP `404`, or when an
update or delete receives a recognized connected-cluster not-found response.
The common causes are the wrong subscription, misspelled resource group or
name, a completed deletion, or an Azure resource missing while Arc state still
exists in Kubernetes.

```azurecli
az account show --query "{subscription:id,tenant:tenantId}" --output yaml
az connectedk8s list --resource-group "<resource-group>" --query "[].{name:name,id:id,state:provisioningState}" --output table
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query id --output tsv
```

The account query verifies the active scope. The list distinguishes an absent
resource from a spelling mismatch without creating anything. For `show` or
update, select the correct subscription and exact names, then retry; the code
is fixed when the command resolves the intended full resource ID.

For delete, a `404` can mean the Azure side is already gone. Check for remaining
Arc state with `helm list --all-namespaces --filter "^azure-arc$"` and read the
three registration fields from `azure-clusterconfig` as shown in the
[`AZK8S0403` procedure](#azk8s0403-clusteralreadyonboarded). Don't recreate an
Azure resource merely to satisfy delete, and don't manually remove agents.
Contact support when cluster-side state remains without a verifiable Azure
owner.

## `AZK8S0406`: `InvalidDeleteRequest`

Before deletion, the extension compares the active Azure subscription and the
requested resource group and name with all three values in the selected
cluster's `azure-clusterconfig`. Any mismatch stops the command before ARM or
Arc agents are deleted.

```azurecli
az account show --query id --output tsv
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query id --output tsv
```

```console
kubectl --kubeconfig "<path>" config current-context
kubectl --kubeconfig "<path>" --context "<context>" get configmap azure-clusterconfig -n azure-arc -o jsonpath="{.data.AZURE_SUBSCRIPTION_ID}{'\n'}{.data.AZURE_RESOURCE_GROUP}{'\n'}{.data.AZURE_RESOURCE_NAME}{'\n'}"
```

Compare subscription, resource group, and resource name case-insensitively.
Select the matching Azure subscription, correct the command names, or switch
to the kubeconfig and context for the intended cluster. Never use force delete
to bypass this ownership guard. The issue is fixed when all three identities
match and the supported delete advances past validation.

## `AZK8S0407`: `ResourceProviderFetchFailed`

The standardized definition is reserved for migration in version 1.11.5; no
active call site emits `AZK8S0407`. A provider fetch can instead appear as an
unnumbered Azure request error during location validation, while the initial
provider-registration check logs some fetch failures and continues. Use these
steps for either current behavior or a later version that emits the code.

```azurecli
az account show --query "{subscription:id,tenant:tenantId,cloud:environmentName}" --output yaml
az provider show --namespace Microsoft.Kubernetes --query "{namespace:namespace,state:registrationState}" --output yaml
```

The first command verifies the ARM cloud and account context. The second makes
the same class of provider metadata request without changing registration. An
authentication, authorization, DNS, proxy, timeout, or service response
identifies the repair path. Retry only after correcting that condition, or
with backoff for a transient `429` or `5xx`. The problem is fixed when the
provider query succeeds in the intended subscription and the original command
advances.

## `AZK8S0408`: `ConnectedClusterProviderNotRegistered`

Before onboarding, the extension queries `Microsoft.Kubernetes`. States
`Registering` and `Registered` pass the code check, but waiting for
`Registered` avoids a race with later resource creation.

```azurecli
az account show --query "{subscription:id,tenant:tenantId}" --output yaml
az provider show --namespace Microsoft.Kubernetes --query "{namespace:namespace,state:registrationState}" --output yaml
```

If the intended subscription reports `NotRegistered` or `Unregistered`, an
identity with provider-registration permission can run:

```azurecli
az provider register --namespace Microsoft.Kubernetes
az provider show --namespace Microsoft.Kubernetes --query registrationState --output tsv
```

Registration is subscription-wide, can take several minutes, and shouldn't be
repeated while state is `Registering`. Retry `connect` after the query returns
`Registered`. Workload identity and gateway options have additional provider
requirements that can produce separate unnumbered validation errors; satisfy
the provider named in that error as well.

## `AZK8S0409`: `ConnectedClusterResourceIdMissing`

During `update`, the extension successfully retrieved a connected cluster
object but its `id` property was `None`. It needs the ARM ID to extract the
subscription before subsequent agent work. This is different from a `404`,
which is `AZK8S0405`.

```azurecli
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{id:id,state:provisioningState}" --output yaml
az resource show --resource-group "<resource-group>" --name "<cluster-name>" --resource-type Microsoft.Kubernetes/connectedClusters --query "{id:id,state:properties.provisioningState}" --output yaml
```

Both commands are read-only views of the same ARM identity through different
clients. A complete ID starts with `/subscriptions/` and includes the intended
resource group, provider type, and resource name. If both return the complete
ID, retry the same update once because the earlier response may have been
transient. If either still returns an empty ID, or the retry receives another
object without an ID, collect sanitized debug output and the correlation ID
and contact Azure support. Don't delete or recreate the resource as a generic
repair. The issue is fixed when both `show` and the same update receive the
complete intended resource ID.

## `AZK8S0500`: `HelmReleaseInstallFailed`

This error covers a non-timeout Helm install or upgrade failure. It can occur
during `connect`, agent upgrade, or feature enablement. Confirm that kubectl is
using the intended cluster, then inspect the Arc workloads.

### Diagnose the Helm release

```console
kubectl config current-context
kubectl cluster-info
kubectl auth can-i create namespaces
kubectl auth can-i create clusterrolebindings
kubectl get deployments,pods -n azure-arc -o wide
kubectl get events -n azure-arc --sort-by=.lastTimestamp
```

If a pod isn't ready, inspect the pod named in the output:

```console
kubectl describe pod -n azure-arc <pod-name>
kubectl logs -n azure-arc <pod-name> --all-containers
```

If Helm is installed locally, inspect the release without changing it:

```console
helm list --all-namespaces --filter '^azure-arc$'
helm status azure-arc --namespace <release-namespace>
```

For a healthy release, Helm reports `STATUS: deployed`, deployments show all
replicas available, and pods become `Running` and ready.

### Resolve the Helm release

- `forbidden`: use a kubeconfig identity with the cluster permissions required
  for onboarding.
- `ErrImagePull` or `ImagePullBackOff`: allow the Microsoft Container Registry
  hostname shown by `kubectl describe pod` through the applicable firewall,
  proxy, or network policy, using the endpoints and ports in the network
  requirements. If the event instead reports authentication or node disk
  pressure, correct that named condition.
- `Pending`: resolve insufficient capacity, Linux-node availability, taints,
  selectors, quotas, or admission-policy restrictions shown in pod events.
- `CrashLoopBackOff`: run `kubectl logs -n azure-arc "<pod-name>"
  --all-containers --previous` to read the containers' previous failed run.
  Use the earliest dependency, authentication, or configuration error that
  precedes the shutdown; later termination messages are usually consequences.
- Admission webhook or policy rejection: the event identifies the rejecting
  webhook or policy and its reason. Ask the cluster-policy administrator to
  create an approved exception or make the named policy compatible with the
  supported Arc resources; don't disable admission controls globally.
- `x509` error: provide the complete trusted proxy certificate chain with
  `--proxy-cert`.
- `Kubernetes cluster unreachable`: restore kubeconfig credentials, VPN or
  private-network access, API server DNS, and firewall connectivity by
  following the [`AZK8S0202` procedure](troubleshoot-cluster-access-networking.md#azk8s0202-kubernetesconnectivityfailed).

Retry the same public operation that failed. Don't manually remove Helm or Arc
resources before collecting diagnostics.

### Verify the Arc agents

```azurecli
az connectedk8s troubleshoot --resource-group "<resource-group>" --name "<cluster-name>"
az connectedk8s show --resource-group "<resource-group>" --name "<cluster-name>" --query "{provisioningState:provisioningState,connectivityStatus:connectivityStatus}" --output yaml
```

Mandatory troubleshoot checks should pass, `provisioningState` should be
`Succeeded`, and `connectivityStatus` should be `Connected`. If troubleshoot
still names a failed endpoint or agent, resolve that result before retrying
Helm.

### Helm support evidence

Provide sanitized Helm stderr, the failed operation, pod and deployment status,
relevant events and logs, Kubernetes version and distribution, node
architecture, and troubleshoot output. Never include kubeconfig, Secrets,
tokens, certificates, or private keys.

## `AZK8S0501`: `HelmReleaseDeleteFailed`

Version 1.11.5 emits this code when `helm delete azure-arc` returns nonzero.
Helm deletion is cluster-side work: it uses the release record to remove
managed resources and can run chart deletion hooks. The error therefore does
not prove that every resource remains, or that none were removed.

```console
helm version --short
# Helm 3:
helm list --all-namespaces --all --filter '^azure-arc$'
# Helm 4:
helm list --all-namespaces --filter '^azure-arc$'
helm status azure-arc --namespace "<release-namespace>"
kubectl get events -n azure-arc --sort-by=.lastTimestamp
```

Choose the list form for the reported major version. Helm 3 needs `--all` to
include failed, pending, and uninstalling releases; Helm 4 returns every state
by default and rejects that flag. A successful empty result means Helm no
longer has a release row; an API error means release state is still unknown.
If a row remains, `status` shows its namespace, state, hooks, and managed
resources. Recent events can identify a denied deletion, failed hook,
unavailable API, or resource that didn't terminate. They don't authorize
removing finalizers.

Restore the kubeconfig access or RBAC named by `forbidden` or `cluster
unreachable`. For a hook timeout, correct the hook's concrete event or log
failure. Retry the original `az connectedk8s delete` once. Don't run `helm
delete`, delete the namespace, or clear finalizers manually; those actions can
bypass the CLI's Azure and cluster ownership checks. The code is fixed when
the supported delete succeeds and the first command returns no Arc release.

## `AZK8S0502`: `HelmChartPullFailed`

The extension invokes Helm to pull an OCI artifact, untar it below
`$HOME/.azure`, and retries five times with a three-second delay. This code
means every attempt returned nonzero. It is a client-to-registry failure, not
an image pull by a Kubernetes node; node-side image failures use `AZK8S0513`.

Use the registry hostname, chart version, and sanitized Helm stderr from the
error. Then test the same layers independently:

```console
nslookup "<registry-hostname>"
helm version --short
```

```powershell
Get-PSDrive -PSProvider FileSystem
```

```bash
df -h "$HOME/.azure"
```

`nslookup` proves only local name resolution; it does not prove HTTPS, proxy,
TLS, or registry authorization. `helm version` proves the selected shell can
start Helm. The filesystem command checks space because `--untar` writes the
chart locally. Use the actual Helm message to distinguish a connection or
proxy timeout, an untrusted certificate chain, denied registry access, a
missing chart version, and a full filesystem. Correct that layer and retry the
original operation. The built-in retry handles brief registry interruptions;
repeated identical failures need correction rather than more retries.

## `AZK8S0503`: `HelmChartExportFailed`

This code occurs after the chart-pull helper returns successfully but the
expected chart directory isn't present. The default expected path is
`$HOME/.azure/AzureArcCharts/azure-arc-k8sagents`. If `HELMCHART` is set, its
value replaces that final expected path. This distinction matters: a valid
pull can still be followed by a bad override or unexpected archive layout.

```powershell
$env:HELMCHART
Test-Path -LiteralPath "$HOME/.azure/AzureArcCharts/azure-arc-k8sagents" -PathType Container
Get-PSDrive -PSProvider FileSystem
```

```bash
printf '%s\n' "${HELMCHART:-<not-set>}"
test -d "$HOME/.azure/AzureArcCharts/azure-arc-k8sagents"; echo $?
df -h "$HOME/.azure"
```

The environment check reveals whether the extension is validating an
override instead of its managed directory. `Test-Path` returning `True`, or
the shell test returning `0`, proves only that the expected directory exists;
it doesn't prove its chart contents are valid. Remove an accidental
`HELMCHART` override from the invoking environment, or correct the explicitly
required path. Correct local security controls or storage only when they
blocked chart extraction. Retry once; the error is fixed when the expected
directory exists and the workflow advances to Helm install or upgrade.

## `AZK8S0504`: `HelmRepositoryAddFailed`

The normal 1.11.5 path pulls an OCI chart. This code is active only when both
`HELMREPONAME` and `HELMREPOURL` are set, causing the extension to run `helm
repo add` before chart retrieval. These environment variables select an
explicit repository override and should not be inferred from the Arc release.

```powershell
Get-Item Env:HELMREPONAME,Env:HELMREPOURL -ErrorAction SilentlyContinue
```

```bash
printf 'HELMREPONAME=%s\nHELMREPOURL=%s\n' "${HELMREPONAME:-}" "${HELMREPOURL:-}"
```

Do not include credentials from the URL in shared logs. If the override is
intentional, run `helm repo add "<repository-name>" "<sanitized-url>"` in a
controlled shell to reproduce its DNS, proxy, CA, authentication, or local
repository-file error. That command changes the user's local Helm repository
configuration; remove only the temporary test entry afterward. If the
variables were accidental, unset them in the environment that launches Azure
CLI so the managed OCI path is used. The issue is fixed when the intentional
repository add succeeds or the unintended override is absent and the original
operation advances.

## `AZK8S0505`: `HelmReleaseListFailed`

Before lifecycle operations, the extension runs a cross-namespace Helm list
and parses its JSON to locate the `azure-arc` release. Helm 3 includes `--all`
so non-deployed states are visible; Helm 4 no longer needs that flag. A
nonzero command result becomes `AZK8S0505`. Valid JSON with no matching release
is a different outcome and can later become `AZK8S0508`.

```console
kubectl config current-context
kubectl cluster-info
helm version --short
# Helm 3:
helm list --all-namespaces --all --output json
# Helm 4:
helm list --all-namespaces --output json
kubectl auth can-i list secrets --all-namespaces
```

The context identifies the cluster being queried. `cluster-info` separates
basic API reachability from Helm's release read. Choose the JSON list form for
the reported major version; Helm 3 needs `--all`, while Helm 4 includes every
state by default. The command should exit `0` with a JSON array, even when the
array is empty. Helm's default storage driver keeps release records in
Kubernetes Secrets, so the authorization check explains a common `forbidden`
response; a nondefault driver can require different access. Restore the exact
context, credentials, network route, or permission named by Helm. The code is
fixed when the same list command returns valid JSON.

## `AZK8S0506`: `AgentStateTimeout`

The extension polls the connected-cluster Azure resource every five seconds
for up to 15 minutes. In version 1.11.5, a missing state, `Succeeded`, and
`Failed` are all terminal; only a persistent nonempty state outside that set
can time out. Create emits the error immediately after its poll. Update records
the timeout, continues the Helm update to avoid leaving it half-finished, and
then emits `AZK8S0506`.

```azurecli
az connectedk8s show -g "<resource-group>" -n "<cluster-name>" --query "{agentState:arcAgentProfile.agentState,provisioningState:provisioningState,connectivityStatus:connectivityStatus}" -o yaml
```

```console
kubectl get deployments,pods -n azure-arc -o wide
kubectl get events -n azure-arc --sort-by=.lastTimestamp
```

The Azure query reads the control-plane view being polled; it can lag the
cluster and does not diagnose the cause. Deployment and pod readiness show
whether the agents are running, while recent warnings identify scheduling,
image, mount, DNS, or connection failures. Correct the newest concrete failure
for an affected workload and retry once. The timeout is fixed when the retry
observes a terminal state and completes without `AZK8S0506`; a terminal
`Failed` state still requires investigation, while `Succeeded` is the healthy
result.

## `AZK8S0507`: `KeyPairGenerationFailed`

During connect, the extension asks its Python cryptography library to generate
an RSA-4096 key in memory. The failure occurs before private-key injection into
Kubernetes. Temporary-directory writability and disk space don't test this
operation, and no supported public Azure CLI command exposes the same key
generator as a standalone diagnostic.

```azurecli
az version
az extension show --name connectedk8s --query "{name:name,version:version}" -o yaml
```

These commands identify the Azure CLI runtime and extension package whose
cryptographic call failed. Retry once to distinguish a transient operating-
system random-source or resource failure. If it repeats, update Azure CLI and
the extension through the organization's approved process, restart the shell,
and retry. Do not generate a replacement key manually or create the Arc Secret
yourself; the onboarding workflow owns both. The issue is fixed when connect
advances beyond key generation. For a repeat on current packages, provide the
sanitized exception and versions to support.

## `AZK8S0508`: `ReleaseNamespaceNotFound`

Update, upgrade, and feature paths first ask Helm where the `azure-arc` release
is stored. This code means no namespace was returned. That can mean the release
is absent, the wrong cluster context was selected, or Helm returned malformed
JSON that version 1.11.5 treated like no result. It does not merely mean that
the workload namespace `azure-arc` is absent; the Helm release metadata can be
stored in a different namespace such as `azure-arc-release`.

```console
kubectl config current-context
helm version --short
# Helm 3:
helm list --all-namespaces --all --output json
helm list --all-namespaces --all --filter '^azure-arc$'
# Helm 4:
helm list --all-namespaces --output json
helm list --all-namespaces --filter '^azure-arc$'
```

Choose the pair for the reported major version. The unfiltered JSON proves
that Helm returned parseable release metadata. The filtered view then proves
whether exactly one Arc release exists and gives its namespace. If it does,
verify only that namespace's existence with `kubectl get namespace
"<release-namespace>" -o name`. If no release exists but an Azure
connected-cluster resource or Arc workloads remain, stop and contact support;
don't reconstruct release records, rerun connect over uncertain ownership, or
delete remnants manually. The issue is fixed when the intended release and
namespace are consistently discoverable or support completes a supported
reconciliation.

## `AZK8S0509`: `HelmValuesGetFailed`

Lifecycle and feature operations read current Helm values so an update can
preserve user settings and evaluate feature state. Some paths request user
values; others add `--all` for computed values. These values can contain proxy
details or other sensitive configuration, so test the exit code without
printing or sharing the content.

```powershell
helm get values azure-arc -n "<release-namespace>" | Out-Null
$LASTEXITCODE
helm get values --all azure-arc -n "<release-namespace>" | Out-Null
$LASTEXITCODE
```

```bash
helm get values azure-arc -n "<release-namespace>" >/dev/null
echo $?
helm get values --all azure-arc -n "<release-namespace>" >/dev/null
echo $?
```

Exit code `0` proves Helm could read and decode the release values. A
`forbidden` response selects Kubernetes release-storage RBAC; `release: not
found` selects context or namespace correction; `cluster unreachable` selects
kubeconfig and API connectivity. Correct that named layer and retry the same
public operation. The code is fixed when both the required values form and the
original operation succeed.

## `AZK8S0510`: `HelmNotInstalled`

Version 1.11.5 emits this code in AGC clouds (`ussec` or `usnat`), where it
skips managed Helm download and requires `helm` on `PATH`. Public-cloud paths
normally use the extension-managed binary, so a managed download failure has a
different, older error rather than `AZK8S0510`.

```powershell
Get-Command helm -ErrorAction SilentlyContinue
helm version --short
```

```bash
command -v helm
helm version --short
```

The lookup must return an executable path, and the version command must run in
the same account and process environment used for Azure CLI. Installing Helm
in another user's profile or changing PATH only in a different terminal does
not satisfy the extension. Install an approved Helm version 3 or later and
restart the invoking shell if PATH changed. The error is fixed when lookup and
version both succeed there.

## `AZK8S0511`: `HelmVersionTooOld`

The extension runs `<selected-helm> version --short`, extracts the major
number, and rejects values below 3. It does not enforce Helm 3.8 specifically.
If the command returns nonzero or an unparseable version, validation defers to
the requested Helm operation so that operation can report the authoritative
failure.

```console
helm version --short
```

Expected output starts with `v3.` or a later major version. When several Helm
binaries are installed, compare the path from `Get-Command helm` on Windows or
`command -v helm` on Linux and macOS with the path in debug output. Upgrade or
replace the selected client through the approved package source. The error is
fixed when that exact executable reports major version 3 or later.

## Helm timeout classification

`AZK8S0512` through `AZK8S0514` are emitted only after Helm stderr contains a
recognized timeout such as `context deadline exceeded`. The extension then
performs read-only list operations for Arc pods, events, and Secret metadata.
It does not read Secret data. Evidence is resolved in this order:

1. Image-pull evidence becomes `AZK8S0513`.
2. Pending or scheduling evidence becomes `AZK8S0512`.
3. Identity-certificate evidence becomes `AZK8S0309`.
4. Everything else becomes `AZK8S0514`.

This order means the reported code identifies the highest-priority evidence,
not necessarily the only problem present.

## `AZK8S0512`: `HelmTimeoutPendingOrUnschedulable`

The timeout diagnostics found a pending pod, `FailedScheduling`,
`NotTriggerScaleUp`, insufficient resources, a blocking taint, or a selector
or affinity constraint.

```console
kubectl get pods -n azure-arc --field-selector=status.phase=Pending -o wide
kubectl describe pod -n azure-arc "<pending-pod>"
kubectl get nodes -o wide
kubectl describe node "<candidate-node>"
```

The pod list identifies what the scheduler hasn't placed. `describe pod`
shows requested resources, selectors, tolerations, and the scheduler's latest
event. Node output supplies the other side of that decision: allocatable
capacity, labels, taints, and pressure. Correct the exact scheduler reason by
adding approved capacity, restoring a suitable Linux node, or reconciling the
named policy or constraint. Don't remove taints or change Arc manifests merely
to force placement. The issue is fixed when affected pods are scheduled and
ready and the original Helm operation completes.

## `AZK8S0513`: `HelmTimeoutImagePullFailed`

This code means timeout diagnostics found `ErrImagePull`, `ImagePullBackOff`,
or an image-related warning. The pull occurs from the Kubernetes node, so a
successful `helm pull` on the Azure CLI host does not disprove it.

```console
kubectl get pods -n azure-arc -o wide
kubectl describe pod -n azure-arc "<affected-pod>"
kubectl get events -n azure-arc --sort-by=.lastTimestamp
```

`describe` provides the exact image reference and kubelet message. A network
timeout or connection refusal selects node egress, proxy, firewall, or network
policy. `x509` selects the node or proxy trust chain. `unauthorized` or
`denied` selects registry or proxy authentication. `no space left on device`
selects node image-storage cleanup or expansion under cluster procedures.
Allow only the documented registry endpoints instead of disabling TLS or
opening unrestricted egress. The issue is fixed when pulls succeed, pods are
ready, and the Helm operation completes.

## `AZK8S0514`: `HelmTimeout`

This is the fallback after a recognized Helm timeout. It includes cases where
pods are running but not ready, restarting, blocked during container creation,
or where read-only post-timeout diagnostics couldn't collect enough evidence.
It should not be treated as proof of a network problem.

```console
kubectl get deployments,pods -n azure-arc -o wide
kubectl get events -n azure-arc --sort-by=.lastTimestamp
kubectl describe pod -n azure-arc "<non-ready-pod>"
kubectl logs -n azure-arc "<non-ready-pod>" --all-containers
kubectl logs -n azure-arc "<restarting-pod>" --all-containers --previous
```

Deployment readiness shows whether rollout is incomplete. Events explain
cluster-level startup failures. Current logs diagnose a running but unhealthy
process; `--previous` reads the last terminated container and is useful for
`CrashLoopBackOff`. If the error says diagnostics themselves failed, first
restore read access to pods, events, and Secret metadata, then repeat the
inspection. Correct the earliest concrete dependency or configuration error,
not later shutdown messages. The issue is fixed when required workloads are
ready and Helm finishes within its timeout.

## `AZK8S0515`: `HelmClientError`

This code is narrower than a generic Helm failure. During client validation,
the operating system raised an error while starting the exact Helm path, such
as file not found, permission denied, or an inaccessible filesystem. If Helm
starts and returns a nonzero exit code, validation deliberately lets the
requested operation produce a more specific error.

```powershell
Test-Path -LiteralPath "<helm-path>" -PathType Leaf
& "<helm-path>" version --short
$LASTEXITCODE
```

```bash
test -x "<helm-path>"; echo $?
"<helm-path>" version --short
echo $?
```

Use the path from the detailed error or debug output; a different system Helm
doesn't test the failing executable. The existence or execute check isolates a
missing path or permission problem. The version invocation then exposes an OS
loader, architecture, filesystem, or endpoint-security failure. Restore the
extension-managed binary through an extension update rather than substituting
an arbitrary file at that path. The code is fixed when that exact executable
starts and reports major version 3 or later.

## Pre-onboarding diagnostic lifecycle

Before installing the Arc agents, `az connectedk8s connect` temporarily
installs the `cluster-diagnostic-checks` Helm release in
`azure-arc-release`. Its Kubernetes Job checks cluster DNS, required outbound
endpoints, Microsoft Entra connectivity, and ownership of Arc CRDs. The
extension watches the Job for up to 180 seconds, reads its pod log, writes a
local diagnostic copy when possible, and then requests deletion of the
temporary release.

This cleanup is expected. After the command returns, `helm list`, `kubectl get
job`, or `kubectl get pod` might show no diagnostic resources even when they
existed during the run. `NotFound` after the operation therefore doesn't prove
that installation or scheduling failed. Start with the check summary and
saved diagnostic path printed by the failing command. If another attempt is
appropriate, observe the temporary resources from a second terminal while
the original command runs with `--debug`:

```console
kubectl get jobs,pods -n azure-arc-release --watch
```

`--watch` streams object changes instead of taking a single snapshot. Stop it
after the onboarding command returns. It doesn't change cluster state. Keep
the complete error code, check summary, Job or pod reason, and UTC timestamp,
but sanitize proxy credentials, tokens, certificates, and kubeconfig data.
Don't manually delete the temporary release or its resources; the extension
owns their lifecycle and attempts cleanup on success and failure paths.

## `AZK8S0600`: `PrediagnosticsFailed`

This code wraps an unexpected exception in the outer diagnostic orchestration.
It is not the aggregate code for a check that returned `Failed`; that condition
is `AZK8S0602`. Known Helm-install errors are also preserved as `AZK8S0607`.
The detailed text after `Details:` is therefore the most important evidence.

Rerun the same onboarding command once with `--debug` only if the detailed
error doesn't identify a persistent input, access, or policy problem. In a
second terminal, collect read-only state while the command is still running:

```console
kubectl auth can-i create jobs.batch -n azure-arc-release
kubectl get events -n azure-arc-release --sort-by=.lastTimestamp
kubectl get jobs,pods -n azure-arc-release -o wide
```

The authorization check asks the API server whether the current kubeconfig
identity can create Jobs; it doesn't create one. `no` selects Kubernetes RBAC
or an external authorization policy. Events expose admission, quota, image,
and scheduling decisions. The object snapshot shows whether orchestration
progressed far enough to create the Job and pod. It doesn't diagnose a local
Python, filesystem, or process error, which should instead appear in the
debug details. Correct that first concrete error. The issue is fixed when the
same command completes diagnostics and reports either passed checks or a more
specific check failure.

## `AZK8S0601`: `PrediagnosticsJobExecutionFailed`

This code means an unexpected exception escaped the lower-level workflow that
loads kubeconfig, reconciles a stale diagnostic release, pulls the chart,
installs it, watches the Job, reads its pod, and requests cleanup. A recognized
chart-pull or Helm-install error keeps its more specific code, so don't assume
`AZK8S0601` always means that the diagnostic container itself exited.

During a controlled retry, run:

```console
kubectl cluster-info
kubectl auth can-i get jobs.batch -n azure-arc-release
kubectl auth can-i list pods -n azure-arc-release
kubectl auth can-i get pods/log -n azure-arc-release
kubectl get jobs,pods -n azure-arc-release -o wide
kubectl get events -n azure-arc-release --sort-by=.lastTimestamp
```

`cluster-info` proves that the selected context can reach and authenticate to
the API server. Each `auth can-i` call isolates one read operation needed by
the workflow without reading object or log contents. The object and event
views then distinguish API access from admission, scheduling, image startup,
or container failure. If all checks succeed and no temporary object remains,
use the debug exception rather than creating resources by hand: expected
cleanup can remove the evidence before inspection. The issue is fixed when
the Job workflow completes and returns output for result parsing.

## `AZK8S0602`: `PostDiagnosticPrecheckFailed`

Despite its name, this is the blocking aggregate for a completed diagnostic
run with at least one explicit `Failed` result. In connectedk8s 1.11.5 the
required results are cluster DNS, required outbound connectivity, Microsoft
Entra connectivity, and Arc CRD ownership. A proxy-configured Entra check can
be reported as `NotApplicable` when the diagnostic pod can't consume that
proxy; the command prints a warning in that case.

Read the `Precheck summary` and the individual lines immediately above the
error. Diagnose only the checks marked `Failed`:

```console
kubectl run arc-dns-check --rm -i --restart=Never --image=busybox:1.36 -- nslookup kubernetes.default.svc.cluster.local
kubectl get customresourcedefinitions
```

The temporary `kubectl run` performs DNS resolution from a pod, which tests
the same cluster DNS path rather than DNS on the Azure CLI host. It creates a
short-lived pod and removes it after completion; use it only when policy
permits diagnostic pods. A successful lookup proves service-name resolution,
not external endpoint reachability. The CRD command lists names only and helps
identify pre-existing Arc CRDs; it doesn't prove ownership, so retain the
diagnostic ownership message for support. For outbound or Entra failures,
follow the matching `AZK8S0306`-`AZK8S0308` procedure and allow only documented
endpoints. The issue is fixed when every required result is `Passed` or an
explicitly allowed `NotApplicable` and onboarding proceeds.

## `AZK8S0603`: `PrediagnosticsIncomplete`

`Incomplete` means the extension couldn't trust the aggregate result. Common
paths are a Job that wasn't observed, a Job that didn't complete, no usable
pod output, or a required DNS, outbound, or Entra result that couldn't be
parsed. It is different from `AZK8S0602`: absence of evidence isn't treated as
a passed or failed connectivity check.

First read any preceding `AZK8S0604` or `AZK8S0605` warning and the
`jobExecutionStatus`, `dnsCheck`, `outboundConnectivityCheck`, `entraCheck`,
and `crdCheck` values in the summary. During one retry, observe:

```console
kubectl get jobs,pods -n azure-arc-release --watch
kubectl get events -n azure-arc-release --sort-by=.lastTimestamp
```

If the Job completes, preserve the saved
`cluster_diagnostic_checks_job_log.txt` and diagnoser results path printed by
the command. A missing result marker with a completed Job selects malformed or
unexpected diagnostic output rather than scheduling. Don't edit the logs to
make parsing succeed. If all Job states are healthy but the same field remains
`Incomplete`, attach sanitized logs and the extension version to support. The
issue is fixed when the Job completes and every required field is conclusive.

## `AZK8S0604`: `PrediagnosticsJobNotScheduled`

The extension watched namespace `azure-arc-release` for 180 seconds but never
observed `cluster-diagnostic-checks-job`. This warning is telemetry-bearing but
isn't raised directly; the command normally ends with `AZK8S0603`. The cause
can be an admission policy, SecurityContextConstraint, ResourceQuota, or an
object that couldn't be created or observed. It does not mean merely that a
pod remained `Pending` after the Job was seen.

During a retry, run these read-only checks from a second terminal:

```console
kubectl auth can-i create jobs.batch -n azure-arc-release
kubectl get resourcequota,limitrange -n azure-arc-release
kubectl get events -n azure-arc-release --sort-by=.lastTimestamp
kubectl get job cluster-diagnostic-checks-job -n azure-arc-release -o wide
```

Authorization isolates RBAC. Quota and limit objects show namespace
constraints but don't prove that a request violated them; an admission or
quota event provides that decision. Seeing the named Job during the watch
disproves this state even if its pod later fails, in which case use
`AZK8S0605`. `NotFound` after onboarding exits is inconclusive because cleanup
is expected. Correct the named policy, quota, or authorization issue through
the cluster owner. The issue is fixed when the Job is observed and creates a
pod.

## `AZK8S0605`: `PrediagnosticsJobNotComplete`

The extension observed the Job, but it didn't reach a `Complete` condition
within the 180-second watch, or its failed count reached three. Before cleanup,
the extension attempts to save pod description and partial logs and reports a
reason such as `ErrImagePull`, `ImagePullBackOff`, `CrashLoopBackOff`,
`OOMKilled`, a nonzero exit code, or `Unschedulable`.

During a retry, identify the current pod and inspect it while it exists:

```console
kubectl get pods -n azure-arc-release -l job-name=cluster-diagnostic-checks-job -o wide --watch
kubectl describe pod -n azure-arc-release "<diagnostic-pod>"
kubectl logs -n azure-arc-release "<diagnostic-pod>" --all-containers
kubectl logs -n azure-arc-release "<diagnostic-pod>" --all-containers --previous
```

The watch reveals whether the pod is pending, running, restarting, or
terminated. `describe` provides scheduler, image-pull, mount, eviction, and
container-state reasons. Current logs diagnose a started process; `--previous`
is useful only when a container restarted and a prior instance exists. Correct
the reported cause: restore approved node capacity for scheduling or OOM,
documented MCR egress and trust for image pulls, or the dependency named in
container logs. Don't increase timeouts merely to hide a deterministic
failure. The issue is fixed when the Job reaches `Complete` within the watch.

## `AZK8S0606`: `PrediagnosticsLogSaveFailed`

This warning means the extension obtained diagnostic pod output but couldn't
write its local copy because of an `OSError` other than no space left on
device, or a value or type conversion error. Disk-full has separate telemetry
and doesn't emit `AZK8S0606` in connectedk8s 1.11.5. The warning is nonfatal:
result parsing continues from the in-memory output.

Use the directory from the command's saved-log message or debug output. Test
the exact parent without displaying any existing log contents:

```powershell
$parent = Split-Path -LiteralPath "<diagnostic-log-path>" -Parent
Test-Path -LiteralPath $parent -PathType Container
Get-Acl -LiteralPath $parent | Format-List Owner,Access
$drive = Split-Path -Qualifier $parent
Get-PSDrive -Name $drive.TrimEnd(':')
```

```bash
parent=$(dirname -- '<diagnostic-log-path>')
test -d "$parent" && test -w "$parent"; echo $?
df -h -- "$parent"
```

The existence check distinguishes a missing directory from access failure.
ACL or writability output shows whether the current identity can write there;
free-space output is supporting evidence, though a full filesystem normally
uses the separate disk-full path. Don't broaden directory permissions or run
Azure CLI as an administrator solely to save logs. Use an approved writable
location or correct ownership according to host policy. The warning is fixed
when the local copy writes successfully; a conclusive in-memory result remains
valid when no local copy is required.

## `AZK8S0607`: `PrediagnosticsHelmInstallFailed`

The extension ran `helm upgrade --install cluster-diagnostic-checks` in
`azure-arc-release` with `--wait` and a 60-second timeout, and Helm returned
nonzero. `forbidden` and `timed out waiting for the condition` are classified
as user-correctable telemetry, but the complete processed Helm detail selects
the actual repair. The extension requests cleanup before returning the error.

During a retry, inspect authorization and transient state:

```console
helm list --all-namespaces --deployed --failed --pending --uninstalling --uninstalled --superseded --filter "^cluster-diagnostic-checks$"
kubectl auth can-i create jobs.batch -n azure-arc-release
kubectl get events -n azure-arc-release --sort-by=.lastTimestamp
kubectl get jobs,pods -n azure-arc-release -o wide --watch
```

The explicit status flags work with Helm 3 and Helm 4 and expose a release
only while its record remains. No row after failure is expected cleanup, not
proof that Helm never ran. Authorization isolates a common `forbidden` cause.
Events and the watch identify an install that created resources but couldn't
make them ready before Helm's timeout. Correct the first Helm detail or event:
cluster RBAC or admission ownership for `forbidden`, namespace quota or policy
for rejected resources, documented registry connectivity for image pulls, or
node capacity for scheduling. Don't install the chart manually or delete the
temporary release. The issue is fixed when the extension-owned release
installs, its Job starts, and the command advances to check results.

## Contact support

If the resolution does not fix the problem, provide:

- The `AZK8Snnnn` code and complete sanitized error text.
- Azure CLI and extension versions from `az version`.
- The command name and UTC timestamp, without credentials or tokens.
- The correlation or request ID and Azure cloud or region when reported.
- The subscription, resource group, and cluster identifiers through the secure
  support channel; replace them with stable placeholders in shared logs.
- Sanitized `az connectedk8s troubleshoot` output.
- Relevant `azure-arc` pod status, events, and logs.
- The diagnostic command results and expected-result comparison from the
  matching detailed procedure.

## Related content

- [Azure Arc-enabled Kubernetes error-code reference](error-codes.md)
- [Troubleshoot platform issues for Azure Arc-enabled Kubernetes clusters](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting)
