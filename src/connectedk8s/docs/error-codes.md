# Troubleshoot Azure Arc-enabled Kubernetes error codes

Use this reference when an `az connectedk8s` command reports an error in the
`AZK8Snnnn` format. Complete the
[troubleshooting prerequisites](troubleshooting-prerequisites.md) first, then
find the complete code below. This reference was validated against the
published `connectedk8s` extension version 1.11.6.

## What this guide covers

The connectedk8s extension reports stable `AZK8Snnnn` error codes for:

- Local argument, file, operating-system, and command-sequencing validation.
- Running pre-onboarding diagnostics and preserving specific check results.
- Downloading, configuring, starting, and monitoring the local Cluster Connect
  client proxy.

Errors originating outside the extension, such as kubeconfig access,
Kubernetes API health or RBAC, cluster networking, Azure RBAC or service
availability, workload scheduling, registry policies, and feature-specific
services, are directed to the relevant documentation or administrator.

## How classification works

The code identifies the connectedk8s operation or failure category. The text
after the code carries the specific resource, endpoint, operation, or source
error. Keep both when investigating or escalating the failure.

The extension reports a specific code when it recognizes the failure stage.
`AZK8S0001` is the fallback for an exception that wasn't
classified more specifically. It doesn't establish that Azure, Kubernetes, or
the local computer caused the failure.

### Multiple and nonfatal codes

Use the most specific code first. During onboarding, keep a specific
`AZK8S0300`-series DNS or outbound result together with the later
`AZK8S0600`-series result. The specific code identifies the failed check; the
`AZK8S0600`-series code identifies why the connectedk8s diagnostic stage
stopped. The aggregate code must not replace the specific result.

Some classifications are nonfatal. `AZK8S0308` means an endpoint returned an
HTTP response, which proves network reachability but not operation success.
`AZK8S0701` can mean a mixed feature request continued without Custom
Locations. Use the final command result and all reported codes together.

### Pre-onboarding diagnostic stages

These codes describe installation and observation of the temporary diagnostic
workload and interpretation of its results:

| Stage | Codes | What the code indicates |
| --- | --- | --- |
| Start and observe the diagnostic workload | `AZK8S0601`, `AZK8S0604`, `AZK8S0605`, `AZK8S0607` | The extension couldn't install, observe, or complete the temporary workload. Kubernetes events can identify an underlying cluster cause. |
| Read and interpret results | `AZK8S0602`, `AZK8S0603` | A required check failed or the extension couldn't obtain a conclusive result. Preserve accompanying `AZK8S0300`-series findings. |
| Save a local copy | `AZK8S0606` | Saving logs failed; this doesn't replace the diagnostic result. |
| Complete the diagnostic workflow | `AZK8S0600` | An unexpected failure occurred after any more specific findings were retained. |

### Local client-proxy stages

The `AZK8S0800` series applies to the local Cluster Connect client proxy
started by `az connectedk8s proxy`, not the outbound HTTP or HTTPS proxy used
for Arc onboarding. The codes identify the last completed local stage:

| Stage | Code | What the code establishes |
| --- | --- | --- |
| Prepare the platform-specific proxy artifact | `AZK8S0800` | Local preparation didn't complete. |
| Reserve the required local ports | `AZK8S0801` | At least one required port was already occupied. |
| Replace the extension-managed local configuration | `AZK8S0803` | Artifact and port preparation completed, but the configuration write failed. |
| Start the local process | `AZK8S0802` | Preparation and configuration completed, but process creation failed. |
| Retrieve and register Cluster Connect credentials | `AZK8S0805` | The process started, but credential exchange didn't complete. |
| Monitor the running process | `AZK8S0804` | The process started successfully and later exited. |

Later-stage codes establish that earlier local stages completed. For
authentication, Azure permissions, connected state, and Cluster Connect
service behavior, use the linked Cluster Connect guidance.

## Error catalog

