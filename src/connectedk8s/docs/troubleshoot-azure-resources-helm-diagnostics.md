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
helm list --all --all-namespaces --filter "^azure-arc$"
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
installing in the cluster.

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
