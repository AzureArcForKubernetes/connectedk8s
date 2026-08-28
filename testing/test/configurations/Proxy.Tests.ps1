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

    It 'Expands the Arc keyword in --proxy-skip-range to the Azure Arc private-link endpoints' {
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --proxy-skip-range Arc
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the Arc keyword expands into the no-proxy list
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            Write-Host "Provisioning State: $provisioningState"
            if ($provisioningState -eq $SUCCEEDED) {
                $noProxy = helm get values -n azure-arc-release azure-arc -o yaml | grep noProxy
                Write-Host "$noProxy"
                if ($noProxy -match "\.his\.arc\.azure") {
                    break
                }
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        $noProxy = helm get values -n azure-arc-release azure-arc -o yaml | grep noProxy
        $noProxy | Should -Match "\.his\.arc\.azure"
        $noProxy | Should -Match "\.dp\.kubernetesconfiguration\.azure"
        $noProxy | Should -Match "\.guestconfiguration\.azure"
    }

    It 'Creates the Container Insights proxy-bypass ConfigMap for the Container Insights keyword' {
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --proxy-skip-range Microsoft.AzureMonitor.Containers
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the update reaches a succeeded provisioning state
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            Write-Host "Provisioning State: $provisioningState"
            if ($provisioningState -eq $SUCCEEDED) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        # The keyword is handled via a ConfigMap, so it must not appear in the agent no-proxy list
        $noProxy = helm get values -n azure-arc-release azure-arc -o yaml | grep noProxy
        $noProxy | Should -Not -Match "Microsoft\.AzureMonitor\.Containers"

        # The Container Insights proxy-bypass ConfigMap must be created in kube-system
        $agentSettings = kubectl get configmap container-azm-ms-agentconfig -n kube-system -o jsonpath='{.data.agent-settings}'
        $? | Should -BeTrue
        # kubectl returns the multi-line agent-settings as an array of lines; join it so the match sees every line.
        $agentSettings = $agentSettings -join "`n"
        $agentSettings | Should -Match "ignore_proxy_settings"
    }

    It 'Merges the proxy bypass into an existing Container Insights ConfigMap without dropping other settings' {
        # Pre-create a ConfigMap that already has an unrelated setting and no proxy bypass.
        kubectl delete configmap container-azm-ms-agentconfig -n kube-system --ignore-not-found
        $manifest = @"
apiVersion: v1
kind: ConfigMap
metadata:
  name: container-azm-ms-agentconfig
  namespace: kube-system
data:
  schema-version: v1
  config-version: ver1
  agent-settings: |-
    [agent_settings.high_log_scale]
      enabled = false
"@
        $manifest | kubectl apply -f -
        $? | Should -BeTrue

        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --proxy-skip-range Microsoft.AzureMonitor.Containers
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the update reaches a succeeded provisioning state
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            Write-Host "Provisioning State: $provisioningState"
            if ($provisioningState -eq $SUCCEEDED) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        # The bypass is merged in...
        $agentSettings = kubectl get configmap container-azm-ms-agentconfig -n kube-system -o jsonpath='{.data.agent-settings}'
        $? | Should -BeTrue
        # kubectl returns the multi-line agent-settings as an array of lines; join it so the match sees every line.
        $agentSettings = $agentSettings -join "`n"
        $agentSettings | Should -Match "ignore_proxy_settings"
        # ...and the pre-existing setting is preserved, proving nothing was overwritten.
        $agentSettings | Should -Match "high_log_scale"
        $agentSettings | Should -Match "enabled = false"
    }

    It 'Removes the proxy bypass on a later update that omits the Container Insights keyword' {
        # The previous test left behind a bypass written by this CLI, so this update must undo it.
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --proxy-skip-range 10.0.0.0/16
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the update reaches a succeeded provisioning state
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            Write-Host "Provisioning State: $provisioningState"
            if ($provisioningState -eq $SUCCEEDED) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        $agentSettings = kubectl get configmap container-azm-ms-agentconfig -n kube-system -o jsonpath='{.data.agent-settings}'
        $? | Should -BeTrue
        # kubectl returns the multi-line agent-settings as an array of lines; join it so the match sees every line.
        $agentSettings = $agentSettings -join "`n"
        # The setting goes away, and so does the header that was left holding nothing...
        $agentSettings | Should -Not -Match "ignore_proxy_settings"
        $agentSettings | Should -Not -Match "proxy_config"
        # ...while the setting the customer had before us is still there.
        $agentSettings | Should -Match "high_log_scale"

        # The annotation is dropped together with the setting it was tracking.
        $annotations = kubectl get configmap container-azm-ms-agentconfig -n kube-system -o jsonpath='{.metadata.annotations}'
        $annotations | Should -Not -Match "proxy-bypass"
    }

    It 'Leaves a Container Insights bypass that the customer set themselves in place' {
        # Pre-create a ConfigMap that already bypasses the proxy, with no annotation from this CLI.
        kubectl delete configmap container-azm-ms-agentconfig -n kube-system --ignore-not-found
        $manifest = @"
apiVersion: v1
kind: ConfigMap
metadata:
  name: container-azm-ms-agentconfig
  namespace: kube-system
data:
  schema-version: v1
  config-version: ver1
  agent-settings: |-
    [agent_settings.proxy_config]
      ignore_proxy_settings = "true"
"@
        $manifest | kubectl apply -f -
        $? | Should -BeTrue

        # The setting is already what we would write, so the CLI writes nothing and claims nothing.
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --proxy-skip-range Microsoft.AzureMonitor.Containers
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the update reaches a succeeded provisioning state
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            Write-Host "Provisioning State: $provisioningState"
            if ($provisioningState -eq $SUCCEEDED) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        # Nothing was claimed, so no annotation should have been added.
        $annotations = kubectl get configmap container-azm-ms-agentconfig -n kube-system -o jsonpath='{.metadata.annotations}'
        $annotations | Should -Not -Match "proxy-bypass"

        # A later update without the keyword must not remove a setting this CLI never wrote.
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --proxy-skip-range 10.0.0.0/16
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the update reaches a succeeded provisioning state
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            Write-Host "Provisioning State: $provisioningState"
            if ($provisioningState -eq $SUCCEEDED) {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        $agentSettings = kubectl get configmap container-azm-ms-agentconfig -n kube-system -o jsonpath='{.data.agent-settings}'
        $? | Should -BeTrue
        # kubectl returns the multi-line agent-settings as an array of lines; join it so the match sees every line.
        $agentSettings = $agentSettings -join "`n"
        $agentSettings | Should -Match "ignore_proxy_settings"
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