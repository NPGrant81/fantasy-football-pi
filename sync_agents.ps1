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
$AgentFileNamePattern = '^[A-Za-z0-9][A-Za-z0-9._-]*\.agent\.md$'

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
    if (-not (Test-Path -LiteralPath $Path)) {
        Fail "Lock file not found: $Path"
    }

    try {
        return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    }
    catch {
        Fail "Lock file is not valid JSON: $Path"
    }
}

function Assert-AgentFileName([string]$AgentFile) {
    if ([string]::IsNullOrWhiteSpace($AgentFile)) {
        Fail "managedAgents entries must be non-empty strings"
    }

    if ($AgentFile -notmatch $AgentFileNamePattern) {
        Fail "managedAgents entry is not a valid simple .agent.md filename: $AgentFile"
    }

    if ($AgentFile.Contains("/") -or $AgentFile.Contains("\\") -or $AgentFile.Contains("..")) {
        Fail "managedAgents entry must not include path traversal or separators: $AgentFile"
    }
}

function Get-UnmanagedAgentFiles($Lock, [string]$ManagedDir) {
    $managed = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($agentFile in $Lock.managedAgents) {
        $null = $managed.Add([string]$agentFile)
    }

    $unmanaged = New-Object System.Collections.Generic.List[string]
    if (-not (Test-Path -LiteralPath $ManagedDir)) {
        return $unmanaged
    }

    $existing = Get-ChildItem -LiteralPath $ManagedDir -File -Filter "*.agent.md"
    foreach ($item in $existing) {
        if (-not $managed.Contains($item.Name)) {
            $unmanaged.Add($item.FullName)
        }
    }

    return $unmanaged
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

    if ($Lock.ref -ne "v0.2.1") {
        Fail "Unexpected ref in lock file: $($Lock.ref)"
    }

    if (-not ($Lock.managedAgents -is [System.Collections.IEnumerable])) {
        Fail "managedAgents must be an array"
    }
}

function Assert-SyncPrereqs($Lock, [string]$CatalogPath) {
    if (-not (Test-Path -LiteralPath $CatalogPath)) {
        Fail "Catalog agents path not found: $CatalogPath"
    }

    foreach ($agentFile in $Lock.managedAgents) {
        if (-not ($agentFile -is [string])) {
            Fail "managedAgents entries must be strings"
        }

        Assert-AgentFileName -AgentFile $agentFile

        $sourcePath = Join-Path $CatalogPath $agentFile
        if (-not (Test-Path -LiteralPath $sourcePath)) {
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
    $unmanaged = Get-UnmanagedAgentFiles -Lock $lock -ManagedDir $AgentsDir
    if ($unmanaged.Count -gt 0) {
        Write-Output "check mode: unmanaged .agent.md files found under .github/agents"
        foreach ($path in $unmanaged) {
            Write-Output "- $path"
        }
        exit 1
    }

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

if (-not (Test-Path -LiteralPath $AgentsDir)) {
    New-Item -ItemType Directory -Path $AgentsDir -Force | Out-Null
}

$removed = New-Object System.Collections.Generic.List[string]
$unmanaged = Get-UnmanagedAgentFiles -Lock $lock -ManagedDir $AgentsDir
foreach ($path in $unmanaged) {
    if ($PSCmdlet.ShouldProcess($path, "Remove unmanaged agent payload")) {
        Remove-Item -LiteralPath $path -Force
    }

    $removed.Add($path)
}

$synced = New-Object System.Collections.Generic.List[string]

foreach ($agentFile in $lock.managedAgents) {
    $sourcePath = Join-Path $CatalogAgentsDir $agentFile
    $targetPath = Join-Path $AgentsDir $agentFile

    if ($PSCmdlet.ShouldProcess($targetPath, "Copy managed agent payload from catalog")) {
        Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
    }

    $synced.Add($agentFile)
}

Write-Output "sync complete"
Write-Output "source repo: $($lock.sourceRepo)@$($lock.ref)"
Write-Output "removed unmanaged agents: $($removed.Count)"
foreach ($path in $removed) {
    Write-Output "- removed: $path"
}
Write-Output "synced managed agents: $($synced.Count)"
foreach ($agentFile in $synced) {
    Write-Output "- $agentFile"
}
