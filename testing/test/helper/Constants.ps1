$ENVCONFIG = Get-Content -Path $PSScriptRoot/../../settings.json | ConvertFrom-Json

$MAX_RETRY_ATTEMPTS = 30
$ARC_LOCATION = "uksouth"
$BUNDLE_FEATURE_TEST_ARC_LOCATION = "eastus"
$SUCCEEDED = "Succeeded"