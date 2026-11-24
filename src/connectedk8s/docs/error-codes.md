# Troubleshoot Azure Arc-enabled Kubernetes error codes

Use this reference when an `az connectedk8s` command reports an error in the
`AZK8Snnnn` format. Complete the
[troubleshooting prerequisites](troubleshooting-prerequisites.md) first, then
find the reported error code in the catalog below.

## What this guide covers

The connectedk8s extension reports stable `AZK8Snnnn` error codes for:

- Local argument, file, operating-system, and command-sequencing validation.
- Pre-onboarding diagnostic results.
- Downloading, configuring, starting, and monitoring the local Cluster Connect
  client proxy.

Errors originating outside the extension, such as kubeconfig access,
Kubernetes API health or RBAC, cluster networking, Azure RBAC or service
availability, workload scheduling, registry policies, and feature-specific
services, are directed to the relevant documentation or administrator.

## How to read an error code

The code identifies the connectedk8s operation or failure category. The text
after the code carries the specific resource, endpoint, operation, or source
error. Record both when investigating or reporting the failure.

`AZK8S0001` doesn't by itself identify whether the problem originated in Azure,
Kubernetes, or the local computer.

### Multiple error codes

Prioritize the most specific code. During onboarding, keep a specific
`AZK8S0300`-series DNS or outbound result together with the later
`AZK8S0600`-series result. The specific code identifies the failed check; the
`AZK8S0600`-series code indicates that the diagnostic command didn't complete.
Include both codes when troubleshooting or contacting support.

### Codes that may be nonfatal

The following codes might not cause the command to fail:

- `AZK8S0308`: The endpoint responded, but the requested operation might not
  have succeeded.
- `AZK8S0701`: The command might continue without Custom Locations when another
  requested feature succeeds.

Use the final command result to determine whether the requested operation
succeeded.

### Local client proxy

The `AZK8S0800` series applies to the local Cluster Connect client proxy
started by `az connectedk8s proxy`, not the outbound HTTP or HTTPS proxy used
for Arc onboarding. For authentication, Azure permissions, connected state,
and Cluster Connect service behavior, use the linked Cluster Connect guidance.

## Error catalog

