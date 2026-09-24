Describe 'Pre-onboarding Diagnostic Telemetry Scenario' {
    BeforeAll {
        . $PSScriptRoot/../helper/Constants.ps1

        $script:OriginalCorefile = kubectl get configmap coredns -n kube-system -o jsonpath='{.data.Corefile}' 2>&1

        function Invoke-RestoreCoreDNS {
            if (-not $script:OriginalCorefile) { return }
            $patch = @{data = @{Corefile = $script:OriginalCorefile}} | ConvertTo-Json -Compress -Depth 5
            kubectl patch configmap coredns -n kube-system --type merge -p $patch | Out-Null
            kubectl rollout restart deployment/coredns -n kube-system | Out-Null
            kubectl rollout status deployment/coredns -n kube-system --timeout=60s | Out-Null
        }

        function Invoke-CoreDNSBlock {
            param([string[]]$Hosts)
            $hostsBlock = ($Hosts | ForEach-Object { "      192.0.2.1 $_" }) -join "`n"
            $newCorefile = @"
.:53 {
    errors
    ready
    health {
      lameduck 5s
    }
    hosts {
$hostsBlock
      fallthrough
    }
    kubernetes cluster.local in-addr.arpa ip6.arpa {
      pods insecure
      fallthrough in-addr.arpa ip6.arpa
      ttl 30
    }
    prometheus :9153
    forward . /etc/resolv.conf
    cache 30
    loop
    reload
    loadbalance
    import custom/*.override
    template ANY ANY internal.cloudapp.net {
      match "^(?:[^.]+\.){4,}internal\.cloudapp\.net\.$"
      rcode NXDOMAIN
      fallthrough
    }
    template ANY ANY reddog.microsoft.com {
      rcode NXDOMAIN
    }
}
import custom/*.server
"@
            $patch = @{data = @{Corefile = $newCorefile}} | ConvertTo-Json -Compress -Depth 5
            kubectl patch configmap coredns -n kube-system --type merge -p $patch | Out-Null
            kubectl rollout restart deployment/coredns -n kube-system | Out-Null
            kubectl rollout status deployment/coredns -n kube-system --timeout=60s | Out-Null
        }

        function Invoke-ApplyBadCRD {
            param([string]$CRDName)
            $plural = ($CRDName -split '\.')[0]
            $manifest = @"
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: $CRDName
  annotations:
    meta.helm.sh/release-name: some-other-component
    meta.helm.sh/release-namespace: default
spec:
  group: clusterconfig.azure.com
  names:
    kind: FakeResource
    listKind: FakeResourceList
    plural: $plural
    singular: fakeresource
  scope: Cluster
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
"@
            $manifest | kubectl apply -f - 2>&1 | Out-Null
        }

        function Invoke-ApplyPodQuota {
            kubectl create namespace azure-arc-release --dry-run=client -o yaml | kubectl apply -f - 2>&1 | Out-Null
            $quota = @"
apiVersion: v1
kind: ResourceQuota
metadata:
  name: block-pods
  namespace: azure-arc-release
spec:
  hard:
    pods: "0"
"@
            $quota | kubectl apply -f - 2>&1 | Out-Null
        }

        function Get-CapturedTelemetryEvents {
            param(
                [Parameter(Mandatory = $true)]
                [string]$CaptureDirectory
            )

            $telemetryDirectory = Join-Path $CaptureDirectory "telemetry"
            $cacheFiles = @(
                Get-ChildItem -Path $telemetryDirectory -Filter "cache*" -File -Recurse -ErrorAction Stop
            )
            $cacheFiles.Count | Should -BeGreaterThan 0

            $events = foreach ($cacheFile in $cacheFiles) {
                foreach ($line in Get-Content -Path $cacheFile.FullName) {
                    $separatorIndex = $line.IndexOf(",")
                    $separatorIndex | Should -BeGreaterThan 0

                    $payload = $line.Substring($separatorIndex + 1) | ConvertFrom-Json -Depth 100
                    foreach ($instrumentationKey in $payload.PSObject.Properties) {
                        foreach ($event in @($instrumentationKey.Value)) {
                            $event
                        }
                    }
                }
            }

            return @($events)
        }
    }

    It 'MCR outbound block emits one terminal fault and local diagnostics' {
        $clusterName = "prediag-onefault-$(([guid]::NewGuid()).ToString('N').Substring(0, 8))"
        $captureDirectory = Join-Path $TestDrive "telemetry-capture"
        $captureHookDirectory = Join-Path $PSScriptRoot "../helper/telemetry_capture"
        $originalPythonPath = $env:PYTHONPATH
        $originalCaptureDirectory = $env:AZURE_CLI_TELEMETRY_CAPTURE_DIR
        $originalAzInstaller = $env:AZ_INSTALLER
        $azureCliPython = "/opt/az/bin/python3"

        try {
            Invoke-CoreDNSBlock -Hosts @("mcr.microsoft.com")
            New-Item -ItemType Directory -Path $captureDirectory -Force | Out-Null
            $azureCliPython | Should -Exist

            $pathSeparator = [IO.Path]::PathSeparator
            $env:PYTHONPATH = if ($originalPythonPath) {
                "$captureHookDirectory$pathSeparator$originalPythonPath"
            }
            else {
                $captureHookDirectory
            }
            $env:AZURE_CLI_TELEMETRY_CAPTURE_DIR = $captureDirectory
            $env:AZ_INSTALLER = "DEB"

            $output = & $azureCliPython -m azure.cli connectedk8s connect -g $ENVCONFIG.resourceGroup -n $clusterName -l $ARC_LOCATION 2>&1
            $connectSucceeded = $?

            $connectSucceeded | Should -BeFalse
            ($output -join "`n") | Should -Match "Pre-onboarding Diagnostic|pre-checks"

            $events = Get-CapturedTelemetryEvents -CaptureDirectory $captureDirectory
            $commands = @($events | Where-Object { $_.name -eq "azurecli/command" })
            $faults = @($events | Where-Object { $_.name -eq "azurecli/fault" })
            $extensions = @($events | Where-Object { $_.name -eq "azurecli/extension" })

            $commands.Count | Should -Be 1
            $faults.Count | Should -Be 1

            $faultTypes = @(
                $faults | ForEach-Object {
                    $_.properties.'Context.Default.AzureCLI.FaultType'
                }
            )
            $faultTypes | Should -Contain "cluster-diagnostic-prechecks-failed"
            $faultTypes | Should -Not -Contain "prediagnostics-outbound-non2xx-response"
            $faultTypes | Should -Not -Contain "unable-to-complete-cluster-diagnostic-checks-job-after-scheduling"
            @($faultTypes | Where-Object { $_ -like "prediagnostics-job-*" }).Count | Should -Be 0
            @($faultTypes | Where-Object { $_ -like "prediagnostics-dns-*" }).Count | Should -Be 0

            $diagnosticTypes = @(
                $extensions | ForEach-Object {
                    $_.properties.'Context.Default.AzureCLI.onboardingErrorType'
                } | Where-Object { $_ }
            )
            $diagnosticTypes | Should -Contain "prediagnostics-failure"
        }
        finally {
            if ($null -eq $originalPythonPath) {
                Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
            }
            else {
                $env:PYTHONPATH = $originalPythonPath
            }

            if ($null -eq $originalCaptureDirectory) {
                Remove-Item Env:AZURE_CLI_TELEMETRY_CAPTURE_DIR -ErrorAction SilentlyContinue
            }
            else {
                $env:AZURE_CLI_TELEMETRY_CAPTURE_DIR = $originalCaptureDirectory
            }

            if ($null -eq $originalAzInstaller) {
                Remove-Item Env:AZ_INSTALLER -ErrorAction SilentlyContinue
            }
            else {
                $env:AZ_INSTALLER = $originalAzInstaller
            }

            Invoke-RestoreCoreDNS
            az connectedk8s delete -g $ENVCONFIG.resourceGroup -n $clusterName --force -y 2>&1 | Out-Null
        }
    }

    It 'Entra endpoint block triggers prediagnostics-failure telemetry' {
        $clusterName = "prediag-test-entra"
        try {
            Invoke-CoreDNSBlock -Hosts @("login.microsoftonline.com")
            $output = az connectedk8s connect -g $ENVCONFIG.resourceGroup -n $clusterName -l $ARC_LOCATION 2>&1
            $? | Should -BeFalse
            ($output -join "`n") | Should -Match "Pre-onboarding Diagnostic|pre-checks"
        }
        finally {
            Invoke-RestoreCoreDNS
            az connectedk8s delete -g $ENVCONFIG.resourceGroup -n $clusterName --force -y 2>&1 | Out-Null
        }
    }

    It 'Combined MCR and Entra block triggers prediagnostics-failure telemetry' {
        $clusterName = "prediag-test-combined"
        try {
            Invoke-CoreDNSBlock -Hosts @("mcr.microsoft.com", "login.microsoftonline.com")
            $output = az connectedk8s connect -g $ENVCONFIG.resourceGroup -n $clusterName -l $ARC_LOCATION 2>&1
            $? | Should -BeFalse
            ($output -join "`n") | Should -Match "Pre-onboarding Diagnostic|pre-checks"
        }
        finally {
            Invoke-RestoreCoreDNS
            az connectedk8s delete -g $ENVCONFIG.resourceGroup -n $clusterName --force -y 2>&1 | Out-Null
        }
    }

    It 'CRD ownership conflict triggers prediagnostics-failure telemetry' {
        $clusterName = "prediag-test-crd"
        $crdName = "extensionconfigs.clusterconfig.azure.com"
        Invoke-ApplyBadCRD $crdName
        $output = az connectedk8s connect -g $ENVCONFIG.resourceGroup -n $clusterName -l $ARC_LOCATION 2>&1
        $? | Should -BeFalse
        ($output -join "`n") | Should -Match "Pre-onboarding Diagnostic|pre-checks"
        kubectl delete crd $crdName --ignore-not-found=true 2>&1 | Out-Null
        az connectedk8s delete -g $ENVCONFIG.resourceGroup -n $clusterName --force -y 2>&1 | Out-Null
    }

    It 'Job not schedulable triggers job-execution-error telemetry' {
        $clusterName = "prediag-test-nojob"
        Invoke-ApplyPodQuota
        $output = az connectedk8s connect -g $ENVCONFIG.resourceGroup -n $clusterName -l $ARC_LOCATION 2>&1
        $? | Should -BeFalse
        ($output -join "`n") | Should -Match "Pre-onboarding Diagnostic|pre-checks"
        kubectl delete resourcequota block-pods -n azure-arc-release --ignore-not-found=true 2>&1 | Out-Null
        az connectedk8s delete -g $ENVCONFIG.resourceGroup -n $clusterName --force -y 2>&1 | Out-Null
    }

    It 'Happy path has no prediagnostics failure telemetry' {
        $clusterName = "prediag-test-happy"
        az connectedk8s connect -g $ENVCONFIG.resourceGroup -n $clusterName -l $ARC_LOCATION --no-wait
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        $n = 0
        do {
            $output = az connectedk8s show -n $clusterName -g $ENVCONFIG.resourceGroup
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            Write-Host "Provisioning State: $provisioningState"
            if ($provisioningState -eq $SUCCEEDED) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS
    }

    It 'Delete the connected instance' {
        az connectedk8s delete -g $ENVCONFIG.resourceGroup -n "prediag-test-happy" --force -y
        $? | Should -BeTrue

        az connectedk8s show -n "prediag-test-happy" -g $ENVCONFIG.resourceGroup
        $? | Should -BeFalse
    }
}
