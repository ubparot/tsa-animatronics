. "$PSScriptRoot\machine_paths.ps1"
$taskRuntime = $PinocchioRuntime
$taskVenvPython = "$taskRuntime\venv\Scripts\python.exe"
$env:TEMP = "$taskRuntime\temp"
$env:TMP = "$taskRuntime\temp"
$env:PIP_CACHE_DIR = "$taskRuntime\pip-cache"

if (-not (Test-Path -LiteralPath $taskVenvPython)) {
    throw 'Voice environment missing. Run setup_voice_pipeline.ps1 first.'
}

New-Item -ItemType Directory -Force -Path $env:TEMP, $env:PIP_CACHE_DIR | Out-Null
& $taskVenvPython -m pip install --force-reinstall --no-cache-dir 'torch==2.11.0+cu128' 'torchaudio==2.11.0+cu128' --index-url https://download.pytorch.org/whl/cu128
& $taskVenvPython -c "import torch, torchaudio; assert torch.cuda.is_available(); print('GPU ready: ' + torch.cuda.get_device_name(0)); print('TorchAudio: ' + torchaudio.__version__)"
