Describe 'Proxy Scenario' {
    BeforeAll {
        . $PSScriptRoot/../helper/Constants.ps1
    }

    It 'Check if basic onboarding works correctly with proxy enabled' {
        az connectedk8s connect -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup -l $ARC_LOCATION --proxy-skip-range logcollector --no-wait
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            Write-Host "Provisioning State: $provisioningState"
            if ($provisioningState -eq $SUCCEEDED) {
                $isProxyEnabled = helm get values -n azure-arc-release azure-arc -o yaml | grep isProxyEnabled
                Write-Host "$isProxyEnabled"
                if ($isProxyEnabled -match "isProxyEnabled: true") {
                    break
                }
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS
    }

    It 'Add and clear the Arc and Container Insights proxy bypass' {
        # Each keyword writes to its own target, so each is asserted where it lands
        $arcEndpoints = @(
            ".his.arc.azure.com",
            ".dp.kubernetesconfiguration.azure.com",
            ".guestconfiguration.azure.com"
        )

        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --add-proxy-bypass Arc,Microsoft.AzureMonitor.Containers
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the agents pick up the widened skip range
        $n = 0
        do
        {
            $noProxy = helm get values -n azure-arc-release azure-arc -o yaml | grep noProxy | Out-String
            Write-Host "noProxy: $noProxy"
            if (@($arcEndpoints | Where-Object { $noProxy -like "*$_*" }).Count -eq $arcEndpoints.Count) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        # Every Arc endpoint has to be bypassed, not just the one that ended the loop
        foreach ($endpoint in $arcEndpoints) {
            $noProxy | Should -BeLike "*$endpoint*"
        }

        # The annotation is what marks the ConfigMap setting as written by the CLI
        $agentConfig = kubectl get configmap container-azm-ms-agentconfig -n kube-system -o yaml | Out-String
        $? | Should -BeTrue
        $agentConfig | Should -BeLike '*ignore_proxy_settings = "true"*'
        $agentConfig | Should -BeLike "*connectedk8s.arc.azure.com/proxy-bypass*"

        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --clear-proxy-bypass Arc,Microsoft.AzureMonitor.Containers
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the endpoints are withdrawn from the skip range
        $n = 0
        do
        {
            $noProxy = helm get values -n azure-arc-release azure-arc -o yaml | grep noProxy | Out-String
            Write-Host "noProxy: $noProxy"
            if (@($arcEndpoints | Where-Object { $noProxy -like "*$_*" }).Count -eq 0) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        # No Arc endpoint may survive the clear
        foreach ($endpoint in $arcEndpoints) {
            $noProxy | Should -Not -BeLike "*$endpoint*"
        }

        # Only the Arc endpoints are removed, so the onboarded skip range stays
        $noProxy | Should -BeLike "*logcollector*"

        # Clearing turns the setting off and drops the annotation, not the ConfigMap
        $agentConfig = kubectl get configmap container-azm-ms-agentconfig -n kube-system -o yaml | Out-String
        $? | Should -BeTrue
        $agentConfig | Should -BeLike '*ignore_proxy_settings = "false"*'
        $agentConfig | Should -Not -BeLike "*connectedk8s.arc.azure.com/proxy-bypass*"
    }

    It 'Keeps an Arc endpoint the skip range lists on its own' {
        # One endpoint is not the bypass this CLI applies, so it is kept as typed
        $ownEndpoint = ".his.arc.azure.com"
        $bypassEndpoints = @(
            ".dp.kubernetesconfiguration.azure.com",
            ".guestconfiguration.azure.com"
        )

        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --proxy-skip-range "logcollector,$ownEndpoint"
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the agents pick up the new skip range
        $n = 0
        do
        {
            $noProxy = helm get values -n azure-arc-release azure-arc -o yaml | grep noProxy | Out-String
            Write-Host "noProxy: $noProxy"
            if ($noProxy -like "*$ownEndpoint*") {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        # The rest of the bypass was never asked for, so it must not have been added
        foreach ($endpoint in $bypassEndpoints) {
            $noProxy | Should -Not -BeLike "*$endpoint*"
        }

        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --clear-proxy-bypass Arc
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # The endpoint was listed by hand, so the clear leaves it alone
        $noProxy = helm get values -n azure-arc-release azure-arc -o yaml | grep noProxy | Out-String
        Write-Host "noProxy: $noProxy"
        $noProxy | Should -BeLike "*$ownEndpoint*"
        $noProxy | Should -BeLike "*logcollector*"

        # Put the skip range back for the tests that follow
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --proxy-skip-range logcollector
        $? | Should -BeTrue
    }

    It 'Disable proxy' {
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --disable-proxy
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            Write-Host "Provisioning State: $provisioningState"
            if ($provisioningState -eq $SUCCEEDED) {
                $isProxyEnabled = helm get values -n azure-arc-release azure-arc -o yaml | grep isProxyEnabled
                Write-Host "$isProxyEnabled"
                if ($isProxyEnabled -match "isProxyEnabled: false") {
                    break
                }
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