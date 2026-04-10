# test_prediagnostic_telemetry.ps1
# Exercises all prediagnostic failing scenarios and verifies az connectedk8s connect fails.
# Usage: .\test_prediagnostic_telemetry.ps1
# Prerequisites: kubectl configured, az cli with connectedk8s extension from source (env1), kubeconfig set.

param(
    [string]$ResourceGroup = "audittest",
    [string]$Location = "eastus2euap"
)

# ── Helpers ──────────────────────────────────────────────────────────────────

$PASS = "[PASS]"
$FAIL = "[FAIL]"
$INFO = "[INFO]"

function Log-Info  { param($msg) Write-Host "$INFO $msg" -ForegroundColor Cyan }
function Log-Pass  { param($msg) Write-Host "$PASS $msg" -ForegroundColor Green }
function Log-Fail  { param($msg) Write-Host "$FAIL $msg" -ForegroundColor Red }
function Log-Sep   { Write-Host ("`n" + "─" * 70) -ForegroundColor DarkGray }

$OriginalCorefile = $null

function Save-CoreDNS {
    $script:OriginalCorefile = kubectl get configmap coredns -n kube-system -o jsonpath='{.data.Corefile}' 2>&1
    Log-Info "CoreDNS original config saved."
}

function Restore-CoreDNS {
    if (-not $script:OriginalCorefile) { return }
    Log-Info "Restoring CoreDNS..."
    $patch = @{data = @{Corefile = $script:OriginalCorefile}} | ConvertTo-Json -Compress -Depth 5
    kubectl patch configmap coredns -n kube-system --type merge -p $patch | Out-Null
    kubectl rollout restart deployment/coredns -n kube-system | Out-Null
    kubectl rollout status deployment/coredns -n kube-system --timeout=60s | Out-Null
    Log-Info "CoreDNS restored."
}

function Apply-CoreDNS-Block {
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
    Log-Info "CoreDNS block applied for: $($Hosts -join ', ')"
}

function Run-ConnectTest {
    param([string]$ClusterName, [string]$TestDescription)
    Log-Info "Running: az connectedk8s connect -g $ResourceGroup -n $ClusterName"
    $output = az connectedk8s connect -g $ResourceGroup -n $ClusterName --location $Location 2>&1
    $exitCode = $LASTEXITCODE

    $telemetryLines = $output | Where-Object { $_ -match "\[Telemetry\]" }
    $resultLines    = $output | Where-Object { $_ -match "Pre-onboarding Diagnostic|Precheck summary|pre-checks|required pre-checks" }

    Write-Host "`n  ── Output excerpt ──"
    $resultLines | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    $telemetryLines | ForEach-Object { Write-Host "  $_" -ForegroundColor Magenta }

    if ($exitCode -ne 0) {
        Log-Pass "$TestDescription → command failed as expected (exit $exitCode)"
        if (-not $telemetryLines) {
            Write-Host "  WARNING: No [Telemetry] line found in output." -ForegroundColor DarkYellow
        }
    } else {
        Log-Fail "$TestDescription → command SUCCEEDED but was expected to FAIL"
    }
}

function Cleanup-AzResource {
    param([string]$ClusterName)
    Log-Info "Cleaning up ARM resource: $ClusterName (if it exists)"
    az connectedk8s delete -g $ResourceGroup -n $ClusterName --force -y 2>&1 | Out-Null
}

function Apply-BadCRD {
    param([string]$CRDName)
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
    plural: $(($CRDName -split '\.')[0])
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
    Log-Info "Bad CRD applied: $CRDName"
}

function Remove-CRD {
    param([string]$CRDName)
    kubectl delete crd $CRDName --ignore-not-found=true 2>&1 | Out-Null
    Log-Info "CRD removed: $CRDName"
}

function Apply-PodQuota {
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
    kubectl create namespace azure-arc-release --dry-run=client -o yaml | kubectl apply -f - 2>&1 | Out-Null
    $quota | kubectl apply -f - 2>&1 | Out-Null
    Log-Info "ResourceQuota applied: pods=0 in azure-arc-release"
}

function Remove-PodQuota {
    kubectl delete resourcequota block-pods -n azure-arc-release --ignore-not-found=true 2>&1 | Out-Null
    Log-Info "ResourceQuota removed."
}

# ── Main ─────────────────────────────────────────────────────────────────────

$results = @()

Save-CoreDNS

# ─────────────────────────────────────────────────────────────────────────────
Log-Sep
Log-Info "TEST 1: Block MCR (outbound connectivity failure)"
Log-Info "Expected telemetry: onboardingErrorType=prediagnostics-failure, outboundConnectivityCheck=Failed"
# ─────────────────────────────────────────────────────────────────────────────
$clusterName = "adblocktest-mcr"
Cleanup-AzResource $clusterName
Apply-CoreDNS-Block -Hosts @("mcr.microsoft.com")
Run-ConnectTest -ClusterName $clusterName -TestDescription "MCR outbound block"
Restore-CoreDNS
Cleanup-AzResource $clusterName
$results += "TEST 1 - MCR Block"

