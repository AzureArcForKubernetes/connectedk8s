Describe 'Basic Onboarding Scenario' {
    BeforeAll {
        . $PSScriptRoot/../helper/Constants.ps1
    }


    function Wait-ForProvisioning {
        param (
            [string]$expectedProvisioningState,
            [string]$expectedAutoUpdate
        )
        $n = 0
        do {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $jsonOutput = [System.Text.Json.JsonDocument]::Parse($output)
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            $autoUpdate = $jsonOutput.RootElement.GetProperty("arcAgentProfile").GetProperty("agentAutoUpgrade").GetString()
            Write-Host "Provisioning State: $provisioningState"
            Write-Host "Auto Update: $autoUpdate"
            if ($provisioningState -eq $expectedProvisioningState -and $autoUpdate -eq $expectedAutoUpdate) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS
    }

    It 'Check if basic onboarding works correctly' {
        az connectedk8s connect -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup -l $ARC_LOCATION --no-wait
        $? | Should -BeTrue
        Start-Sleep -Seconds 10
        Wait-ForProvisioning -expectedProvisioningState $SUCCEEDED -expectedAutoUpdate "Enabled"
    }

    It 'Enable azure-rbac feature' {
        az connectedk8s enable-features -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --features azure-rbac
        $? | Should -BeTrue
        Start-Sleep -Seconds 10
        Wait-ForProvisioning -expectedProvisioningState $SUCCEEDED -expectedAutoUpdate "Enabled"
    }

    It 'Disable azure-rbac feature' {
        az connectedk8s disable-features -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --features azure-rbac
        $? | Should -BeTrue
        Start-Sleep -Seconds 10
        Wait-ForProvisioning -expectedProvisioningState $SUCCEEDED -expectedAutoUpdate "Enabled"
    }

    It 'Enable cluster-connect feature' {
        az connectedk8s enable-features -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --features cluster-connect
        $? | Should -BeTrue
        Start-Sleep -Seconds 10
        Wait-ForProvisioning -expectedProvisioningState $SUCCEEDED -expectedAutoUpdate "Enabled"
    }

    It 'Disable cluster-connect feature' {
        az connectedk8s disable-features -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --features cluster-connect
        $? | Should -BeTrue
        Start-Sleep -Seconds 10
        Wait-ForProvisioning -expectedProvisioningState $SUCCEEDED -expectedAutoUpdate "Enabled"
    }

    It 'Enable custom-locations feature' {
        az connectedk8s enable-features -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --features custom-locations --custom-locations-oid $ENVCONFIG.customLocationsOid
        $? | Should -BeTrue
        Start-Sleep -Seconds 10
        Wait-ForProvisioning -expectedProvisioningState $SUCCEEDED -expectedAutoUpdate "Enabled"
    }

    It 'Disable custom-locations feature' {
        az connectedk8s disable-features -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --features custom-locations
        $? | Should -BeTrue
        Start-Sleep -Seconds 10
        Wait-ForProvisioning -expectedProvisioningState $SUCCEEDED -expectedAutoUpdate "Enabled"
    }

    It 'Enable all features (cluster-connect, custom-locations, azure-rbac) together' {
        az connectedk8s enable-features -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --features cluster-connect custom-locations azure-rbac --custom-locations-oid $ENVCONFIG.customLocationsOid
        $? | Should -BeTrue
        Start-Sleep -Seconds 10
        Wait-ForProvisioning -expectedProvisioningState $SUCCEEDED -expectedAutoUpdate "Enabled"
    }

    It 'Disable all features (cluster-connect, custom-locations, azure-rbac) together' {
        az connectedk8s disable-features -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --features cluster-connect custom-locations azure-rbac
        $? | Should -BeTrue
        Start-Sleep -Seconds 10
        Wait-ForProvisioning -expectedProvisioningState $SUCCEEDED -expectedAutoUpdate "Enabled"
    }

    It 'Disable auto-upgrade' {
    az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --auto-upgrade false
    $? | Should -BeTrue
    Start-Sleep -Seconds 10
    Wait-ForProvisioning -expectedProvisioningState $SUCCEEDED -expectedAutoUpdate "Disabled"
    }

    It "Delete the connected instance" {
        az connectedk8s delete -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup -y
        $? | Should -BeTrue

        # Configuration should be removed from the resource model
        az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
        $? | Should -BeFalse
    }
}