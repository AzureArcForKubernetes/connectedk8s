# Troubleshoot Azure Arc-enabled Kubernetes error codes

Use this reference when an `az connectedk8s` command reports an error in the
`AZK8Snnnn` format. Find the code in the tables below, follow the resolution,
and retry the original command.

The code identifies the operation or failure category. The detailed text after
the code identifies the specific resource, endpoint, or underlying failure.
Use that detailed text to decide which resolution step applies.

The error catalog is introduced incrementally. Some codes are reserved for
call sites that have not yet migrated to standardized errors. DNS and outbound
connectivity codes, and diagnostic log-save failures, can also appear as
non-fatal diagnostic results. A non-fatal result needs action only when the
related check or command also fails.

## Find your error

Use your browser's page search to find the complete `AZK8Snnnn` code, or select
its category:

| Code range | Category |
| --- | --- |
| `AZK8S0000`-`AZK8S0099` | [General and internal errors](#general-and-internal-errors) |
| `AZK8S0100`-`AZK8S0199` | [Configuration and input errors](#configuration-and-input-errors) |
| `AZK8S0200`-`AZK8S0299` | [Kubeconfig and cluster access errors](#kubeconfig-and-cluster-access-errors) |
| `AZK8S0300`-`AZK8S0399` | [Network and connectivity errors](#network-and-connectivity-errors) |
| `AZK8S0400`-`AZK8S0499` | [Azure resource operation errors](#azure-resource-operation-errors) |
| `AZK8S0500`-`AZK8S0599` | [Helm and agent lifecycle errors](#helm-and-agent-lifecycle-errors) |
| `AZK8S0600`-`AZK8S0699` | [Pre-onboarding diagnostic errors](#pre-onboarding-diagnostic-errors) |
| `AZK8S0700`-`AZK8S0799` | [Feature errors](#feature-errors) |
| `AZK8S0800`-`AZK8S0899` | [Client proxy errors](#client-proxy-errors) |

Detailed procedures are available for these common errors:

- [`AZK8S0104`: `InvalidLocation`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0104-invalidlocation)
- [`AZK8S0200`: `KubeconfigLoadFailed`](troubleshoot-cluster-access-networking.md#azk8s0200-kubeconfigloadfailed)
- [`AZK8S0202`: `KubernetesConnectivityFailed`](troubleshoot-cluster-access-networking.md#azk8s0202-kubernetesconnectivityfailed)
- [`AZK8S0203`: `KubernetesDistributionDetectionFailed`](troubleshoot-cluster-access-networking.md#azk8s0203-kubernetesdistributiondetectionfailed)
- [`AZK8S0204`: `KubernetesNamespaceGetFailed`](troubleshoot-cluster-access-networking.md#azk8s0204-kubernetesnamespacegetfailed)
- [`AZK8S0205`: `LinuxNodeNotFound`](troubleshoot-cluster-access-networking.md#azk8s0205-linuxnodenotfound)
- [`AZK8S0206`: `ClusterRoleBindingCreateForbidden`](troubleshoot-cluster-access-networking.md#azk8s0206-clusterrolebindingcreateforbidden)
- [`AZK8S0207`: `KubernetesConfigurationLoadFailed`](troubleshoot-cluster-access-networking.md#azk8s0207-kubernetesconfigurationloadfailed)
- [`AZK8S0208`: `KubernetesPrivateKeyInjectionFailed`](troubleshoot-cluster-access-networking.md#azk8s0208-kubernetesprivatekeyinjectionfailed)
- [`AZK8S0209`: `ConfigMapWriteFailed`](troubleshoot-cluster-access-networking.md#azk8s0209-configmapwritefailed)
- [`AZK8S0300`: `DataPlaneHealthCheckFailed`](troubleshoot-cluster-access-networking.md#azk8s0300-dataplanehealthcheckfailed)
- [`AZK8S0301`: `DnsNxDomain`](troubleshoot-cluster-access-networking.md#azk8s0301-dnsnxdomain)
- [`AZK8S0302`: `DnsTimeout`](troubleshoot-cluster-access-networking.md#azk8s0302-dnstimeout)
- [`AZK8S0303`: `DnsServerFailure`](troubleshoot-cluster-access-networking.md#azk8s0303-dnsserverfailure)
- [`AZK8S0304`: `DnsNoServersReachable`](troubleshoot-cluster-access-networking.md#azk8s0304-dnsnoserversreachable)
- [`AZK8S0305`: `DnsCommunicationsError`](troubleshoot-cluster-access-networking.md#azk8s0305-dnscommunicationserror)
- [`AZK8S0306`: `OnboardingOutboundConnectivityFailed`](troubleshoot-cluster-access-networking.md#azk8s0306-onboardingoutboundconnectivityfailed)
- [`AZK8S0307`: `ClusterConnectOutboundConnectivityFailed`](troubleshoot-cluster-access-networking.md#azk8s0307-clusterconnectoutboundconnectivityfailed)
- [`AZK8S0308`: `OutboundEndpointNonSuccessResponse`](troubleshoot-cluster-access-networking.md#azk8s0308-outboundendpointnonsuccessresponse)
- [`AZK8S0309`: `CertificatePulldownFailed`](troubleshoot-cluster-access-networking.md#azk8s0309-certificatepulldownfailed)
- [`AZK8S0400`: `ConnectedClusterCreateFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0400-connectedclustercreatefailed)
- [`AZK8S0401`: `ConnectedClusterUpdateFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0401-connectedclusterupdatefailed)
- [`AZK8S0402`: `ConnectedClusterDeleteFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0402-connectedclusterdeletefailed)
- [`AZK8S0403`: `ClusterAlreadyOnboarded`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0403-clusteralreadyonboarded)
- [`AZK8S0404`: `ConnectedClusterResourceAlreadyExists`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0404-connectedclusterresourcealreadyexists)
- [`AZK8S0405`: `ConnectedClusterResourceNotFound`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0405-connectedclusterresourcenotfound)
- [`AZK8S0406`: `InvalidDeleteRequest`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0406-invaliddeleterequest)
- [`AZK8S0407`: `ResourceProviderFetchFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0407-resourceproviderfetchfailed)
- [`AZK8S0408`: `ConnectedClusterProviderNotRegistered`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0408-connectedclusterprovidernotregistered)
- [`AZK8S0409`: `ConnectedClusterResourceIdMissing`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0409-connectedclusterresourceidmissing)
- [`AZK8S0500`: `HelmReleaseInstallFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0500-helmreleaseinstallfailed)
- [`AZK8S0501`: `HelmReleaseDeleteFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0501-helmreleasedeletefailed)
- [`AZK8S0502`: `HelmChartPullFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0502-helmchartpullfailed)
- [`AZK8S0503`: `HelmChartExportFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0503-helmchartexportfailed)
- [`AZK8S0504`: `HelmRepositoryAddFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0504-helmrepositoryaddfailed)
- [`AZK8S0505`: `HelmReleaseListFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0505-helmreleaselistfailed)
- [`AZK8S0506`: `AgentStateTimeout`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0506-agentstatetimeout)
- [`AZK8S0507`: `KeyPairGenerationFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0507-keypairgenerationfailed)
- [`AZK8S0508`: `ReleaseNamespaceNotFound`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0508-releasenamespacenotfound)
- [`AZK8S0509`: `HelmValuesGetFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0509-helmvaluesgetfailed)
- [`AZK8S0510`: `HelmNotInstalled`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0510-helmnotinstalled)
- [`AZK8S0511`: `HelmVersionTooOld`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0511-helmversiontooold)
- [`AZK8S0512`: `HelmTimeoutPendingOrUnschedulable`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0512-helmtimeoutpendingorunschedulable)
- [`AZK8S0513`: `HelmTimeoutImagePullFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0513-helmtimeoutimagepullfailed)
- [`AZK8S0514`: `HelmTimeout`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0514-helmtimeout)
- [`AZK8S0515`: `HelmClientError`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0515-helmclienterror)
- [`AZK8S0600`: `PrediagnosticsFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0600-prediagnosticsfailed)
- [`AZK8S0601`: `PrediagnosticsJobExecutionFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0601-prediagnosticsjobexecutionfailed)
- [`AZK8S0602`: `PostDiagnosticPrecheckFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0602-postdiagnosticprecheckfailed)
- [`AZK8S0603`: `PrediagnosticsIncomplete`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0603-prediagnosticsincomplete)
- [`AZK8S0604`: `PrediagnosticsJobNotScheduled`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0604-prediagnosticsjobnotscheduled)
- [`AZK8S0605`: `PrediagnosticsJobNotComplete`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0605-prediagnosticsjobnotcomplete)
- [`AZK8S0606`: `PrediagnosticsLogSaveFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0606-prediagnosticslogsavefailed)
- [`AZK8S0607`: `PrediagnosticsHelmInstallFailed`](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0607-prediagnosticshelminstallfailed)
- [`AZK8S0700`: `CustomLocationsEnableFailed`](troubleshoot-features-cluster-connect.md#azk8s0700-customlocationsenablefailed)
- [`AZK8S0701`: `CustomLocationsOidFetchFailed`](troubleshoot-features-cluster-connect.md#azk8s0701-customlocationsoidfetchfailed)
- [`AZK8S0702`: `CustomLocationsRegistrationCheckFailed`](troubleshoot-features-cluster-connect.md#azk8s0702-customlocationsregistrationcheckfailed)
- [`AZK8S0800`: `ClientProxyDownloadFailed`](troubleshoot-features-cluster-connect.md#azk8s0800-clientproxydownloadfailed)
- [`AZK8S0801`: `ClientProxyPortInUse`](troubleshoot-features-cluster-connect.md#azk8s0801-clientproxyportinuse)
- [`AZK8S0802`: `ClientProxyStartFailed`](troubleshoot-features-cluster-connect.md#azk8s0802-clientproxystartfailed)
- [`AZK8S0803`: `ClientProxyConfigCreateFailed`](troubleshoot-features-cluster-connect.md#azk8s0803-clientproxyconfigcreatefailed)
- [`AZK8S0804`: `ClientProxyClosed`](troubleshoot-features-cluster-connect.md#azk8s0804-clientproxyclosed)
- [`AZK8S0805`: `ClusterCredentialsGetFailed`](troubleshoot-features-cluster-connect.md#azk8s0805-clustercredentialsgetfailed)

## Troubleshooting guides

- [Troubleshoot cluster access and networking](troubleshoot-cluster-access-networking.md)
  covers kubeconfig, Kubernetes API access, DNS, and data-plane connectivity.
- [Troubleshoot Azure resources, Helm, and diagnostics](troubleshoot-azure-resources-helm-diagnostics.md)
  covers Azure resource operations, Arc agents, Helm, and pre-onboarding diagnostics.
- [Troubleshoot features and Cluster Connect](troubleshoot-features-cluster-connect.md)
  covers Custom Locations, Cluster Connect credentials, and the client proxy.

## General and internal errors

| Code and name | What it means | How to resolve |
| --- | --- | --- |
| `AZK8S0001` `UnexpectedError` | The extension encountered an unclassified error. In version 1.11.5, `az connectedk8s show` also uses this code when Azure returns `ResourceNotFound`. | If the detailed error is `ResourceNotFound`, follow `AZK8S0405`. Otherwise, record the installed versions with `az version`, then run `az upgrade` and `az extension update --name connectedk8s`. Retry the original command once. If the error repeats, rerun that command with `--debug`, remove credentials, tokens, certificates, private keys, proxy details, and customer identifiers from the output, and contact support with the sanitized error and versions. |
| `AZK8S0002` `UnsupportedOperatingSystem` | The command is running on a host operating system other than Windows, Linux, or macOS. In version 1.11.5, current command paths display an unnumbered error; the client-proxy path records this classification in telemetry, while Helm installation uses a separate legacy fault type. The code is reserved for their migration to standardized console errors. | On Linux or macOS, run `uname -srm`; the first value must be `Linux` or `Darwin`. On Windows PowerShell, run `[System.Environment]::OSVersion.VersionString`; the result must identify Windows. The remaining values describe the kernel and processor architecture and don't determine this error. Run the latest Azure CLI and `connectedk8s` extension on a supported OS. See [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) for supported installation options and OS-version details. |
| `AZK8S0003` `UnsupportedProvisionedClusterOperation` | The requested `az connectedk8s` operation isn't available for an AKS Arc provisioned cluster. Current command paths record this classification in telemetry but display an unnumbered error; the code is reserved for their migration to standardized console errors. | Run `az connectedk8s show -g "<resource-group>" -n "<cluster-name>" --query kind -o tsv`; this error applies when the result is `ProvisionedCluster`. Use the `az aksarc` command named in the detailed error for lifecycle operations: `update`, `delete`, or `upgrade`. Run `az aksarc <command> --help` before retrying. Manage supported features through cluster extensions as directed by the detailed error. Connecting an existing cluster with `az connectedk8s connect` doesn't convert it into an AKS Arc provisioned cluster. |

## Configuration and input errors

| Code and name | What it means | How to resolve |
| --- | --- | --- |
| `AZK8S0100` `InvalidArgumentValue` | One or more command arguments are invalid. | Read the detailed message, run `az connectedk8s <command> --help`, and correct the named value or format. |
| `AZK8S0101` `UpdateNoParameters` | `az connectedk8s update` was called without a setting to change. | Supply at least one supported update option. Use `az connectedk8s update --help` to list the options. |
| `AZK8S0102` `UpdateProxyParameterConflict` | `az connectedk8s update` was given proxy settings and `--disable-proxy` in the same command. | To update the proxy settings, rerun without `--disable-proxy`, for example: `az connectedk8s update -g "<resource-group>" -n "<cluster-name>" --proxy-https "<https-proxy-url>" --proxy-http "<http-proxy-url>" --proxy-skip-range "<host-or-cidr>,<additional-host-or-cidr>"`. Add `--proxy-cert "<certificate-path>"` only when required. To disable all proxy settings, run `az connectedk8s update -g "<resource-group>" -n "<cluster-name>" --disable-proxy` without proxy or bypass options. |
| `AZK8S0103` `ProxyCertificatePathNotFound` | The proxy certificate file cannot be found. | On Windows run `Test-Path -LiteralPath "<certificate-path>" -PathType Leaf`; expect `True`. On Linux or macOS run `test -f "<certificate-path>" && test -r "<certificate-path>"; echo $?`; expect exit code `0`. Retry with the absolute path if the check fails. |
| `AZK8S0104` `InvalidLocation` | The Azure location is not in the current `Microsoft.Kubernetes/connectedClusters` supported-location list. | Follow the [location steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0104-invalidlocation) and retry with the canonical name of a supported region. |
| `AZK8S0105` `PrivateLinkScopeLocationMismatch` | The Azure Arc Private Link Scope and the requested connected cluster are in different locations. | Run `az resource show --ids "<private-link-scope-id>" --query "{type:type,location:location}" -o yaml`; `type` must be `Microsoft.HybridCompute/privateLinkScopes`. Compare the returned location with the `--location` value passed to `az connectedk8s connect`. Retry with a matching supported location or an approved scope in the requested region. **Fixed when:** the two locations match case-insensitively and the retry no longer reports `AZK8S0105`; later independent onboarding checks can still fail. |
| `AZK8S0106` `InvalidGatewayArmId` | The gateway resource ID is malformed or does not identify a `Microsoft.HybridCompute/gateways` resource. | Run `az resource show --ids "<gateway-resource-id>" --query "{id:id,type:type}" -o yaml`. An invalid-ID or `ResourceNotFound` response means you need the ARM ID of an existing Azure Arc gateway. Otherwise, `type` must be `Microsoft.HybridCompute/gateways`; pass the returned `id` unchanged to `--gateway-resource-id`. **Fixed when:** the retry no longer reports `AZK8S0106`; later independent onboarding checks can still fail. |
| `AZK8S0107` `ProxyBypassStateInvalid` | The saved Arc proxy-bypass ownership record is unreadable or does not match the current `global.noProxy` Helm value. This can happen when Helm values are changed outside the CLI. The command stops before changing proxy or Helm settings. | Do not guess which `global.noProxy` entries the CLI owns. Run `kubectl get configmap azure-clusterconfig -n azure-arc -o jsonpath="{.data.AZURE_ARC_HELM_NAMESPACE}{'\n'}"` to read the Helm release namespace without displaying other ConfigMap data. Collect `helm get values azure-arc --namespace "<release-namespace>"`. Before sharing the output outside a secure support channel, replace credentials, proxy URLs, internal hostnames and IP addresses, certificate data, and Azure resource identifiers with descriptive placeholders. Keep the field names, structure, and number and order of `noProxy` entries intact so support can reconcile `connectedk8sCli.arcProxyBypass` with `global.noProxy`. |

### List supported regions

To list the regions that support Azure Arc-enabled Kubernetes connected
clusters, run:

```azurecli
az provider show --namespace Microsoft.Kubernetes --query "resourceTypes[?resourceType=='connectedClusters'].locations | [0][]" --output table
```

## Kubeconfig and cluster access errors

| Code and name | What it means | How to resolve |
| --- | --- | --- |
| `AZK8S0200` `KubeconfigLoadFailed` | Azure CLI could not open the kubeconfig or interpret its YAML, referenced files, or contexts. | Follow the [kubeconfig loading steps](troubleshoot-cluster-access-networking.md#azk8s0200-kubeconfigloadfailed). Run `kubectl --kubeconfig "<path>" config get-contexts` and `kubectl --kubeconfig "<path>" config current-context`; both must succeed and identify the intended context. If they succeed but the `/version` request fails, kubeconfig loading is fixed; continue with `AZK8S0202` to troubleshoot API connectivity. **Fixed when:** Azure CLI loads the same file and selects the intended context without `AZK8S0200`. |
| `AZK8S0201` `ConfigMapReadFailed` | A required Kubernetes ConfigMap could not be read. | Use the name and namespace from the detailed error and the same kubeconfig and context as the failing command. Reuse its `--kube-config` and `--kube-context` values when supplied. Otherwise, check `KUBECONFIG`; if it is unset, the default path is `$HOME/.kube/config` on Linux or macOS and `%USERPROFILE%\.kube\config` on Windows. Run `kubectl --kubeconfig "<path>" config current-context` to find the selected context. Then run `kubectl --kubeconfig "<path>" --context "<context>" auth can-i get configmap/"<name>" -n "<namespace>"` and `kubectl --kubeconfig "<path>" --context "<context>" get configmap "<name>" -n "<namespace>" -o name`; expect `yes` and `configmap/<name>`. Use `-o name` because only existence and read access are needed. If you inspect the ConfigMap data, don't share it without removing customer-specific values. **Fixed when:** both checks succeed and the original command reads the ConfigMap. |
| `AZK8S0202` `KubernetesConnectivityFailed` | The Kubernetes `/version` request failed. | Follow the [Kubernetes connectivity steps](troubleshoot-cluster-access-networking.md#azk8s0202-kubernetesconnectivityfailed) for authentication, TLS, DNS, routing, firewall, VPN, and API health. **Fixed when:** `/version` returns `gitVersion` with the same kubeconfig and context. |
| `AZK8S0203` `KubernetesDistributionDetectionFailed` | The extension received the node list but couldn't parse the node fields used to identify the Kubernetes distribution. In version 1.11.5, this is a non-fatal warning: `connect` falls back to `generic` and continues. | Follow the [distribution-detection steps](troubleshoot-cluster-access-networking.md#azk8s0203-kubernetesdistributiondetectionfailed). If the actual distribution is known and supported, retry `connect` with its explicit `--distribution` value to bypass automatic detection. **Fixed when:** the retry no longer reports `AZK8S0203` and passes distribution detection; a later independent error doesn't invalidate this result. |
| `AZK8S0204` `KubernetesNamespaceGetFailed` | The extension couldn't read or list the `azure-arc` namespace. During `connect`, this is a fatal read failure before Helm ownership metadata and the onboarding Secret are written. During delete cleanup, version 1.11.5 reports it as a warning after namespace lookup has failed for three minutes. | Follow the [namespace-read steps](troubleshoot-cluster-access-networking.md#azk8s0204-kubernetesnamespacegetfailed). Use the same kubeconfig and context as the original command. **Fixed when:** `connect` can read `namespace/azure-arc`, or a delete-state check confirms that the namespace is absent or readable without `AZK8S0204`. A later independent error doesn't invalidate this result. |
| `AZK8S0205` `LinuxNodeNotFound` | `connect` found no Node whose `kubernetes.io/os` label is `linux`. In version 1.11.5 this is a non-fatal warning, but Arc agents require Linux scheduling capacity. | Follow the [Linux-node steps](troubleshoot-cluster-access-networking.md#azk8s0205-linuxnodenotfound). **Fixed when:** the same identity lists at least one usable Linux node and the retry no longer reports `AZK8S0205`. |
| `AZK8S0206` `ClusterRoleBindingCreateForbidden` | The kubeconfig identity failed a SelfSubjectAccessReview for creating cluster-scoped `clusterrolebindings.rbac.authorization.k8s.io`. The review checks permission; it doesn't create a binding. | Follow the [ClusterRoleBinding authorization steps](troubleshoot-cluster-access-networking.md#azk8s0206-clusterrolebindingcreateforbidden). **Fixed when:** the review returns `yes` and `connect` advances beyond the permission check. |
| `AZK8S0207` `KubernetesConfigurationLoadFailed` | The extension couldn't load a local kubeconfig while merging credentials obtained by `az connectedk8s proxy`. This differs from `AZK8S0200`, which applies when a lifecycle command initially loads its input kubeconfig. | Follow the [credential-merge steps](troubleshoot-cluster-access-networking.md#azk8s0207-kubernetesconfigurationloadfailed). **Fixed when:** the merge target is readable and writable, valid kubeconfig YAML and the same proxy command merges the context without `AZK8S0207`. |
| `AZK8S0208` `KubernetesPrivateKeyInjectionFailed` | `connect` couldn't create or adopt `azure-arc`, or couldn't create or replace the `azure-arc-connect-privatekey` Secret. | Follow the [private-key injection steps](troubleshoot-cluster-access-networking.md#azk8s0208-kubernetesprivatekeyinjectionfailed). Check the detailed error to distinguish namespace creation, namespace metadata patching, Secret creation, and Secret replacement. **Fixed when:** the retry passes that exact stage. |
| `AZK8S0209` `ConfigMapWriteFailed` | The extension couldn't create or replace `container-azm-ms-agentconfig` in `kube-system` while changing the Container Insights proxy bypass. The detailed error identifies `create`, `update`, or bypass removal. | Follow the [Container Insights ConfigMap steps](troubleshoot-cluster-access-networking.md#azk8s0209-configmapwritefailed). **Fixed when:** the same add or clear operation completes its ConfigMap write without `AZK8S0209`. |

## Network and connectivity errors

| Code and name | What it means | How to resolve |
| --- | --- | --- |
| `AZK8S0300` `DataPlaneHealthCheckFailed` | Before retrieving Helm metadata, `connect` or `update` couldn't complete its authenticated POST to the regional Arc data-plane health endpoint. Only HTTP `200` passes this check. | Follow the [data-plane health-check steps](troubleshoot-cluster-access-networking.md#azk8s0300-dataplanehealthcheckfailed). **Fixed when:** the original command's health-check POST returns `200` and advances to Helm metadata retrieval. |
| `AZK8S0301` `DnsNxDomain` | The in-cluster diagnostic's latest recognized DNS result for the Kubernetes service ended in `NXDOMAIN`. | Follow the [`NXDOMAIN` steps](troubleshoot-cluster-access-networking.md#azk8s0301-dnsnxdomain). **Fixed when:** the same cluster DNS path returns a valid address for `kubernetes.default` and the diagnostic passes. |
| `AZK8S0302` `DnsTimeout` | The in-cluster diagnostic's latest recognized result ended in a DNS timeout. | Follow the [DNS-timeout steps](troubleshoot-cluster-access-networking.md#azk8s0302-dnstimeout). **Fixed when:** the same lookup returns a valid address without timing out and the diagnostic passes. |
| `AZK8S0303` `DnsServerFailure` | The in-cluster DNS server returned `SERVFAIL`; it received the query but couldn't produce an answer. | Follow the [`SERVFAIL` steps](troubleshoot-cluster-access-networking.md#azk8s0303-dnsserverfailure). **Fixed when:** the same lookup returns a valid address and the diagnostic passes. |
| `AZK8S0304` `DnsNoServersReachable` | The diagnostic couldn't reach any resolver configured for the pod. | Follow the [resolver-reachability steps](troubleshoot-cluster-access-networking.md#azk8s0304-dnsnoserversreachable). **Fixed when:** the pod reaches a configured resolver, resolves `kubernetes.default`, and the diagnostic passes. |
| `AZK8S0305` `DnsCommunicationsError` | Communication with the pod's configured DNS resolver was interrupted. | Follow the [DNS-communications steps](troubleshoot-cluster-access-networking.md#azk8s0305-dnscommunicationserror). **Fixed when:** repeated lookups reliably return a valid address and the diagnostic passes. |
| `AZK8S0306` `OnboardingOutboundConnectivityFailed` | A mandatory onboarding endpoint produced response code `000`, meaning no HTTP response was received. The pre-onboarding connectivity check fails. | Follow the [mandatory-egress steps](troubleshoot-cluster-access-networking.md#azk8s0306-onboardingoutboundconnectivityfailed). **Fixed when:** every mandatory endpoint produces an HTTP response and the pre-onboarding check passes. |
| `AZK8S0307` `ClusterConnectOutboundConnectivityFailed` | The optional Cluster Connect endpoint produced response code `000`. Version 1.11.5 records the diagnostic but lets pre-onboarding pass when mandatory endpoints are reachable. | Follow the [Cluster Connect egress steps](troubleshoot-cluster-access-networking.md#azk8s0307-clusterconnectoutboundconnectivityfailed) when Cluster Connect is required. **Fixed when:** the endpoint produces an HTTP response and `az connectedk8s proxy` can carry Kubernetes traffic. |
| `AZK8S0308` `OutboundEndpointNonSuccessResponse` | An endpoint returned HTTP 4xx or 5xx. This is informational in the connectivity diagnostic because an HTTP response proves DNS, TCP, and TLS reachability far enough to receive a status. | Follow the [non-success response steps](troubleshoot-cluster-access-networking.md#azk8s0308-outboundendpointnonsuccessresponse). No network repair is required for this code alone; troubleshoot a separate operation-level failure by its own status and code. |
| `AZK8S0309` `CertificatePulldownFailed` | After a Helm timeout, read-only pod, warning-event, and Secret-metadata checks identified an Arc identity-certificate synchronization signal. Image-pull and scheduling classifications take precedence over this code. | Follow the [certificate synchronization steps](troubleshoot-cluster-access-networking.md#azk8s0309-certificatepulldownfailed). **Fixed when:** the required certificate Secret metadata exists, the responsible agents are ready, and the supported Helm operation completes. |

See [Azure Arc-enabled Kubernetes network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements)
for the current endpoint and port list.

## Azure resource operation errors

| Code and name | What it means | How to resolve |
| --- | --- | --- |
| `AZK8S0400` `ConnectedClusterCreateFailed` | The `connect` workflow's Azure Resource Manager create-or-replace request failed. Recognized name conflicts are classified as `AZK8S0404` instead. | Follow the [resource-creation steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0400-connectedclustercreatefailed). **Fixed when:** `az connectedk8s show` returns the intended nonempty resource ID and `provisioningState: Succeeded`. |
| `AZK8S0401` `ConnectedClusterUpdateFailed` | An Azure Resource Manager get, patch, or create-or-replace request in `update` failed. A recognized connected-cluster `404` is classified as `AZK8S0405`. | Follow the [resource-update steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0401-connectedclusterupdatefailed). **Fixed when:** the same update succeeds and the resource returns `provisioningState: Succeeded` with the requested property. |
| `AZK8S0402` `ConnectedClusterDeleteFailed` | The Azure Resource Manager get or delete request failed. A recognized connected-cluster `404` is classified as `AZK8S0405`. | Follow the [resource-delete steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0402-connectedclusterdeletefailed). **Fixed when:** the supported delete completes, Azure returns resource not found, and Arc cleanup reaches the expected state. |
| `AZK8S0403` `ClusterAlreadyOnboarded` | The selected Kubernetes cluster has an Arc release whose registration points to an existing Azure resource with different resource-group or resource-name values. | Follow the [existing-registration steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0403-clusteralreadyonboarded). **Fixed when:** `connect` targets that registration or a kubeconfig for the intended different cluster. |
| `AZK8S0404` `ConnectedClusterResourceAlreadyExists` | The requested Azure resource name already identifies another connected cluster, either detected before creation or returned as a recognized ARM `409`. | Follow the [resource-name ownership steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0404-connectedclusterresourcealreadyexists). **Fixed when:** the selected resource identity is unambiguous and `connect` proceeds with the intended cluster. |
| `AZK8S0405` `ConnectedClusterResourceNotFound` | Azure returned `404` for `show`, or a recognized connected-cluster not-found response during update or delete. Version 1.11.5 reports this standardized code directly. | Follow the [resource-not-found steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0405-connectedclusterresourcenotfound). **Fixed when:** `show` or update resolves the intended resource ID; for delete, verify the already-absent Azure side and reconcile any remaining Arc state through a supported path. |
| `AZK8S0406` `InvalidDeleteRequest` | The kubeconfig cluster's saved subscription, resource group, or resource name doesn't match the Azure resource requested for deletion. The command stops before deleting ARM or cluster state. | Follow the [delete-identity steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0406-invaliddeleterequest). **Fixed when:** all three identities match and the supported delete advances past validation. |
| `AZK8S0407` `ResourceProviderFetchFailed` | This standardized definition has no active emitter in version 1.11.5. Provider-fetch failures in current paths are logged or shown as an unnumbered Azure request error; the code is reserved for migration. | Follow the [provider-fetch steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0407-resourceproviderfetchfailed) for the unnumbered failure or a later version that emits this code. **Fixed when:** the provider query succeeds in the intended subscription and the original operation advances. |
| `AZK8S0408` `ConnectedClusterProviderNotRegistered` | The pre-onboarding registration check found `Microsoft.Kubernetes` in a state other than `Registering` or `Registered`. | Follow the [provider-registration steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0408-connectedclusterprovidernotregistered). **Fixed when:** registration reaches `Registered` and `connect` advances past the check. |
| `AZK8S0409` `ConnectedClusterResourceIdMissing` | During `update`, Azure returned the connected cluster object but its `id` property was `None`, so the extension couldn't derive the subscription for subsequent agent work. | Follow the [missing-resource-ID steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0409-connectedclusterresourceidmissing). **Fixed when:** `show` and the same update receive the complete intended resource ID. |

## Helm and agent lifecycle errors

| Code and name | What it means | How to resolve |
| --- | --- | --- |
| `AZK8S0500` `HelmReleaseInstallFailed` | Installing or upgrading the Azure Arc agent Helm release failed. | Follow the [Helm release steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0500-helmreleaseinstallfailed). **Fixed when:** Helm reports `deployed` and required Arc workloads become ready. |
| `AZK8S0501` `HelmReleaseDeleteFailed` | The supported delete workflow invoked Helm, but Helm couldn't remove the Arc release. | Follow the [Helm release deletion steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0501-helmreleasedeletefailed). **Fixed when:** the supported delete succeeds and Helm no longer lists the release. |
| `AZK8S0502` `HelmChartPullFailed` | All five attempts to pull and unpack the Arc OCI chart failed. | Follow the [chart pull steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0502-helmchartpullfailed). **Fixed when:** the same managed chart and version pull successfully. |
| `AZK8S0503` `HelmChartExportFailed` | Helm returned success, but the expected exported chart directory wasn't present. | Follow the [chart export steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0503-helmchartexportfailed). **Fixed when:** the expected chart directory exists and the operation advances. |
| `AZK8S0504` `HelmRepositoryAddFailed` | Helm couldn't add the repository supplied through the `HELMREPONAME` and `HELMREPOURL` environment variables. | Follow the [repository steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0504-helmrepositoryaddfailed). **Fixed when:** the repository add succeeds and the original operation advances. |
| `AZK8S0505` `HelmReleaseListFailed` | Helm couldn't query release metadata across namespaces, so the extension couldn't determine Arc release ownership. | Follow the [release-list steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0505-helmreleaselistfailed). **Fixed when:** the same kubeconfig and context return valid release JSON. |
| `AZK8S0506` `AgentStateTimeout` | During create or update, Azure continued reporting a nonterminal agent state for 15 minutes. A missing state, `Succeeded`, and `Failed` are terminal in version 1.11.5. | Follow the [agent-state steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0506-agentstatetimeout). **Fixed when:** a retry observes a terminal state and completes without `AZK8S0506`; investigate `Failed` separately. |
| `AZK8S0507` `KeyPairGenerationFailed` | The extension's in-memory RSA-4096 key generation failed before key injection. | Follow the [key-generation steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0507-keypairgenerationfailed). **Fixed when:** a retry generates the key and advances to cluster access checks. |
| `AZK8S0508` `ReleaseNamespaceNotFound` | Update, upgrade, or feature validation couldn't find an `azure-arc` Helm release namespace. | Follow the [release-namespace steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0508-releasenamespacenotfound). **Fixed when:** the intended release and namespace are consistently discoverable or support completes an ownership-safe recovery. |
| `AZK8S0509` `HelmValuesGetFailed` | Helm couldn't read the values needed to preserve or inspect the current Arc release configuration. | Follow the [Helm values steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0509-helmvaluesgetfailed). **Fixed when:** the same Helm values query exits with code `0`. |
| `AZK8S0510` `HelmNotInstalled` | In an AGC cloud, where version 1.11.5 requires a preinstalled client, `helm` wasn't found on `PATH`. | Follow the [Helm installation steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0510-helmnotinstalled). **Fixed when:** Helm 3 or later resolves from `PATH` in the same process environment. |
| `AZK8S0511` `HelmVersionTooOld` | The Helm client reported a major version below 3. | Follow the [Helm version steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0511-helmversiontooold). **Fixed when:** the selected client reports major version 3 or later. |
| `AZK8S0512` `HelmTimeoutPendingOrUnschedulable` | A Helm timeout occurred and read-only diagnostics found pending pods or scheduling constraints. | Follow the [pending or unschedulable steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0512-helmtimeoutpendingorunschedulable). **Fixed when:** affected workloads schedule and the Helm operation finishes. |
| `AZK8S0513` `HelmTimeoutImagePullFailed` | A Helm timeout occurred and read-only diagnostics found image-pull evidence. This classification takes precedence over scheduling and identity evidence. | Follow the [image-pull steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0513-helmtimeoutimagepullfailed). **Fixed when:** images pull, affected pods become ready, and the Helm operation finishes. |
| `AZK8S0514` `HelmTimeout` | A Helm timeout occurred, but read-only diagnostics found no higher-priority image-pull, scheduling, or identity classification. | Follow the [generic timeout steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0514-helmtimeout). **Fixed when:** the phase-specific failure is corrected and the Helm operation finishes. |
| `AZK8S0515` `HelmClientError` | The operating system couldn't start the selected Helm executable. A Helm process that starts but returns nonzero is handled by the requested operation instead. | Follow the [Helm execution steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0515-helmclienterror). **Fixed when:** that exact executable starts and reports a supported version. |

## Pre-onboarding diagnostic errors

| Code and name | What it means | How to resolve |
| --- | --- | --- |
| `AZK8S0600` `PrediagnosticsFailed` | An unexpected failure occurred in the outer pre-onboarding diagnostic workflow. Specific Helm, Job, and check-result failures use `AZK8S0601`-`AZK8S0607` instead. | Follow the [diagnostic orchestration steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0600-prediagnosticsfailed). **Fixed when:** the same onboarding command completes diagnostics and reaches the precheck result. |
| `AZK8S0601` `PrediagnosticsJobExecutionFailed` | An unexpected exception interrupted the diagnostic Job workflow, including Kubernetes API, Job watch, pod lookup, or cleanup operations. | Follow the [Job execution steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0601-prediagnosticsjobexecutionfailed). **Fixed when:** the Job workflow completes and returns diagnostic output. |
| `AZK8S0602` `PostDiagnosticPrecheckFailed` | The diagnostic Job ran and at least one required DNS, outbound-connectivity, Entra-connectivity, or CRD-ownership check returned `Failed`. | Follow the [failed precheck steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0602-postdiagnosticprecheckfailed). **Fixed when:** every required check is `Passed` or an explicitly allowed `NotApplicable`. |
| `AZK8S0603` `PrediagnosticsIncomplete` | The extension couldn't obtain a trustworthy result, such as when the Job wasn't scheduled, didn't finish, produced no usable output, or omitted a required result. | Follow the [incomplete-result steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0603-prediagnosticsincomplete). **Fixed when:** the Job completes and every required check has a conclusive result. |
| `AZK8S0604` `PrediagnosticsJobNotScheduled` | During the 180-second Job watch, the extension never observed the named diagnostic Job. This warning is normally followed by `AZK8S0603`. | Follow the [Job scheduling steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0604-prediagnosticsjobnotscheduled). **Fixed when:** the Job is observed and a diagnostic pod can be created. |
| `AZK8S0605` `PrediagnosticsJobNotComplete` | The Job was observed but didn't reach `Complete` before the watch ended, or it reached three failed attempts. This warning is followed by the aggregate result, usually `AZK8S0603`. | Follow the [Job completion steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0605-prediagnosticsjobnotcomplete). **Fixed when:** the Job reaches `Complete` within the watch period. |
| `AZK8S0606` `PrediagnosticsLogSaveFailed` | A non-disk-full local write or conversion error prevented the extension from saving a copy of diagnostic Job logs. The warning doesn't replace the Job's check result. | Follow the [local log-save steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0606-prediagnosticslogsavefailed). **Fixed when:** the log file is written, or the diagnostic result is otherwise collected when a local copy isn't required. |
| `AZK8S0607` `PrediagnosticsHelmInstallFailed` | `helm upgrade --install` couldn't install and wait for the temporary `cluster-diagnostic-checks` release. | Follow the [diagnostic Helm-install steps](troubleshoot-azure-resources-helm-diagnostics.md#azk8s0607-prediagnosticshelminstallfailed). **Fixed when:** the temporary release installs and its Job can start. |

## Feature errors

| Code and name | What it means | How to resolve |
| --- | --- | --- |
| `AZK8S0700` `CustomLocationsEnableFailed` | Custom Locations prerequisites failed and no other requested feature remained to enable, so `enable-features` stopped before kubeconfig, chart, or Helm work. A mixed feature request removes Custom Locations and continues with the remaining features instead. | Follow the [Custom Locations enablement steps](troubleshoot-features-cluster-connect.md#azk8s0700-customlocationsenablefailed). **Fixed when:** the provider is registered, a valid tenant-specific object ID is available, and the same request advances to Helm feature enablement. |
| `AZK8S0701` `CustomLocationsOidFetchFailed` | Microsoft Graph returned no Custom Locations service principal when no manual object ID was supplied, or the Graph lookup raised an exception. This is a nonfatal diagnostic: a supplied object ID can be used without validation; otherwise Custom Locations is skipped and `AZK8S0700` can follow. | Follow the [object-ID lookup steps](troubleshoot-features-cluster-connect.md#azk8s0701-customlocationsoidfetchfailed). **Fixed when:** Graph returns the tenant-specific object ID or the exact verified object ID is supplied manually and enablement advances. |
| `AZK8S0702` `CustomLocationsRegistrationCheckFailed` | The extension raised an exception while querying `Microsoft.ExtendedLocation` registration or retrieving its prerequisite object ID. This nonfatal diagnostic disables Custom Locations for the request; it does not prove that the provider is unregistered. | Follow the [provider-check steps](troubleshoot-features-cluster-connect.md#azk8s0702-customlocationsregistrationcheckfailed). **Fixed when:** the provider query succeeds, returns `Registered`, and object-ID retrieval can proceed. |

See [Create and manage custom locations on Azure Arc-enabled Kubernetes](https://learn.microsoft.com/azure/azure-arc/kubernetes/custom-locations)
for current prerequisites and permissions.

## Client proxy errors

| Code and name | What it means | How to resolve |
| --- | --- | --- |
| `AZK8S0800` `ClientProxyDownloadFailed` | Azure CLI could not prepare the OS- and architecture-specific Cluster Connect proxy. This includes installation-directory creation or cleanup, MCR artifact download, archive validation or extraction, executable permission, and expected-file checks. | Follow the [proxy download and installation steps](troubleshoot-features-cluster-connect.md#azk8s0800-clientproxydownloadfailed). **Fixed when:** preparation completes and the command advances to proxy startup. |
| `AZK8S0801` `ClientProxyPortInUse` | The requested local API port or the proxy's internal port is already in use. | Follow the [port conflict steps](troubleshoot-features-cluster-connect.md#azk8s0801-clientproxyportinuse). **Fixed when:** the proxy remains running and listens on both selected ports. |
| `AZK8S0802` `ClientProxyStartFailed` | The proxy executable was prepared and its configuration was written, but the operating system rejected or failed process creation. It doesn't mean a process that started later exited. | Follow the [proxy process-start steps](troubleshoot-features-cluster-connect.md#azk8s0802-clientproxystartfailed). **Fixed when:** process creation succeeds and the command advances to token and credential exchange. |
| `AZK8S0803` `ClientProxyConfigCreateFailed` | Azure CLI couldn't remove the previous `config.yml` or write its replacement in the proxy installation directory. | Follow the [proxy configuration steps](troubleshoot-features-cluster-connect.md#azk8s0803-clientproxyconfigcreatefailed). **Fixed when:** the configuration is replaced and the command advances to process startup. |
| `AZK8S0804` `ClientProxyClosed` | A proxy process that started successfully wasn't running when Azure CLI next checked it. Version 1.11.5 checks after each 60-second monitoring interval. | Follow the [proxy exit steps](troubleshoot-features-cluster-connect.md#azk8s0804-clientproxyclosed). **Fixed when:** the proxy remains running beyond the monitor interval and `/version` succeeds through its generated context. |
| `AZK8S0805` `ClusterCredentialsGetFailed` | Reserved standardized definition for Cluster Connect credential retrieval. In version 1.11.5, the active path terminates the proxy, records the legacy credential fault type, and raises the ARM helper's unnumbered typed error instead of emitting `AZK8S0805` directly. | Follow the [Cluster Connect credential steps](troubleshoot-features-cluster-connect.md#azk8s0805-clustercredentialsgetfailed) for `AZK8S0805` or the legacy ARM error. **Fixed when:** the proxy remains running and `/version` succeeds through its generated context. |

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

- [Troubleshoot cluster access and networking](troubleshoot-cluster-access-networking.md)
- [Troubleshoot Azure resources, Helm, and diagnostics](troubleshoot-azure-resources-helm-diagnostics.md)
- [Troubleshoot features and Cluster Connect](troubleshoot-features-cluster-connect.md)
- [Azure Arc-enabled Kubernetes system requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/system-requirements)
- [Connect an existing Kubernetes cluster to Azure Arc](https://learn.microsoft.com/azure/azure-arc/kubernetes/quickstart-connect-cluster#prerequisites)
- [Azure Arc-enabled Kubernetes network requirements](https://learn.microsoft.com/azure/azure-arc/kubernetes/network-requirements)
- [Troubleshoot platform issues for Azure Arc-enabled Kubernetes clusters](https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting)
- [Diagnose connection issues for Azure Arc-enabled Kubernetes clusters](https://learn.microsoft.com/azure/azure-arc/kubernetes/diagnose-connection-issues)
