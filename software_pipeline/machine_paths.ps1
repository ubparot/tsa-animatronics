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