### General and input

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0001` `UnexpectedError` | The extension couldn't classify the failure more specifically. | **Possible cause:** An unexpected exception occurred before a more specific error code was available. In version 1.11.6, a missing `az connectedk8s show` target is one known case. Follow the detailed error. For a missing `show` target, verify the subscription, resource group, and cluster name. Otherwise, update Azure CLI and the extension, retry once, then contact support if it repeats. |
| `AZK8S0002` `UnsupportedOperatingSystem` | The command is running on an unsupported operating system. | **Possible cause:** Azure CLI is running on an unsupported platform or the platform couldn't be identified. Use a supported Azure CLI platform listed in [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli). |
| `AZK8S0003` `UnsupportedProvisionedClusterOperation` | The requested operation isn't supported for an AKS Arc provisioned cluster. | **Possible cause:** A connectedk8s lifecycle command was used for a provisioned cluster managed through `az aksarc`. Use the `az aksarc` command named in the error. |
| `AZK8S0100` `InvalidArgumentValue` | A command argument is invalid. | **Possible cause:** The named value is malformed, outside its supported range, or incompatible with the operation. Correct the named value using `az connectedk8s <command> --help`. |
| `AZK8S0101` `UpdateNoParameters` | No update setting was supplied. | **Possible cause:** `az connectedk8s update` was run without an option that changes the resource. Supply at least one supported update option. |
| `AZK8S0102` `UpdateProxyParameterConflict` | Proxy settings and `--disable-proxy` were supplied together. | **Possible cause:** The command requests proxy configuration and proxy removal at the same time. Choose either proxy configuration or proxy removal. |
| `AZK8S0103` `ProxyCertificatePathNotFound` | The proxy certificate file can't be found. | **Possible cause:** The path is incorrect, relative to a different execution environment, or unreadable by the current identity. Supply a readable absolute path and follow the [outbound proxy guidance](https://learn.microsoft.com/azure/azure-arc/kubernetes/diagnose-connection-issues#connections-with-a-proxy-server). |
| `AZK8S0104` `InvalidLocation` | The requested Azure location isn't supported. | **Possible cause:** The location name is invalid or isn't available for connected clusters. Select a location returned for `Microsoft.Kubernetes/connectedClusters`. |
| `AZK8S0105` `PrivateLinkScopeLocationMismatch` | The connected cluster and Azure Arc Private Link Scope locations differ. | **Possible cause:** The selected Private Link Scope was created in a different Azure location. Use matching locations as required by [Azure Arc Private Link](https://learn.microsoft.com/azure/azure-arc/kubernetes/private-link). |
| `AZK8S0106` `InvalidGatewayArmId` | The gateway resource ID is invalid or identifies the wrong resource type. | **Possible cause:** The ID is malformed, the resource doesn't exist, or it isn't a `Microsoft.HybridCompute/gateways` resource. Supply an existing `Microsoft.HybridCompute/gateways` resource ID. |
| `AZK8S0107` `ProxyBypassStateInvalid` | The saved proxy-bypass state doesn't match the Helm configuration. | **Possible cause:** Proxy bypass values were changed outside the CLI or the saved state is unreadable. Contact support with sanitized Helm values. |

### Kubernetes access

Start with the cluster administrator or Kubernetes provider for these errors.
Use the same kubeconfig and context as the failing command.

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0200` `KubeconfigLoadFailed` | The kubeconfig couldn't be opened or parsed. | **Possible cause:** The path, YAML, selected context, or a referenced credential file is missing or invalid. Confirm the lookup path and context in the [Kubernetes access prerequisites](troubleshooting-prerequisites.md#kubernetes-access), or restore the provider-issued kubeconfig. |
| `AZK8S0201` `ConfigMapReadFailed` | Azure CLI couldn't read a ConfigMap required by the current workflow. | **Possible cause:** The ConfigMap is absent, the identity lacks read access, or the Kubernetes API request failed. Use the name and namespace in the detailed error and verify the identity can read it: `kubectl --kubeconfig "<path>" --context "<context>" auth can-i get configmap/<name> -n <namespace>`. |
| `AZK8S0202` `KubernetesConnectivityFailed` | The Kubernetes `/version` request failed. | **Possible cause:** Authentication, TLS, DNS, routing, firewall, VPN, or API-server health prevented the request. Restore the provider-approved Kubernetes API access path. |
| `AZK8S0203` `KubernetesDistributionDetectionFailed` | Azure CLI couldn't identify the Kubernetes distribution from node data. Connect continues with the generic distribution. | **Possible cause:** Node-list access failed or the returned node metadata didn't identify a supported distribution. If onboarding otherwise succeeds, no action is required. If distribution-specific behavior is needed, restore node-list access or pass the supported `--distribution` value. |
| `AZK8S0204` `KubernetesNamespaceGetFailed` | The `azure-arc` namespace couldn't be read. | **Possible cause:** The namespace is absent, access is denied, or the Kubernetes API request failed. Restore namespace read access. |
| `AZK8S0205` `LinuxNodeNotFound` | Azure CLI found no Linux node and reports a warning; Arc agents still require Linux scheduling capacity. | **Possible cause:** The cluster has no Linux node available for Arc agent scheduling. Provide Linux scheduling capacity that meets the [system requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/system-requirements). |
| `AZK8S0206` `ClusterRoleBindingCreateForbidden` | The identity can't create ClusterRoleBindings. | **Possible cause:** Kubernetes RBAC denies the required cluster-scoped operation. Use the approved onboarding identity or grant the required operation. |
| `AZK8S0207` `KubernetesConfigurationLoadFailed` | Cluster Connect couldn't load the local kubeconfig used for credential merge. | **Possible cause:** The merge target is missing, invalid, unreadable, or unwritable. Restore a valid, readable, and writable merge target. |
| `AZK8S0208` `KubernetesPrivateKeyInjectionFailed` | The onboarding namespace or private-key Secret couldn't be created or replaced. | **Possible cause:** Kubernetes RBAC, admission policy, or conflicting namespace or Secret state blocked the write. Restore the named namespace or Secret permission. |
| `AZK8S0209` `ConfigMapWriteFailed` | A required ConfigMap couldn't be created or updated. | **Possible cause:** Kubernetes RBAC, admission policy, or conflicting ConfigMap state blocked the write. Restore the named ConfigMap write permission. |

