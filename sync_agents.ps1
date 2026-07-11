[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Check,
    [string]$LockFile = "agent_catalog.lock.json",
    [string]$CatalogRoot = ""
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LockPath = Join-Path $RootDir $LockFile
$AgentsDir = Join-Path $RootDir ".github/agents"

if ([string]::IsNullOrWhiteSpace($CatalogRoot)) {
    $DevDir = Split-Path -Parent (Split-Path -Parent $RootDir)
    $CatalogRoot = Join-Path $DevDir "agent-catalog"
}

$CatalogAgentsDir = Join-Path $CatalogRoot "agents"

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

function Read-LockFile([string]$Path) {
    if (-not (Test-Path $Path)) {
        Fail "Lock file not found: $Path"
    }

    try {
        return Get-Content -Path $Path -Raw | ConvertFrom-Json
    }
    catch {
        Fail "Lock file is not valid JSON: $Path"
    }
}

function Assert-LockShape($Lock) {
    $required = @(
        "schemaVersion",
        "sourceRepo",
        "ref",
        "deferred",
        "enabled",
        "managedAgents",
        "notes"
    )

    foreach ($key in $required) {
        if (-not ($Lock.PSObject.Properties.Name -contains $key)) {
            Fail "Lock file missing required key: $key"
        }
    }

    if ($Lock.sourceRepo -ne "NPGrant81/agent-catalog") {
        Fail "Unexpected sourceRepo in lock file: $($Lock.sourceRepo)"
    }

    if ($Lock.ref -ne "v0.1.0") {
        Fail "Unexpected ref in lock file: $($Lock.ref)"
    }

    if (-not ($Lock.managedAgents -is [System.Collections.IEnumerable])) {
        Fail "managedAgents must be an array"
    }
}

function Assert-SyncPrereqs($Lock, [string]$CatalogPath) {
    if (-not (Test-Path $CatalogPath)) {
        Fail "Catalog agents path not found: $CatalogPath"
    }

    foreach ($agentFile in $Lock.managedAgents) {
        if (-not ($agentFile -is [string]) -or [string]::IsNullOrWhiteSpace($agentFile)) {
            Fail "managedAgents entries must be non-empty strings"
        }

        if (-not $agentFile.EndsWith(".agent.md")) {
            Fail "managedAgents entry must end with .agent.md: $agentFile"
        }

        $sourcePath = Join-Path $CatalogPath $agentFile
        if (-not (Test-Path $sourcePath)) {
            Fail "Managed agent payload not found in catalog: $sourcePath"
        }
    }
}

$lock = Read-LockFile -Path $LockPath
Assert-LockShape -Lock $lock

$isCheckMode = $Check -or $WhatIfPreference

$isDeferred = [bool]$lock.deferred
$isEnabled = [bool]$lock.enabled

if ($isCheckMode) {
    if ($isDeferred -or -not $isEnabled) {
        Write-Output "bootstrapped, sync deferred"
        Write-Output "check mode: validated lock file and deferred-sync configuration"
        exit 0
    }

    Assert-SyncPrereqs -Lock $lock -CatalogPath $CatalogAgentsDir
    Write-Output "check mode: validated lock file and non-deferred sync prerequisites"
    exit 0
}

if ($isDeferred -or -not $isEnabled) {
    Write-Output "bootstrapped, sync deferred"
    Write-Output "source repo: $($lock.sourceRepo)@$($lock.ref)"
    Write-Output "managed agents declared: $($lock.managedAgents.Count)"
    Write-Output "first real sync pending source availability and approval"
    exit 0
}

Assert-SyncPrereqs -Lock $lock -CatalogPath $CatalogAgentsDir

if (-not (Test-Path $AgentsDir)) {
    New-Item -ItemType Directory -Path $AgentsDir -Force | Out-Null
}

$synced = New-Object System.Collections.Generic.List[string]

foreach ($agentFile in $lock.managedAgents) {
    $sourcePath = Join-Path $CatalogAgentsDir $agentFile
    $targetPath = Join-Path $AgentsDir $agentFile

    if ($PSCmdlet.ShouldProcess($targetPath, "Copy managed agent payload from catalog")) {
        Copy-Item -Path $sourcePath -Destination $targetPath -Force
    }

    $synced.Add($agentFile)
}

Write-Output "sync complete"
Write-Output "source repo: $($lock.sourceRepo)@$($lock.ref)"
Write-Output "synced managed agents: $($synced.Count)"
foreach ($agentFile in $synced) {
    Write-Output "- $agentFile"
}
