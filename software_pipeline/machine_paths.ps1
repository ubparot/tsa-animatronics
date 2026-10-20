# Per-computer folder locations, shared by the PowerShell launchers.
# Mirrors machine_paths.py: each entry under "paths" in machine.json is either
# absolute or relative to "root". Dot-source this file: . "$PSScriptRoot\machine_paths.ps1"
$machineConfigPath = Join-Path $PSScriptRoot 'machine.json'
if (-not (Test-Path -LiteralPath $machineConfigPath)) {
    throw 'machine.json is missing. Copy machine.example.json to machine.json and set root for this computer.'
}
$machineConfig = Get-Content -LiteralPath $machineConfigPath -Raw | ConvertFrom-Json

function Resolve-MachinePath([string]$Value) {
    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }
    # Path.Combine, not Join-Path: Join-Path throws when the root's drive letter
    # does not exist yet (e.g. a template for another computer).
    return [System.IO.Path]::Combine($machineConfig.root, $Value)
}

$PinocchioRuntime = Resolve-MachinePath $machineConfig.paths.runtime
$PinocchioRvc = Resolve-MachinePath $machineConfig.paths.rvc
$PinocchioOllamaModels = Resolve-MachinePath $machineConfig.paths.ollama_models
$PinocchioVoiceTraining = Resolve-MachinePath $machineConfig.paths.voice_training
$PinocchioRuntimePython = [System.IO.Path]::Combine($PinocchioRuntime, 'venv\Scripts\python.exe')
$PinocchioOllama = Resolve-MachinePath $machineConfig.paths.ollama_exe
if (-not (Test-Path -LiteralPath $PinocchioOllama)) {
    # A standard Ollama install puts ollama.exe on PATH instead of under root.
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCommand) {
        $PinocchioOllama = $ollamaCommand.Source
    }
}

# Optional GPU split for a computer with two cards. machine.json "gpus" may name
# a "text" card (Ollama) and a "voice" card (Whisper + Chatterbox) by index,
# UUID, or part of the name, e.g. "2060" and "3070". Empty or missing means
# every process uses the default GPU, as on a single-GPU computer.
function Resolve-PinocchioGpu([string]$Role) {
    $selector = if ($machineConfig.gpus) { [string]$machineConfig.gpus.$Role } else { '' }
    if (-not $selector) {
        return $null
    }
    $cards = @(& nvidia-smi --query-gpu=index,uuid,name --format=csv,noheader 2>$null | ForEach-Object {
        $index, $uuid, $name = $_ -split ',\s*', 3
        [pscustomobject]@{ Index = $index; Uuid = $uuid; Name = $name }
    })
    $hits = @($cards | Where-Object {
        $_.Index -eq $selector -or $_.Uuid -eq $selector -or $_.Name -like "*$selector*"
    })
    if ($hits.Count -eq 1) {
        return $hits[0]
    }
    $found = ($cards | ForEach-Object { "$($_.Index): $($_.Name)" }) -join '; '
    if ($hits.Count -eq 0) {
        Write-Warning "machine.json gpus.$Role '$selector' matches no GPU ($found). Using the default GPU."
        return $null
    }
    throw "machine.json gpus.$Role '$selector' matches more than one GPU ($found). Use the index or UUID."
}

$PinocchioTextGpu = Resolve-PinocchioGpu 'text'
$PinocchioVoiceGpu = Resolve-PinocchioGpu 'voice'

function Test-PinocchioOllama {
    # A plain TCP connect, not Invoke-WebRequest: in a fresh Windows PowerShell
    # process Invoke-WebRequest can stall on proxy auto-detection well past its
    # -TimeoutSec, which froze the launchers before Python ever started.
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        return $client.ConnectAsync('127.0.0.1', 11434).Wait(1000) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Start-PinocchioOllama {
    if (Test-PinocchioOllama) {
        if ($PinocchioTextGpu) {
            # CUDA_VISIBLE_DEVICES is read once when Ollama starts.
            Write-Warning ("Ollama was already running, so it was not pinned to the $($PinocchioTextGpu.Name). " +
                'Quit Ollama (including its tray icon) and relaunch to apply the GPU split.')
        }
        return
    }
    $previous = $env:CUDA_VISIBLE_DEVICES
    if ($PinocchioTextGpu) {
        $env:CUDA_VISIBLE_DEVICES = $PinocchioTextGpu.Uuid
        Write-Host "Text model GPU: $($PinocchioTextGpu.Name)"
    }
    Start-Process -FilePath $PinocchioOllama -ArgumentList 'serve' -WindowStyle Hidden
    $env:CUDA_VISIBLE_DEVICES = $previous
    Start-Sleep -Seconds 3
}

# Call after Start-PinocchioOllama, just before launching the voice process.
function Use-PinocchioVoiceGpu {
    if ($PinocchioVoiceGpu) {
        $env:CUDA_VISIBLE_DEVICES = $PinocchioVoiceGpu.Uuid
        Write-Host "Voice GPU: $($PinocchioVoiceGpu.Name)"
    }
}