### Network and connectivity

Use the detailed endpoint from the error with the
[Azure Arc network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements).
Use [Diagnose connection issues](https://learn.microsoft.com/azure/azure-arc/kubernetes/diagnose-connection-issues)
for the supported DNS and outbound-connectivity diagnostic workflow.
Work with the cluster or network administrator for DNS, firewall, proxy, and
routing changes.

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0300` `DataPlaneHealthCheckFailed` | The authenticated Arc data-plane health request failed. | **Possible cause:** DNS, proxy, TLS, routing, authentication, authorization, throttling, or service health blocked the request. Follow the detailed status; escalate persistent authenticated `429` or `5xx` responses. |
| `AZK8S0301` `DnsNxDomain` | Cluster DNS returned `NXDOMAIN`. | **Possible cause:** The hostname, forwarding rule, or private DNS configuration is incorrect. Correct the hostname, forwarding, or private DNS configuration. |
| `AZK8S0302` `DnsTimeout` | Cluster DNS repeatedly timed out. | **Possible cause:** A resolver is unavailable or DNS traffic is blocked. Restore resolver availability and DNS network access. |
| `AZK8S0303` `DnsServerFailure` | Cluster DNS returned `SERVFAIL`. | **Possible cause:** The resolver couldn't complete the query through its upstream path. Correct the resolver's upstream or forwarding configuration. |
| `AZK8S0304` `DnsNoServersReachable` | No configured resolver was reachable. | **Possible cause:** Pod-to-resolver routing, network policy, or firewall rules block DNS. Restore pod-to-resolver connectivity. |
| `AZK8S0305` `DnsCommunicationsError` | Communication with the resolver was interrupted. | **Possible cause:** The resolver or network path reset or interrupted the query. Correct the cluster DNS or network path. |
| `AZK8S0306` `OnboardingOutboundConnectivityFailed` | A required endpoint returned no HTTP response. | **Possible cause:** DNS, routing, firewall, outbound proxy, or TLS prevented an HTTP response. Allow the required endpoint and port. |
| `AZK8S0307` `ClusterConnectOutboundConnectivityFailed` | The Cluster Connect endpoint returned no HTTP response. | **Possible cause:** Cluster Connect websocket or Service Bus access is blocked. Apply the [Cluster Connect network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements). |
| `AZK8S0308` `OutboundEndpointNonSuccessResponse` | An endpoint returned HTTP `4xx` or `5xx`; network reachability was established. | **Possible cause:** The endpoint rejected or couldn't complete the operation after the network request arrived. Troubleshoot the operation-level status. Don't change networking for this code alone. |
| `AZK8S0309` `CertificatePulldownFailed` | Arc identity certificate synchronization failed. | **Possible cause:** Arc agents aren't healthy or the required certificate Secret wasn't synchronized. Use [Azure Arc platform troubleshooting](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting) and contact support if agent health doesn't identify the cause. |

### Azure resources, Helm, and agents

Work with an Azure resource administrator for account scope, RBAC, provider
registration, and connected-cluster state. Work with a cluster operator for
Helm, scheduling, image pulls, and Arc agent health. Use
[Azure Arc platform troubleshooting](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting).

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0400` `ConnectedClusterCreateFailed` | Azure couldn't create the connected-cluster resource. | **Possible cause:** The ARM request failed because of authorization, policy, invalid state, conflict, throttling, or service health. Resolve the detailed ARM status with the Azure resource administrator. |
| `AZK8S0401` `ConnectedClusterUpdateFailed` | Azure couldn't read or update the resource. | **Possible cause:** The ARM request failed for a reason other than a recognized missing resource. Resolve the detailed ARM status. |
| `AZK8S0402` `ConnectedClusterDeleteFailed` | Azure couldn't read or delete the resource. | **Possible cause:** The ARM request failed for a reason other than a recognized already-absent resource. Resolve the detailed ARM status. |
| `AZK8S0403` `ClusterAlreadyOnboarded` | The Kubernetes cluster is registered to a different Azure resource identity. | **Possible cause:** The Arc release metadata points to another subscription, resource group, or connected-cluster name. Use the existing registration or the kubeconfig for the intended cluster. |
| `AZK8S0404` `ConnectedClusterResourceAlreadyExists` | The requested Azure name belongs to another connected cluster. | **Possible cause:** A connected-cluster resource with the same name already represents a different Kubernetes cluster. Select the intended existing resource or a unique name. |
| `AZK8S0405` `ConnectedClusterResourceNotFound` | The connected-cluster Azure resource requested by `update` or `delete` wasn't found. | **Possible cause:** The selected subscription, resource group, or cluster name is incorrect, or the resource was already deleted. Correct the subscription, resource group, and name. If a delete target was already removed, no Azure resource remains to delete. |
| `AZK8S0406` `InvalidDeleteRequest` | The kubeconfig registration doesn't match the requested Azure resource. | **Possible cause:** The delete command targets a different subscription, resource group, or name than the Arc release metadata. Use matching cluster and Azure identities. |
| `AZK8S0407` `ResourceProviderFetchFailed` | Azure couldn't return resource-provider information. | **Possible cause:** Account scope, authorization, proxy access, or Azure service health blocked the provider query. Verify account scope, authorization, proxy access, and Azure service health. |
| `AZK8S0408` `ConnectedClusterProviderNotRegistered` | `Microsoft.Kubernetes` isn't registered. | **Possible cause:** The subscription hasn't completed connected-cluster provider registration. Ask the subscription administrator to register the provider. |
| `AZK8S0409` `ConnectedClusterResourceIdMissing` | Azure returned an incomplete connected-cluster identity. | **Possible cause:** The service response omitted the resource ID required by the extension. Retry once, then contact support if the resource remains incomplete. |
| `AZK8S0500` `HelmReleaseInstallFailed` | The Arc Helm release couldn't be installed or upgraded. | **Possible cause:** Helm or Kubernetes reported a chart, admission, scheduling, image, timeout, or cluster-access failure. Use the Helm error and Kubernetes events to resolve the underlying cluster cause. |
| `AZK8S0501` `HelmReleaseDeleteFailed` | The Arc Helm release couldn't be removed. | **Possible cause:** Helm or Kubernetes rejected or couldn't complete release deletion. Resolve the Helm error through the supported delete workflow. |
| `AZK8S0502` `HelmChartPullFailed` | The Arc chart couldn't be pulled. | **Possible cause:** Registry DNS, TLS, proxy, authentication, or network access failed. Restore registry access. |
| `AZK8S0503` `HelmChartExportFailed` | The expected exported chart wasn't created. | **Possible cause:** Local storage, file permissions, archive handling, or endpoint security blocked export. Verify local storage and endpoint-security policy, then retry once. |
| `AZK8S0504` `HelmRepositoryAddFailed` | Helm couldn't add the configured repository. | **Possible cause:** The repository name or URL is invalid, unreachable, or rejected. Correct the repository configuration and access path. |
| `AZK8S0505` `HelmReleaseListFailed` | Helm couldn't query release metadata. | **Possible cause:** Cluster access, Helm permissions, or release metadata retrieval failed. Restore cluster access and Helm permissions. |
| `AZK8S0506` `AgentStateTimeout` | Azure didn't report a terminal agent state before timeout. | **Possible cause:** Arc agents remained unhealthy, disconnected, or in a nonterminal service state. Check Arc agent health, then contact support if the agents are healthy. |
| `AZK8S0507` `KeyPairGenerationFailed` | Local key generation failed. | **Possible cause:** The supported cryptography operation failed in the local process. Retry once on a supported platform; contact support if it repeats. |
| `AZK8S0508` `ReleaseNamespaceNotFound` | The Arc Helm release namespace wasn't found. | **Possible cause:** The wrong cluster is selected, the release is absent, or release metadata is inconsistent. Confirm the intended cluster and use the supported recovery path from platform troubleshooting. |
| `AZK8S0509` `HelmValuesGetFailed` | Helm couldn't read the current release values. | **Possible cause:** Cluster access, Helm permissions, or release state prevented the query. Restore Helm release access. |
| `AZK8S0510` `HelmNotInstalled` | A required local Helm client wasn't found. | **Possible cause:** Helm isn't installed or isn't available on `PATH` in an environment that requires it. Install the supported Helm version for the environment. |
| `AZK8S0511` `HelmVersionTooOld` | The Helm major version is below 3. | **Possible cause:** The selected Helm executable is an unsupported older version. Upgrade to Helm 3 or later. |
| `AZK8S0512` `HelmTimeoutPendingOrUnschedulable` | Workloads couldn't schedule before timeout. | **Possible cause:** Kubernetes events report capacity, placement, taint, affinity, quota, or admission constraints. Resolve the Kubernetes scheduling events. |
| `AZK8S0513` `HelmTimeoutImagePullFailed` | Workloads couldn't pull images before timeout. | **Possible cause:** Registry DNS, network, authentication, policy, or image availability blocked a pull. Resolve the image-pull events using the network requirements and registry policy. |
| `AZK8S0514` `HelmTimeout` | Helm timed out without a more specific classification. | **Possible cause:** A cluster or release condition prevented completion but emitted no recognized higher-priority signal. Use Helm status, pod status, and Kubernetes events to identify the underlying cause. |
| `AZK8S0515` `HelmClientError` | The operating system couldn't start Helm. | **Possible cause:** The executable path, local permission, architecture, or endpoint-security policy blocked process creation. Correct the executable path, permission, or endpoint-security policy. |

### Pre-onboarding diagnostics

Run `az connectedk8s troubleshoot` and keep any specific `AZK8S0300`-series
result with the aggregate code.

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0600` `PrediagnosticsFailed` | The diagnostic workflow failed unexpectedly. | **Possible cause:** An unclassified exception interrupted the workflow after any specific findings were retained. Follow the detailed error and any accompanying specific code. |
| `AZK8S0601` `PrediagnosticsJobExecutionFailed` | The diagnostic Job workflow was interrupted. | **Possible cause:** Kubernetes API, Job watch, pod lookup, or cleanup failed unexpectedly. Use the Kubernetes error or event to resolve access, scheduling, or API health. |
| `AZK8S0602` `PostDiagnosticPrecheckFailed` | At least one required check failed. | **Possible cause:** DNS, outbound connectivity, identity connectivity, or resource consistency checks reported failure. Fix each specific failed check before retrying onboarding. |
| `AZK8S0603` `PrediagnosticsIncomplete` | The diagnostic result wasn't conclusive. | **Possible cause:** The Job wasn't scheduled, didn't finish, or didn't produce a required result. Resolve the accompanying Job, scheduling, or log-access result. |
| `AZK8S0604` `PrediagnosticsJobNotScheduled` | The diagnostic Job wasn't observed. | **Possible cause:** Scheduling, quota, admission policy, or API observation prevented the Job from appearing. Resolve scheduling or admission-policy events. |
| `AZK8S0605` `PrediagnosticsJobNotComplete` | The diagnostic Job didn't complete in time. | **Possible cause:** Its pod remained pending, failed repeatedly, or couldn't finish before the watch ended. Resolve the Job and pod events. |
| `AZK8S0606` `PrediagnosticsLogSaveFailed` | A local copy of diagnostic logs couldn't be saved. | **Possible cause:** Local storage, file permission, or conversion failed after result collection. Correct local storage or file permissions; retain the diagnostic result separately. |
| `AZK8S0607` `PrediagnosticsHelmInstallFailed` | The temporary diagnostic Helm release couldn't be installed. | **Possible cause:** Helm, cluster access, admission, scheduling, image pull, or timeout blocked installation. Resolve the detailed Helm and Kubernetes error. |

### Custom Locations and Cluster Connect

For Custom Locations behavior, permissions, and recovery, use the
[Custom Locations documentation](https://learn.microsoft.com/azure/azure-arc/kubernetes/custom-locations).

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0700` `CustomLocationsEnableFailed` | Custom Locations couldn't be enabled. | **Possible cause:** A Custom Locations prerequisite failed and no other requested feature could continue. Follow the Custom Locations documentation and the detailed error. |
| `AZK8S0701` `CustomLocationsOidFetchFailed` | The tenant-specific service-principal object ID couldn't be obtained. | **Possible cause:** The service principal is absent, Graph access failed, or the identity can't read it. Use the documented administrator-provided object-ID workflow. |
| `AZK8S0702` `CustomLocationsRegistrationCheckFailed` | A prerequisite or provider-registration check failed. | **Possible cause:** Account scope, authorization, Graph access, or `Microsoft.ExtendedLocation` registration lookup failed. Verify account scope, authorization, and `Microsoft.ExtendedLocation` registration. |

The following codes apply to the local Cluster Connect client proxy started by
`az connectedk8s proxy`, not the outbound HTTP or HTTPS proxy configured for
Arc onboarding. Follow [Cluster Connect setup and authentication](https://learn.microsoft.com/azure/azure-arc/kubernetes/cluster-connect),
[Cluster Connect troubleshooting](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting#cluster-connect-problems),
and the [`az connectedk8s proxy` reference](https://learn.microsoft.com/cli/azure/connectedk8s#az-connectedk8s-proxy).

| Code | Description | Possible cause |
| --- | --- | --- |
| `AZK8S0800` `ClientProxyDownloadFailed` | The local client proxy couldn't be prepared. | **Possible cause:** MCR access, local storage, archive extraction, architecture selection, file permission, or endpoint security blocked preparation. Verify the documented prerequisites, local storage, MCR access, and endpoint-security policy. |
| `AZK8S0801` `ClientProxyPortInUse` | A required local port is occupied. | **Possible cause:** Another process or proxy session is using one of the required local ports. Stop that process or select another supported `--port`. |
| `AZK8S0802` `ClientProxyStartFailed` | The operating system couldn't start the proxy. | **Possible cause:** Local execution permission, architecture, process policy, or endpoint security blocked creation. Correct local execution permission or endpoint-security policy. |
| `AZK8S0803` `ClientProxyConfigCreateFailed` | The local proxy configuration couldn't be replaced. | **Possible cause:** Local storage, file permission, file locking, or endpoint security blocked the write. Correct local storage or file permissions; don't share the configuration. |
| `AZK8S0804` `ClientProxyClosed` | The proxy started and then exited. | **Possible cause:** The local process encountered a runtime, capacity, configuration, network, credential, or endpoint-security failure. Use sanitized `--debug` output and local process-security events, then follow Cluster Connect troubleshooting. |
| `AZK8S0805` `ClusterCredentialsGetFailed` | Cluster Connect credentials couldn't be retrieved. | **Possible cause:** Authentication, Azure RBAC, disconnected agents, disabled Cluster Connect, or service health blocked retrieval. Verify authentication, the documented Azure roles, connected state, and feature enablement. |

## Contact support

If the linked guidance doesn't resolve the problem, provide Azure support:

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
