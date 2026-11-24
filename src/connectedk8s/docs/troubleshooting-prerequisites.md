# Prerequisites for troubleshooting Azure Arc-enabled Kubernetes errors

Complete these checks before using the
[connectedk8s error-code reference](error-codes.md). They establish the local
tool, Azure, Kubernetes, and network context used by the failing command.
For issues involving infrastructure outside the connectedk8s CLI, contact the
appropriate administrator or provider.

## Supported environment

Review the current
[Azure Arc-enabled Kubernetes system requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/system-requirements)
and use supported Azure CLI, connectedk8s extension, Kubernetes, and Helm
versions for the operation.

Run these commands from the same computer and shell as the failing command:

```azurecli
az version
az extension show --name connectedk8s --query version --output tsv
az account show --query "{subscription:id,tenant:tenantId}" --output yaml
kubectl version --client
```

Confirm that Azure CLI is using the intended tenant and subscription. Update
Azure CLI and the extension before troubleshooting an issue that might be
resolved in a newer supported release.

## Kubernetes access

Use the exact kubeconfig path and context supplied to Azure CLI.

If `--kube-config` wasn't supplied, Azure CLI uses `KUBECONFIG` when it is
set. Otherwise, the default is `$HOME/.kube/config` on Linux or macOS and
`%USERPROFILE%\.kube\config` on Windows. Then run:

```console
kubectl --kubeconfig "<path>" config get-contexts "<context>"
kubectl --kubeconfig "<path>" --context "<context>" get --raw=/version
kubectl --kubeconfig "<path>" --context "<context>" auth can-i get namespaces
```

The context must exist, `/version` must return Kubernetes version data, and the
authorization check must return `yes`. If these checks fail, contact the
cluster administrator or Kubernetes provider for kubeconfig issuance,
API-server availability, or Kubernetes RBAC.

## Minimum onboarding permissions

Azure and Kubernetes permissions are separate:

- **Azure:** assign the connecting identity the
  [Kubernetes Cluster - Azure Arc Onboarding](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/containers#kubernetes-cluster---azure-arc-onboarding)
  role at the intended resource-group scope. The identity also needs read
  access to the existing resource group.
- **Kubernetes:** use an approved onboarding identity with
  [`cluster-admin`](https://learn.microsoft.com/azure/architecture/hybrid/arc-hybrid-kubernetes#cluster-registration),
  or an organization-defined equivalent that can create the resources in the
  Arc agent chart. Don't retain `cluster-admin` access after troubleshooting.

Permissions vary by operation. Check the documentation before assigning roles
for [`az connectedk8s update`](https://learn.microsoft.com/cli/azure/connectedk8s#az-connectedk8s-update),
[`az connectedk8s delete`](https://learn.microsoft.com/cli/azure/connectedk8s#az-connectedk8s-delete),
[Cluster Connect](https://learn.microsoft.com/azure/azure-arc/kubernetes/cluster-connect),
or [Custom Locations](https://learn.microsoft.com/azure/azure-arc/kubernetes/custom-locations).

## Network and existing-cluster readiness

Apply the
[Azure Arc-enabled Kubernetes network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements).
Work with the cluster or network administrator for DNS, firewall, outbound
proxy, private routing, and provider-specific connectivity changes.

For an existing connected cluster, run the supported diagnostic command:

```azurecli
az connectedk8s troubleshoot --resource-group "<resource-group>" --name "<cluster-name>" --kube-config "<path>" --kube-context "<context>"
```

Use [Azure Arc platform troubleshooting](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting)
for Arc agent and service issues. Use
[Diagnose connection issues](https://learn.microsoft.com/azure/azure-arc/kubernetes/diagnose-connection-issues)
for the supported diagnostic collection workflow.

## Protect diagnostic data

Don't display or share kubeconfig contents, tokens, certificates, private keys,
proxy credentials, customer endpoints, returned Cluster Connect credentials,
or unsanitized diagnostic files. Share subscription, resource group, and
cluster identifiers only through an approved secure support channel.

After these checks pass, use the complete `AZK8Snnnn` value in the
[connectedk8s error-code reference](error-codes.md).
