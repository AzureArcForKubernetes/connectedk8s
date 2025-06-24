Describe 'Setting Bundle Feature Flag Scenario' {
    BeforeAll {
        . $PSScriptRoot/../helper/Constants.ps1
    }

    It 'Enable the bundle feature flag when connecting the cluster to Arc' {
        $output = & {
            az connectedk8s connect -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup -l $BUNDLE_FEATURE_TEST_ARC_LOCATION `
                --disable-auto-upgrade --config extensionSets.versionManagedExtensions='off' 2>&1 | Out-String
        }
        $output | Should -Match "Not supported value for the feature flag"

        $output = & {
            az connectedk8s connect -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup -l $BUNDLE_FEATURE_TEST_ARC_LOCATION `
                --disable-auto-upgrade --config extensionSets.versionManagedExtensions='disabled' 2>&1 | Out-String
        }
        $output | Should -Match "'disabled' mode can only be set using 'az connectedk8s update'"

        az connectedk8s connect -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup -l $BUNDLE_FEATURE_TEST_ARC_LOCATION `
            --disable-auto-upgrade --config extensionSets.versionManagedExtensions='preview' --no-wait --yes
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $jsonOutput = [System.Text.Json.JsonDocument]::Parse($output)
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            $bundleFeatureFlag = $jsonOutput.RootElement.GetProperty("arcAgentryConfigurations")[0].GetProperty("settings").GetProperty("versionManagedExtensions").GetString()
            Write-Host "Provisioning State: $provisioningState"
            Write-Host "Bundle Feature Flag: $bundleFeatureFlag"
            if ($provisioningState -eq $SUCCEEDED -and $bundleFeatureFlag -eq "preview")
            {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        $output = & {
            az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --auto-upgrade false `
                --config extensionSets.versionManagedExtensions='enabled' 2>&1 | Out-String
        }
        $output | Should -Match "The cluster is in versionManagedExtensions 'preview' mode, updating the value is not allowed."

        az connectedk8s delete -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --force -y
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        az connectedk8s connect -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup -l $BUNDLE_FEATURE_TEST_ARC_LOCATION `
            --disable-auto-upgrade --config extensionSets.versionManagedExtensions='enabled' --no-wait
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $jsonOutput = [System.Text.Json.JsonDocument]::Parse($output)
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            $bundleFeatureFlag = $jsonOutput.RootElement.GetProperty("arcAgentryConfigurations")[0].GetProperty("settings").GetProperty("versionManagedExtensions").GetString()
            Write-Host "Provisioning State: $provisioningState"
            Write-Host "Bundle Feature Flag: $bundleFeatureFlag"
            if ($provisioningState -eq $SUCCEEDED -and $bundleFeatureFlag -eq "enabled")
            {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS
    }

    It 'Enable the bundle feature flag using update cmd' {
        $output = & {
            az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --auto-upgrade false `
                --config extensionSets.versionManagedExtensions='on' 2>&1 | Out-String
        }
        $output | Should -Match "Not supported value for the feature flag"

        $output = & {
            az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --auto-upgrade false `
                --config extensionSets.versionManagedExtensions='preview' 2>&1 | Out-String
        }
        $output | Should -Match "Updating the preview mode config with 'az connectedk8s update' is not allowed"

        $output = & {
            az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --auto-upgrade false `
                --config extensionSets.versionManagedExtensions='' 2>&1 | Out-String
        }
        $output | Should -Match "Could not set extensionSets.versionManagedExtensions from 'enabled' to ''"

        az k8s-extension create --cluster-name $ENVCONFIG.arcClusterName --resource-group $ENVCONFIG.resourceGroup `
            --cluster-type connectedClusters --extension-type microsoft.iotoperations.platform `
            --name azure-iot-operations-platform --release-train preview --auto-upgrade-minor-version False `
            --config installTrustManager=true --config installCertManager=true --version 0.7.6 `
            --release-namespace cert-manager --scope cluster
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        az k8s-extension create --cluster-name $ENVCONFIG.arcClusterName --resource-group $ENVCONFIG.resourceGroup `
            --cluster-type connectedClusters --extension-type microsoft.azure.secretstore `
            --name azure-secret-store --auto-upgrade-minor-version False `
            --config rotationPollIntervalInSeconds=120 --config validatingAdmissionPolicies.applyPolicies=false `
            --scope cluster
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        $output = & {
            az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --auto-upgrade false `
                --config extensionSets.versionManagedExtensions='disabled' 2>&1 | Out-String
        }
        $output | Should -Match "detected the following extension types on the cluster"

        az k8s-extension delete --cluster-name $ENVCONFIG.arcClusterName --resource-group $ENVCONFIG.resourceGroup `
            --cluster-type connectedClusters --name azure-secret-store --yes
        $? | Should -BeTrue

        az k8s-extension delete --cluster-name $ENVCONFIG.arcClusterName --resource-group $ENVCONFIG.resourceGroup `
            --cluster-type connectedClusters --name azure-iot-operations-platform --yes
        $? | Should -BeTrue

        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --auto-upgrade false `
            --config extensionSets.versionManagedExtensions='disabled'
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $jsonOutput = [System.Text.Json.JsonDocument]::Parse($output)
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            $bundleFeatureFlag = $jsonOutput.RootElement.GetProperty("arcAgentryConfigurations")[0].GetProperty("settings").GetProperty("versionManagedExtensions").GetString()
            Write-Host "Provisioning State: $provisioningState"
            Write-Host "Bundle Feature Flag: $bundleFeatureFlag"
            if ($provisioningState -eq $SUCCEEDED -and $bundleFeatureFlag -eq "disabled")
            {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS
    }

    It "Verify the error message when failing to upgrade the agent with bundle feature flag enabled" {
        az connectedk8s update -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --auto-upgrade false `
            --config extensionSets.versionManagedExtensions='enabled'
        $? | Should -BeTrue
        Start-Sleep -Seconds 10

        # Loop and retry until the configuration installs
        $n = 0
        do 
        {
            $output = az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
            $jsonOutput = [System.Text.Json.JsonDocument]::Parse($output)
            $provisioningState = ($output | ConvertFrom-Json).provisioningState
            $bundleFeatureFlag = $jsonOutput.RootElement.GetProperty("arcAgentryConfigurations")[0].GetProperty("settings").GetProperty("versionManagedExtensions").GetString()
            Write-Host "Provisioning State: $provisioningState"
            Write-Host "Bundle Feature Flag: $bundleFeatureFlag"
            if ($provisioningState -eq $SUCCEEDED -and $bundleFeatureFlag -eq "enabled")
            {
                break
            }
            Start-Sleep -Seconds 10
            $n += 1
        } while ($n -le $MAX_RETRY_ATTEMPTS)
        $n | Should -BeLessOrEqual $MAX_RETRY_ATTEMPTS

        $ns = "azure-arc"
        $rootDir = Resolve-Path "$PSScriptRoot/../../../"

        $configDir = Join-Path $rootDir "src/connectedk8s/azext_connectedk8s/tests/latest/agent_update_validator_test_config"
        $arcAgentValuesPath = Join-Path $configDir "ArcAgentryValues.json"
        $fakeExtConfigPath = Join-Path $configDir "fake_ext_config.yml"

        $tmpDir = Join-Path $rootDir "testing/tmp"

        if (-not (Test-Path $tmpDir)) {
            New-Item -ItemType Directory -Path $tmpDir | Out-Null
        }

        # Update lastSyncTime in fake_ext_config.yml
        $updatedFakeExtConfigPath = Join-Path $tmpDir "fake_ext_config_updated.yml"
        $data = Get-Content $fakeExtConfigPath | ConvertFrom-Yaml
        $data.status.syncStatus.lastSyncTime = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss.000Z")
        $data | ConvertTo-Yaml | Set-Content $updatedFakeExtConfigPath

        # Create the fake extension config to simulate an extension that depends on the bundle
        kubectl apply -f $updatedFakeExtConfigPath --namespace $ns
        $? | Should -BeTrue

        $ENV:HELMVALUESPATH = $arcAgentValuesPath

        $output = & {
            az connectedk8s upgrade -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --agent-version "1.26.0" 2>&1 | Out-String
        }
        $output | Should -Match "Error: Failed to validate agent update.*no such host"

        $env:HELMVALUESPATH = ""

        # Remove the finalizers from the fake extension config to allow deletion
        kubectl patch extensionconfig fake-ext-config --namespace $ns --type=json -p '[{"op": "remove", "path": "/metadata/finalizers"}]'

        Start-Process kubectl -ArgumentList "delete extensionconfig fake-ext-config --namespace $ns" -NoNewWindow

        Start-Sleep -Seconds 60

        kubectl get extensionconfig fake-ext-config --namespace $ns 2>&1
        $? | Should -BeFalse
    }

    It "Delete the connected instance" {
        az connectedk8s delete -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup --force -y
        $? | Should -BeTrue

        # Configuration should be removed from the resource model
        az connectedk8s show -n $ENVCONFIG.arcClusterName -g $ENVCONFIG.resourceGroup
        $? | Should -BeFalse
    }
}