### General and input

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0001` `UnexpectedError` | The command encountered an unexpected error. | Follow the detailed error, update Azure CLI and the extension, and retry once. Verify the subscription, resource group, and cluster name when the command targets an existing resource. |
| `AZK8S0002` `UnsupportedOperatingSystem` | The command is running on an unsupported operating system. | Azure CLI is running on an unsupported platform or the platform couldn't be identified. Use a supported Azure CLI platform listed in [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli). |
| `AZK8S0003` `UnsupportedProvisionedClusterOperation` | The requested operation isn't supported for an AKS Arc provisioned cluster. | A connectedk8s lifecycle command was used for a provisioned cluster managed through `az aksarc`. Use the `az aksarc` command named in the error. |
| `AZK8S0100` `InvalidArgumentValue` | A command argument is invalid. | The named value is malformed, outside its supported range, or incompatible with the operation. Correct the named value using `az connectedk8s <command> --help`. |
| `AZK8S0101` `UpdateNoParameters` | No changes were specified for `az connectedk8s update`. | Supply at least one supported update option. |
| `AZK8S0102` `UpdateProxyParameterConflict` | `az connectedk8s update` included both proxy settings and `--disable-proxy`. | The command requests proxy configuration and proxy removal at the same time. Choose either proxy configuration or proxy removal. |
| `AZK8S0103` `ProxyCertificatePathNotFound` | The proxy certificate file can't be found. | The path is incorrect, relative to a different execution environment, or unreadable by the current identity. Supply a readable absolute path and follow the [outbound proxy guidance](https://learn.microsoft.com/azure/azure-arc/kubernetes/diagnose-connection-issues#connections-with-a-proxy-server). |
| `AZK8S0104` `InvalidLocation` | The requested Azure location isn't supported. | The location name is invalid or isn't available for connected clusters. Select a location returned for `Microsoft.Kubernetes/connectedClusters`. |
| `AZK8S0105` `PrivateLinkScopeLocationMismatch` | The connected cluster and Azure Arc Private Link Scope locations differ. | The selected Private Link Scope was created in a different Azure location. Use matching locations as required by [Azure Arc Private Link](https://learn.microsoft.com/azure/azure-arc/kubernetes/private-link). |
| `AZK8S0106` `InvalidGatewayArmId` | The gateway resource ID is invalid or identifies the wrong resource type. | The ID is malformed, the resource doesn't exist, or it isn't a `Microsoft.HybridCompute/gateways` resource. Supply an existing `Microsoft.HybridCompute/gateways` resource ID. |
| `AZK8S0107` `ProxyBypassStateInvalid` | The saved proxy-bypass state doesn't match the Helm configuration. | The saved proxy-bypass information is inconsistent or unreadable. Contact Azure support and provide sanitized Helm values. |

### Kubernetes access

Contact the cluster administrator or Kubernetes provider for assistance with
these errors. Use the same kubeconfig and context as the failing command.

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0200` `KubeconfigLoadFailed` | The kubeconfig couldn't be opened or parsed. | The path, YAML, selected context, or a referenced credential file is missing or invalid. Confirm the lookup path and context in the [Kubernetes access prerequisites](troubleshooting-prerequisites.md#kubernetes-access), or restore the provider-issued kubeconfig. |
| `AZK8S0201` `ConfigMapReadFailed` | Azure CLI couldn't read a ConfigMap required by the current workflow. | The ConfigMap is absent, the identity lacks read access, or the Kubernetes API request failed. Use the name and namespace in the detailed error and verify the identity can read it: `kubectl --kubeconfig "<path>" --context "<context>" auth can-i get configmap/<name> -n <namespace>`. |
| `AZK8S0202` `KubernetesConnectivityFailed` | The Kubernetes `/version` request failed. | Authentication, TLS, DNS, routing, firewall, VPN, or API-server health prevented the request. Run the [Kubernetes access checks](troubleshooting-prerequisites.md#kubernetes-access). |
| `AZK8S0203` `KubernetesDistributionDetectionFailed` | Azure CLI couldn't identify the Kubernetes distribution from node data. Connect continues with the generic distribution. | Node-list access failed or the returned node metadata didn't identify a supported distribution. If onboarding succeeds, no action is required. To specify the distribution, use `az connectedk8s connect --distribution <value>` or update it later with `az connectedk8s update --distribution <value>`. |
| `AZK8S0204` `KubernetesNamespaceGetFailed` | The `azure-arc` namespace couldn't be read. | Kubernetes RBAC or API-server health prevented access to the namespace. Run the [Kubernetes access checks](troubleshooting-prerequisites.md#kubernetes-access). If access is denied, contact the cluster administrator. |
| `AZK8S0205` `LinuxNodeNotFound` | Azure CLI found no Linux node and reports a warning; Arc agents still require Linux scheduling capacity. | The cluster has no Linux node available for Arc agent scheduling. Provide Linux scheduling capacity that meets the [system requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/system-requirements). |
| `AZK8S0206` `ClusterRoleBindingCreateForbidden` | The identity can't create ClusterRoleBindings. | Kubernetes RBAC denies the required cluster-scoped operation. Use an approved identity that meets the [minimum onboarding permissions](troubleshooting-prerequisites.md#minimum-onboarding-permissions). |
| `AZK8S0207` `KubernetesConfigurationLoadFailed` | Cluster Connect couldn't update the local kubeconfig. | The kubeconfig is missing, invalid, unreadable, or unwritable. Restore a valid, readable, and writable kubeconfig. |
| `AZK8S0208` `KubernetesPrivateKeyInjectionFailed` | The onboarding namespace or private-key Secret couldn't be created or replaced. | Kubernetes RBAC, admission policy, or conflicting namespace or Secret state blocked the write. Review the detailed Kubernetes error. For denied access, use an approved identity that meets the [minimum onboarding permissions](troubleshooting-prerequisites.md#minimum-onboarding-permissions). |
| `AZK8S0209` `ConfigMapWriteFailed` | A required ConfigMap couldn't be created or updated. | Kubernetes RBAC, admission policy, or conflicting ConfigMap state blocked the write. Review the detailed Kubernetes error. For denied access, use an approved identity that meets the [minimum onboarding permissions](troubleshooting-prerequisites.md#minimum-onboarding-permissions). |

### Network and connectivity

Use the detailed endpoint from the error with the
[Azure Arc network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements).
Use [Diagnose connection issues](https://learn.microsoft.com/azure/azure-arc/kubernetes/diagnose-connection-issues)
for the supported DNS and outbound-connectivity diagnostic workflow.
Work with the cluster or network administrator for DNS, firewall, proxy, and
routing changes.

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0300` `DataPlaneHealthCheckFailed` | The authenticated Arc data-plane health request failed. | DNS, proxy, TLS, routing, authentication, authorization, throttling, or service health blocked the request. Follow the detailed status. Contact Azure support for persistent authenticated `429` or `5xx` responses. |
| `AZK8S0301` `DnsNxDomain` | Cluster DNS returned `NXDOMAIN`. | The hostname, forwarding rule, or private DNS configuration is incorrect. Correct the hostname, forwarding, or private DNS configuration. |
| `AZK8S0302` `DnsTimeout` | Cluster DNS repeatedly timed out. | A resolver is unavailable or DNS traffic is blocked. Check resolver availability and DNS access with the cluster or network administrator. |
| `AZK8S0303` `DnsServerFailure` | Cluster DNS returned `SERVFAIL`. | The resolver couldn't complete the query through its upstream path. Correct the resolver's upstream or forwarding configuration. |
| `AZK8S0304` `DnsNoServersReachable` | No configured resolver was reachable. | Pod-to-resolver routing, network policy, or firewall rules block DNS. Restore pod-to-resolver connectivity. |
| `AZK8S0305` `DnsCommunicationsError` | Communication with the resolver was interrupted. | The resolver or network path reset or interrupted the query. Correct the cluster DNS or network path. |
| `AZK8S0306` `OnboardingOutboundConnectivityFailed` | A required endpoint returned no HTTP response. | DNS, routing, firewall, outbound proxy, or TLS prevented an HTTP response. Allow the required endpoint and port. |
| `AZK8S0307` `ClusterConnectOutboundConnectivityFailed` | The Cluster Connect endpoint returned no HTTP response. | Cluster Connect websocket or Service Bus access is blocked. Apply the [Cluster Connect network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements). |
| `AZK8S0308` `OutboundEndpointNonSuccessResponse` | An endpoint returned HTTP `4xx` or `5xx`; network reachability was established. | The endpoint rejected or couldn't complete the operation after the network request arrived. Use the HTTP status and detailed error to troubleshoot the request. Don't change networking for this code alone. |
| `AZK8S0309` `CertificatePulldownFailed` | Arc identity certificate synchronization failed. | Arc agents aren't healthy or the required certificate Secret wasn't synchronized. Use [Azure Arc platform troubleshooting](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting). |

### Azure resources, Helm, and agents

Use the guidance that matches the error:

- **Account scope or RBAC:** Review the
  [minimum onboarding permissions](troubleshooting-prerequisites.md#minimum-onboarding-permissions).
- **`Microsoft.Kubernetes` registration:** Review
  [resource provider registration](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-providers-and-types#register-resource-provider).
- **Helm, scheduling, image pulls, or agent health:** Use
  [Azure Arc platform troubleshooting](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting)
  with the cluster operator.

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0400` `ConnectedClusterCreateFailed` | `az connectedk8s connect` couldn't create the connected-cluster resource. | The ARM request failed because of authorization, policy, invalid state, conflict, throttling, or service health. Resolve the detailed ARM status with the Azure resource administrator. |
| `AZK8S0401` `ConnectedClusterUpdateFailed` | `az connectedk8s update` couldn't read or update the resource. | Authorization, policy, resource state, conflict, throttling, or service health blocked the request. Resolve the detailed ARM status. |
| `AZK8S0402` `ConnectedClusterDeleteFailed` | `az connectedk8s delete` couldn't read or delete the resource. | Authorization, policy, resource state, conflict, throttling, or service health blocked the request. Resolve the detailed ARM status. |
| `AZK8S0403` `ClusterAlreadyOnboarded` | The cluster passed to `az connectedk8s connect` is registered to a different Azure resource identity. | The existing Arc registration uses another subscription, resource group, or connected-cluster name. Use the existing registration or the kubeconfig for the intended cluster. |
| `AZK8S0404` `ConnectedClusterResourceAlreadyExists` | The Azure name passed to `az connectedk8s connect` belongs to another connected cluster. | A connected-cluster resource with the same name already represents a different Kubernetes cluster. Select the intended existing resource or a unique name. |
| `AZK8S0405` `ConnectedClusterResourceNotFound` | The resource requested by `az connectedk8s update` or `az connectedk8s delete` wasn't found. | The selected subscription, resource group, or cluster name is incorrect, or the resource was already deleted. Correct the subscription, resource group, and name. If a delete target was already removed, no Azure resource remains to delete. |
| `AZK8S0406` `InvalidDeleteRequest` | The kubeconfig used by `az connectedk8s delete` doesn't match the requested Azure resource. | The delete command targets a different subscription, resource group, or name than the existing Arc registration. Use matching cluster and Azure identities. |
| `AZK8S0407` `ResourceProviderFetchFailed` | Azure couldn't return resource-provider information. | Account scope, authorization, proxy access, or Azure service health blocked the provider query. Verify account scope, authorization, proxy access, and Azure service health. |
| `AZK8S0408` `ConnectedClusterProviderNotRegistered` | `Microsoft.Kubernetes` isn't registered. | The subscription hasn't completed connected-cluster provider registration. Ask the subscription administrator to register the provider. |
| `AZK8S0409` `ConnectedClusterResourceIdMissing` | Azure returned incomplete connected-cluster information. | Retry once, then contact Azure support if the resource information remains incomplete. |
| `AZK8S0500` `HelmReleaseInstallFailed` | The Arc Helm release couldn't be installed or upgraded. | Helm or Kubernetes reported a chart, admission, scheduling, image, timeout, or cluster-access failure. Use the Helm error and Kubernetes events to resolve the underlying cluster cause. |
| `AZK8S0501` `HelmReleaseDeleteFailed` | The Arc Helm release couldn't be removed. | Helm or Kubernetes rejected or couldn't complete release deletion. Resolve the Helm error through the supported delete workflow. |
| `AZK8S0502` `HelmChartPullFailed` | The Arc chart couldn't be pulled. | Registry DNS, TLS, proxy, authentication, or network access failed. Verify registry access against the [Azure Arc network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements). |
| `AZK8S0503` `HelmChartExportFailed` | The expected exported chart wasn't created. | Local storage, file permissions, archive handling, or endpoint security blocked export. Verify local storage and endpoint-security policy, then retry once. |
| `AZK8S0504` `HelmRepositoryAddFailed` | Helm couldn't add the configured repository. | The repository name or URL is invalid, unreachable, or rejected. Correct the repository configuration and access path. |
| `AZK8S0505` `HelmReleaseListFailed` | Helm couldn't query release metadata. | Cluster access, Kubernetes RBAC, or release metadata retrieval failed. Run the [Kubernetes access checks](troubleshooting-prerequisites.md#kubernetes-access) and review the detailed Helm error. |
| `AZK8S0506` `AgentStateTimeout` | Azure didn't report whether the Arc agents became ready before timeout. | Arc agents remained unhealthy or disconnected, or Azure didn't receive their latest status. Check Arc agent health, then contact Azure support if the agents are healthy. |
| `AZK8S0507` `KeyPairGenerationFailed` | Local key generation failed. | The supported cryptography operation failed in the local process. Retry once on a supported platform. |
| `AZK8S0508` `ReleaseNamespaceNotFound` | The Arc Helm release namespace wasn't found. | An unintended cluster is selected, the release is absent, or release metadata is inconsistent. Confirm the intended cluster and use the supported recovery path from platform troubleshooting. |
| `AZK8S0509` `HelmValuesGetFailed` | Helm couldn't read the current release values. | Cluster access, Kubernetes RBAC, or release state prevented the query. Run the [Kubernetes access checks](troubleshooting-prerequisites.md#kubernetes-access) and review the detailed Helm error. |
| `AZK8S0510` `HelmNotInstalled` | A required local Helm client wasn't found. | Helm isn't installed or isn't available on `PATH` in an environment that requires it. Install the supported Helm version for the environment. |
| `AZK8S0511` `HelmVersionTooOld` | The Helm major version is below 3. | The selected Helm executable is an unsupported older version. Upgrade to Helm 3 or later. |
| `AZK8S0512` `HelmTimeoutPendingOrUnschedulable` | Workloads couldn't schedule before timeout. | Kubernetes events report capacity, placement, taint, affinity, quota, or admission constraints. Resolve the Kubernetes scheduling events. |
| `AZK8S0513` `HelmTimeoutImagePullFailed` | Workloads couldn't pull images before timeout. | Registry DNS, network, authentication, policy, or image availability blocked a pull. Resolve the image-pull events using the network requirements and registry policy. |
| `AZK8S0514` `HelmTimeout` | Helm timed out without a more specific error code. | A cluster or release condition prevented completion, but Kubernetes didn't report a more specific scheduling or image-pull error. Use Helm status, pod status, and Kubernetes events to identify the cause. |
| `AZK8S0515` `HelmClientError` | The operating system couldn't start Helm. | The executable path, local permission, architecture, or endpoint-security policy blocked process creation. Correct the executable path, permission, or endpoint-security policy. |

### Pre-onboarding diagnostics

Run `az connectedk8s troubleshoot` and keep any specific `AZK8S0300`-series
result with the summary code. Use the guidance that matches the error:

- **Run or configure diagnostics:** Review the
  [`az connectedk8s troubleshoot` reference](https://learn.microsoft.com/cli/azure/connectedk8s#az-connectedk8s-troubleshoot).
- **Kubernetes API or RBAC:** Run the
  [Kubernetes access checks](troubleshooting-prerequisites.md#kubernetes-access).
- **DNS or outbound connectivity:** Use
  [Diagnose connection issues](https://learn.microsoft.com/azure/azure-arc/kubernetes/diagnose-connection-issues)
  and review the
  [Azure Arc network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements).
- **Job scheduling, admission, Helm, or image pulls:** Review Kubernetes events
  and use
  [Azure Arc platform troubleshooting](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting).
- **Saving logs locally:** Check local storage and file permissions.

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0600` `PrediagnosticsFailed` | The diagnostic workflow failed unexpectedly. | An unexpected error interrupted diagnostics. Follow the detailed error and any specific code reported with it. |
| `AZK8S0601` `PrediagnosticsJobExecutionFailed` | The diagnostic Job workflow was interrupted. | Kubernetes API access, scheduling, or Job execution failed. Use the Kubernetes error or event to resolve access, scheduling, or API health. |
| `AZK8S0602` `PostDiagnosticPrecheckFailed` | At least one required check failed. | A DNS, outbound connectivity, or identity connectivity check reported failure. Fix each specific failed check before retrying onboarding. |
| `AZK8S0603` `PrediagnosticsIncomplete` | The diagnostic result wasn't conclusive. | The Job wasn't scheduled, didn't finish, or didn't produce a required result. Resolve the accompanying Job, scheduling, or log-access result. |
| `AZK8S0604` `PrediagnosticsJobNotScheduled` | The diagnostic Job didn't appear before timeout. | Scheduling, quota, admission policy, or Kubernetes API health prevented the Job from starting. Resolve scheduling or admission-policy events. |
| `AZK8S0605` `PrediagnosticsJobNotComplete` | The diagnostic Job didn't complete in time. | Its pod remained pending, failed repeatedly, or didn't finish within the expected time. Resolve the Job and pod events. |
| `AZK8S0606` `PrediagnosticsLogSaveFailed` | A local copy of diagnostic logs couldn't be saved. | Local storage or file permissions blocked the save. Correct local storage or file permissions and retain the displayed diagnostic result. |
| `AZK8S0607` `PrediagnosticsHelmInstallFailed` | The temporary diagnostic Helm release couldn't be installed. | Helm, cluster access, admission, scheduling, image pull, or timeout blocked installation. Resolve the detailed Helm and Kubernetes error. |

### Custom Locations and Cluster Connect

For Custom Locations behavior, permissions, and recovery, use the
[Custom Locations documentation](https://learn.microsoft.com/azure/azure-arc/kubernetes/custom-locations).

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0700` `CustomLocationsEnableFailed` | Custom Locations couldn't be enabled. | A Custom Locations prerequisite failed and no other requested feature could continue. Follow the Custom Locations documentation and the detailed error. |
| `AZK8S0701` `CustomLocationsOidFetchFailed` | The tenant-specific service-principal object ID couldn't be obtained. | The service principal is absent, Graph access failed, or the identity can't read it. Use the documented administrator-provided object-ID workflow. |
| `AZK8S0702` `CustomLocationsRegistrationCheckFailed` | A prerequisite or provider-registration check failed. | Account scope, authorization, Graph access, or `Microsoft.ExtendedLocation` registration lookup failed. Verify account scope, authorization, and `Microsoft.ExtendedLocation` registration. |

The following codes apply to the local Cluster Connect client proxy started by
`az connectedk8s proxy`, not the outbound HTTP or HTTPS proxy configured for
Arc onboarding. Use the guidance that matches the error:

- **Setup, authentication, or Azure roles:** Review
  [Cluster Connect setup and authentication](https://learn.microsoft.com/azure/azure-arc/kubernetes/cluster-connect).
- **Disconnected agents or connection failures:** Use
  [Cluster Connect troubleshooting](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting#cluster-connect-problems).
- **Ports or command options:** Review the
  [`az connectedk8s proxy` reference](https://learn.microsoft.com/cli/azure/connectedk8s#az-connectedk8s-proxy).
- **MCR or outbound access:** Review the
  [Azure Arc network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements).

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0800` `ClientProxyDownloadFailed` | `az connectedk8s proxy` couldn't prepare the local client proxy. | MCR access, local storage, archive extraction, architecture selection, file permission, or endpoint security blocked preparation. Verify MCR access, local storage, file permissions, architecture, and endpoint-security policy. |
| `AZK8S0801` `ClientProxyPortInUse` | A local port required by `az connectedk8s proxy` is occupied. | Another process or proxy session is using one of the required local ports. Stop that process or select another supported `--port`. |
| `AZK8S0802` `ClientProxyStartFailed` | `az connectedk8s proxy` couldn't start the local proxy process. | Local execution permission, architecture, process policy, or endpoint security blocked creation. Correct local execution permission or endpoint-security policy. |
| `AZK8S0803` `ClientProxyConfigCreateFailed` | `az connectedk8s proxy` couldn't replace the local proxy configuration. | Local storage, file permission, file locking, or endpoint security blocked the write. Correct local storage or file permissions; don't share the configuration. |
| `AZK8S0804` `ClientProxyClosed` | The proxy started by `az connectedk8s proxy` exited. | The local process encountered a runtime, capacity, configuration, network, credential, or endpoint-security failure. Use sanitized `--debug` output and local process-security events, then follow Cluster Connect troubleshooting. |
| `AZK8S0805` `ClusterCredentialsGetFailed` | `az connectedk8s proxy` couldn't retrieve Cluster Connect credentials. | Authentication, Azure RBAC, disconnected agents, disabled Cluster Connect, or service health blocked retrieval. Verify authentication, the required Cluster Connect roles, connected state, and feature enablement. |

## Contact support

If the linked guidance doesn't resolve the problem, provide the following
information to Azure support:

- The `AZK8Snnnn` code and complete sanitized error text.
- Azure CLI and extension versions.
- The command name and UTC timestamp, without arguments containing secrets.
- Correlation or request IDs and the Azure cloud or region when reported.
- Subscription, resource group, and cluster identifiers only through the
  secure support channel.
- Sanitized output from `az connectedk8s troubleshoot` and relevant Arc pod
  status or events.

Never include kubeconfig contents, tokens, certificates, private keys, proxy
credentials, returned Cluster Connect credentials, or unsanitized logs.

## Related content

- [Azure Arc-enabled Kubernetes system requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/system-requirements)
- [Connect an existing Kubernetes cluster to Azure Arc](https://learn.microsoft.com/azure/azure-arc/kubernetes/quickstart-connect-cluster#prerequisites)
- [Azure Arc-enabled Kubernetes network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements)
- [Troubleshoot Azure Arc-enabled Kubernetes](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting)
- [Diagnose Azure Arc-enabled Kubernetes connection issues](https://learn.microsoft.com/azure/azure-arc/kubernetes/diagnose-connection-issues)
- [Use Cluster Connect](https://learn.microsoft.com/azure/azure-arc/kubernetes/cluster-connect)
- [Create and manage Custom Locations](https://learn.microsoft.com/azure/azure-arc/kubernetes/custom-locations)
