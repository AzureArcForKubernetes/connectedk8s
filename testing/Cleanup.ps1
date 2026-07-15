<#
.SYNOPSIS
    Deletes stale connectedk8s test clusters from the CI resource group.

.DESCRIPTION
    CI runs create clusters named "connectedk8s-cluster-{RAND}-arc". When tests
    fail before reaching the delete step, these orphans accumulate and eventually
    hit the 800-resource quota. This script deletes clusters older than a
    configurable threshold (default: 2 hours).

.PARAMETER MaxAgeHours
    Delete clusters older than this many hours. Default: 2.

.PARAMETER DryRun
    List clusters that would be deleted without actually deleting them.
#>
param (
    [int]$MaxAgeHours = 2,
    [switch]$DryRun
)

$ENVCONFIG = Get-Content -Path $PSScriptRoot/settings.json -ErrorAction SilentlyContinue | ConvertFrom-Json

$resourceGroup = if ($ENVCONFIG.resourceGroup) { $ENVCONFIG.resourceGroup } else { "K8sPartnerExtensionTest" }

Write-Host "Listing connectedClusters in resource group '$resourceGroup'..."
$clusters = az resource list -g $resourceGroup `
    --resource-type Microsoft.Kubernetes/connectedClusters `
    --query "[].{name:name, createdTime:createdTime}" -o json | ConvertFrom-Json

if (-not $clusters -or $clusters.Count -eq 0) {
    Write-Host "No connected clusters found."
    exit 0
}

$cutoff = (Get-Date).ToUniversalTime().AddHours(-$MaxAgeHours)
$stale = $clusters | Where-Object {
    $created = [DateTime]::Parse($_.createdTime).ToUniversalTime()
    $created -lt $cutoff
}

Write-Host "Found $($clusters.Count) total clusters, $($stale.Count) older than $MaxAgeHours hours."

if ($stale.Count -eq 0) {
    Write-Host "Nothing to clean up."
    exit 0
}

foreach ($cluster in $stale) {
    if ($DryRun) {
        Write-Host "[DRY RUN] Would delete: $($cluster.name) (created $($cluster.createdTime))"
    } else {
        Write-Host "Deleting: $($cluster.name) (created $($cluster.createdTime))..."
        az connectedk8s delete -n $cluster.name -g $resourceGroup --force -y 2>&1 | Out-Null
        if ($?) {
            Write-Host "  Deleted successfully."
        } else {
            Write-Host "  Failed to delete (may already be gone). Continuing..."
        }
    }
}

Write-Host "Cleanup complete. Deleted $($stale.Count) stale clusters."
