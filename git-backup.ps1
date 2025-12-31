# Stop on errors (similar to set -e)
$ErrorActionPreference = "Stop"

# Load variables from .env
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') {
        return
    }

    $name, $value = $_ -split '=', 2
    $value = $value.Trim('"')
    [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
}

# Run pg_dump via docker compose
docker compose exec -T postgres `
  pg_dump -U $env:SQL_USER -d $env:SQL_DBNAME -F c -Z 9 `
  > outline.dump
