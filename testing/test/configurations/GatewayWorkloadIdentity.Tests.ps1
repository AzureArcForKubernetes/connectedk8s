Describe 'Onboarding with Gateway Scenario' {
    BeforeAll {
        . $PSScriptRoot/../helper/Constants.ps1

        $gatewayResourceId = "/subscriptions/15c06b1b-01d6-407b-bb21-740b8617dea3/resourceGroups/connectedk8sCLITestResources/providers/Microsoft.HybridCompute/gateways/gateway-test-cli"
    }

    It 'Check if onboarding works with gateway and workload identity enabled' {
        az connectedk8s connect -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup -l $ARC_LOCATION --gateway-resource-id $gatewayResourceId --enable-oidc-issuer --enable-workload-identity
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $jsonOutput = [System.Text.Json.JsonDocument]::Parse($output)
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            $gatewayStatus = $jsonOutput.RootElement.GetProperty("gateway").GetProperty("enabled").GetBoolean()
            $securityProfile = $jsonOutput.RootElement.GetProperty("securityProfile").GetProperty("workloadIdentity").GetProperty("enabled").GetBoolean()
            $oidcIssuerProfile = $jsonOutput.RootElement.GetProperty("oidcIssuerProfile").GetProperty("enabled").GetBoolean()
            $issuerUrl = $jsonOutput.RootElement.GetProperty("oidcIssuerProfile").GetProperty("issuerUrl").GetString()
            $selfHostedIssuerUrl = $jsonOutput.RootElement.GetProperty("oidcIssuerProfile").GetProperty("selfHostedIssuerUrl").GetString() 
            $agentState = $jsonOutput.RootElement.GetProperty("arcAgentProfile").GetProperty("agentState").GetString()
            Write-Host "Provisioning State: $provisioningState"
            Write-Host "Gateway Status: $gatewayStatus"
            Write-Host "Security Profile Status: $securityProfile"
            Write-Host "OIDC Issuer Profile Status: $oidcIssuerProfile"
            Write-Host "Issuer Url: $issuerUrl"
            Write-Host "Self Hosted Issuer Url: $selfHostedIssuerUrl"
            Write-Host "Agent State: $agentState"
            if ($provisioningState -eq $SUCCEEDED -and $gatewayStatus -eq $true-and 
                $securityProfile -eq $true -and 
                $oidcIssuerProfile -eq $true -and 
                ![string]::IsNullOrEmpty($issuerUrl) -and 
                $issuerUrl -like "*unitedkingdom*" -and 
                [string]::IsNullOrEmpty($selfHostedIssuerUrl) -and
                $agentState -eq $SUCCEEDED) {
                break
            }
            Start-Sleep -Seconds 30
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS
    }

    It 'Disable the gateway and workload identity' {
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --disable-gateway --disable-workload-identity
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $jsonOutput = [System.Text.Json.JsonDocument]::Parse($output)
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            $gatewayStatus = $jsonOutput.RootElement.GetProperty("gateway").GetProperty("enabled").GetBoolean()
            $securityProfile = $jsonOutput.RootElement.GetProperty("securityProfile").GetProperty("workloadIdentity").GetProperty("enabled").GetBoolean()
            $agentState = $jsonOutput.RootElement.GetProperty("arcAgentProfile").GetProperty("agentState").GetString()
            Write-Host "Provisioning State: $provisioningState"
            Write-Host "Gateway Status: $gatewayStatus"
            Write-Host "Security Profile Status: $securityProfile"
            Write-Host "Agent State: $agentState"
            if ($provisioningState -eq $SUCCEEDED -and $gatewayStatus -eq $false -and $securityProfile -eq $false -and $agentState -eq $SUCCEEDED) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS
    }

    It 'Update the cluster to use gateway and workload identity again using update cmd' {
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --gateway-resource-id $gatewayResourceId --enable-workload-identity
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $jsonOutput = [System.Text.Json.JsonDocument]::Parse($output)
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            $gatewayStatus = $jsonOutput.RootElement.GetProperty("gateway").GetProperty("enabled").GetBoolean()
            $securityProfile = $jsonOutput.RootElement.GetProperty("securityProfile").GetProperty("workloadIdentity").GetProperty("enabled").GetBoolean()
            $agentState = $jsonOutput.RootElement.GetProperty("arcAgentProfile").GetProperty("agentState").GetString()
            Write-Host "Provisioning State: $provisioningState"
            Write-Host "Gateway Status: $gatewayStatus"
            Write-Host "Security Profile Status: $securityProfile"
            Write-Host "Agent State: $agentState"
            if ($provisioningState -eq $SUCCEEDED -and
                $gatewayStatus -eq $true -and
                $securityProfile -eq $true -and
                $agentState -eq $SUCCEEDED) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS
    }

    It 'Disable the gateway' {
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --disable-gateway
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $jsonOutput = [System.Text.Json.JsonDocument]::Parse($output)
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            $gatewayStatus = $jsonOutput.RootElement.GetProperty("gateway").GetProperty("enabled").GetBoolean()
            Write-Host "Provisioning State: $provisioningState"
            Write-Host "Gateway Status: $gatewayStatus"
            if ($provisioningState -eq $SUCCEEDED -and $gatewayStatus -eq $false) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS
    }

    It 'Disable workload identity' {
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --disable-workload-identity
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $jsonOutput = [System.Text.Json.JsonDocument]::Parse($output)
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            $securityProfile = $jsonOutput.RootElement.GetProperty("securityProfile").GetProperty("workloadIdentity").GetProperty("enabled").GetBoolean()
            $agentState = $jsonOutput.RootElement.GetProperty("arcAgentProfile").GetProperty("agentState").GetString()
            Write-Host "Provisioning State: $provisioningState"
            Write-Host "Security Profile Status: $securityProfile"
            Write-Host "Agent State: $agentState"
            if ($provisioningState -eq $SUCCEEDED -and $securityProfile -eq $false -and $agentState -eq $SUCCEEDED) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS
    }

    It "Delete the connected instance" {
        az connectedk8s delete -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --force -y
        $? | Should -BeTrue

        # Configuration should be removed from the resource model
        az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
        $? | Should -BeFalse
    }
}