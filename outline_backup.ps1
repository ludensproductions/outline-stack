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

$Timestamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot  = ".\backups"
$WorkDir     = Join-Path $BackupRoot "${OutlineVolume}_${Timestamp}"
$ArchivePath = [System.IO.Path]::GetFullPath((Join-Path $BackupRoot "${OutlineVolume}_${Timestamp}.tar.gz"))
$StageDir    = $null

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

try {
    # 1. Dump DB — Start-Process preserves binary stdout without PowerShell encoding it
    Write-Host "Dumping database..."
    $DumpPath    = Join-Path $WorkDir "outline_db.dump"
    $DumpErrPath = [System.IO.Path]::GetTempFileName()

    $proc = Start-Process "docker" `
        -ArgumentList @("compose", "exec", "-T", "postgres", "pg_dump",
                        "-U", $SqlUser, "-d", $SqlDbName, "-F", "c", "-Z", "9") `
        -RedirectStandardOutput $DumpPath `
        -RedirectStandardError  $DumpErrPath `
        -NoNewWindow -Wait -PassThru

    if ($proc.ExitCode -ne 0) {
        $errMsg = Get-Content $DumpErrPath -Raw
        throw "DB dump failed: $errMsg"
    }
    Remove-Item $DumpErrPath -ErrorAction SilentlyContinue

    if ((Get-Item $DumpPath).Length -eq 0) {
        throw "DB dump is empty (silent failure)"
    }

    # 2. Copy volume
    Write-Host "Copying volume: $OutlineVolume"
    $WorkDirAbs = [System.IO.Path]::GetFullPath($WorkDir)
    docker run --rm `
        -v "${OutlineVolume}:/volume-data:ro" `
        -v "${WorkDirAbs}:/backup-data" `
        busybox `
        sh -c "cp -a /volume-data/. /backup-data/ 2>/dev/null || true"
    if ($LASTEXITCODE -ne 0) { throw "Volume copy failed with exit code $LASTEXITCODE" }

    # 3. Create archive with db/ and media/ structure expected by restore
    Write-Host "Creating archive: $ArchivePath"
    $StageDir = Join-Path $env:TEMP ([System.IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Force -Path (Join-Path $StageDir "db")    | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $StageDir "media") | Out-Null

    Move-Item -Path $DumpPath -Destination (Join-Path $StageDir "db\outline_db.dump")

    Get-ChildItem -Path $WorkDir | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination (Join-Path $StageDir "media") -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
    tar -czf $ArchivePath -C $StageDir .
    if ($LASTEXITCODE -ne 0) { throw "tar failed with exit code $LASTEXITCODE" }

    Write-Host "Archive created: $ArchivePath"

    # 4. Upload via SFTP
    Write-Host "Uploading to SFTP..."
    python sftp_backup.py --archive-path $ArchivePath
    if ($LASTEXITCODE -ne 0) { throw "SFTP upload failed with exit code $LASTEXITCODE" }

    Write-Host "Backup completed successfully."
} finally {
    Write-Host "Cleaning up..."
    if (Test-Path $WorkDir) {
        Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue
    }
    if ($StageDir -and (Test-Path $StageDir)) {
        Remove-Item -Recurse -Force $StageDir -ErrorAction SilentlyContinue
    }
}
