$ENVCONFIG = Get-Content -Path $PSScriptRoot/../../settings.json | ConvertFrom-Json

$MAX_RETRY_ATTEMPTS = 30