# ─────────────────────────────────────────────────────────────────────────────
Log-Sep
Log-Info "TEST 2: Block Entra auth endpoint (Entra check failure)"
Log-Info "Expected telemetry: onboardingErrorType=prediagnostics-failure, entraCheck=Failed"
# ─────────────────────────────────────────────────────────────────────────────
$clusterName = "adblocktest-entra"
Cleanup-AzResource $clusterName
Apply-CoreDNS-Block -Hosts @("login.microsoftonline.com")
Run-ConnectTest -ClusterName $clusterName -TestDescription "Entra endpoint block"
Restore-CoreDNS
Cleanup-AzResource $clusterName
$results += "TEST 2 - Entra Block"

# ─────────────────────────────────────────────────────────────────────────────
Log-Sep
Log-Info "TEST 3: Block BOTH MCR + Entra (combined outbound failure)"
Log-Info "Expected telemetry: onboardingErrorType=prediagnostics-failure, outboundConnectivityCheck=Failed, entraCheck=Failed"
# ─────────────────────────────────────────────────────────────────────────────
$clusterName = "adblocktest-all-outbound"
Cleanup-AzResource $clusterName
Apply-CoreDNS-Block -Hosts @("mcr.microsoft.com", "login.microsoftonline.com")
Run-ConnectTest -ClusterName $clusterName -TestDescription "MCR + Entra combined block"
Restore-CoreDNS
Cleanup-AzResource $clusterName
$results += "TEST 3 - MCR + Entra Block"

# ─────────────────────────────────────────────────────────────────────────────
Log-Sep
Log-Info "TEST 4: CRD ownership conflict (crdCheck failure)"
Log-Info "Expected telemetry: onboardingErrorType=prediagnostics-failure, crdCheck=Failed"
# ─────────────────────────────────────────────────────────────────────────────
$clusterName = "adblocktest-crd"
Cleanup-AzResource $clusterName
Apply-BadCRD "extensionconfigs.clusterconfig.azure.com"
Run-ConnectTest -ClusterName $clusterName -TestDescription "CRD ownership conflict"
Remove-CRD "extensionconfigs.clusterconfig.azure.com"
Cleanup-AzResource $clusterName
$results += "TEST 4 - CRD Conflict"

# ─────────────────────────────────────────────────────────────────────────────
Log-Sep
Log-Info "TEST 5: Job cannot be scheduled (ResourceQuota pods=0)"
Log-Info "Expected telemetry: onboardingErrorType=prediagnostics-job-execution-error, jobExecutionStatus=NotScheduled"
# ─────────────────────────────────────────────────────────────────────────────
$clusterName = "adblocktest-nojob"
Cleanup-AzResource $clusterName
Apply-PodQuota
Run-ConnectTest -ClusterName $clusterName -TestDescription "Job not schedulable"
Remove-PodQuota
Cleanup-AzResource $clusterName
$results += "TEST 5 - Job Not Schedulable"

# ─────────────────────────────────────────────────────────────────────────────
Log-Sep
Log-Info "TEST 6: Happy path (all checks pass — command should SUCCEED)"
Log-Info "Expected: no [Telemetry] failure lines, 'pre-checks have succeeded'"
# ─────────────────────────────────────────────────────────────────────────────
$clusterName = "adblocktest-happy"
Log-Info "Running: az connectedk8s connect -g $ResourceGroup -n $clusterName"
$output = az connectedk8s connect -g $ResourceGroup -n $clusterName --location $Location 2>&1
$exitCode = $LASTEXITCODE
$telemetryFailLines = $output | Where-Object { $_ -match "\[Telemetry\].*prediagnostics" }
if ($exitCode -eq 0 -and -not $telemetryFailLines) {
    Log-Pass "Happy path → command succeeded, no failure telemetry"
} elseif ($exitCode -eq 0 -and $telemetryFailLines) {
    Log-Fail "Happy path → command succeeded BUT unexpected [Telemetry] failure lines found:"
    $telemetryFailLines | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
} else {
    Log-Fail "Happy path → command FAILED unexpectedly (exit $exitCode)"
}
Cleanup-AzResource $clusterName
$results += "TEST 6 - Happy Path"

# ─────────────────────────────────────────────────────────────────────────────
Log-Sep
Write-Host "`nTest run complete. Scenarios executed:" -ForegroundColor White
$results | ForEach-Object { Write-Host "  • $_" -ForegroundColor Gray }
Log-Sep
