[CmdletBinding()]
param()

# Run from the project root alongside sftp_backup.py

$ErrorActionPreference = "Stop"

if (Test-Path ".env") {
    Get-Content ".env" | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
        $parts = $_ -split '=', 2
        $name  = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

$OutlineVolume = $env:OUTLINE_VOLUME
$SqlUser       = $env:SQL_USER
$SqlDbName     = $env:SQL_DBNAME

if (-not $OutlineVolume) { throw "OUTLINE_VOLUME is required" }
if (-not $SqlUser)       { throw "SQL_USER is required" }
if (-not $SqlDbName)     { throw "SQL_DBNAME is required" }

$TempDir     = $null
$ArchivePath = $null

try {
    # 1. Download latest backup from SFTP (progress goes to stderr, path to stdout)
    Write-Host "Downloading latest backup..."
    $ArchivePath = python sftp_backup.py --download
    if ($LASTEXITCODE -ne 0) { throw "Download failed with exit code $LASTEXITCODE" }
    Write-Host "Downloaded: $ArchivePath"

    # 2. Extract archive
    $TempDir = Join-Path $env:TEMP "restore_$([System.IO.Path]::GetRandomFileName())"
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

    Write-Host "Extracting backup from $ArchivePath..."
    tar -xzf $ArchivePath -C $TempDir
    if ($LASTEXITCODE -ne 0) { throw "tar extraction failed with exit code $LASTEXITCODE" }

    $MediaDir = Join-Path $TempDir "media"
    $DbDump   = Join-Path $TempDir "db\outline_db.dump"

    if (-not (Test-Path $MediaDir)) { throw "Missing media directory in backup" }
    if (-not (Test-Path $DbDump))   { throw "Missing database dump in backup" }

    # 3. Restore media volume (clean + copy)
    Write-Host "Restoring media volume (clean overwrite)..."
    $MediaDirAbs = [System.IO.Path]::GetFullPath($MediaDir)
    docker run --rm `
        -v "${OutlineVolume}:/volume-data" `
        -v "${MediaDirAbs}:/restore-data:ro" `
        busybox `
        sh -c "rm -rf /volume-data/* && cp -a /restore-data/. /volume-data/"
    if ($LASTEXITCODE -ne 0) { throw "Volume restore failed with exit code $LASTEXITCODE" }

    # 4. Restore database — Start-Process preserves binary stdin without PowerShell encoding it
    Write-Host "Restoring database..."
    $RestoreErrPath = [System.IO.Path]::GetTempFileName()

    $proc = Start-Process "docker" `
        -ArgumentList @("compose", "exec", "-T", "postgres", "pg_restore",
                        "-U", $SqlUser, "-d", $SqlDbName, "--clean", "--if-exists") `
        -RedirectStandardInput $DbDump `
        -RedirectStandardError $RestoreErrPath `
        -NoNewWindow -Wait -PassThru

    if ($proc.ExitCode -ne 0) {
        $errMsg = Get-Content $RestoreErrPath -Raw
        throw "DB restore failed: $errMsg"
    }
    Remove-Item $RestoreErrPath -ErrorAction SilentlyContinue

    # Cleanup downloaded archive (only reached on success)
    Remove-Item $ArchivePath -ErrorAction SilentlyContinue

    Write-Host "Restore completed."
} finally {
    Write-Host "Cleaning up..."
    if ($TempDir -and (Test-Path $TempDir)) {
        Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
    }
}
