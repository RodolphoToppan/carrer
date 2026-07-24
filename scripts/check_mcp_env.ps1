$required = @(
    "AZURE_DEVOPS_ORG",
    "AZURE_DEVOPS_PROJECT",
    "AZURE_DEVOPS_EXT_PAT",
    "GITLAB_API_URL",
    "GITLAB_PERSONAL_ACCESS_TOKEN"
)

$failed = $false

foreach ($name in $required) {
    $value = [Environment]::GetEnvironmentVariable($name)

    if ([string]::IsNullOrWhiteSpace($value) -or $value -eq "replace-me") {
        Write-Output "$name=MISSING"
        $failed = $true
    }
    else {
        Write-Output "$name=SET(length=$($value.Length))"
    }
}

if ($failed) {
    exit 1
}

