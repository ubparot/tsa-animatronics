. "$PSScriptRoot\machine_paths.ps1"
$taskRuntime = $PinocchioRuntime
$taskEnvironment = Join-Path $PinocchioRuntime 'venv'
$env:TEMP = "$taskRuntime\temp"
$env:TMP = "$taskRuntime\temp"
$env:PIP_CACHE_DIR = "$taskRuntime\pip-cache"
$env:HF_HOME = "$taskRuntime\hf-cache"
$env:HF_HUB_OFFLINE = '0'

New-Item -ItemType Directory -Force -Path $env:TEMP, $env:PIP_CACHE_DIR, $env:HF_HOME, "$taskRuntime\voices" | Out-Null
if (-not (Test-Path -LiteralPath "$taskEnvironment\Scripts\python.exe")) {
    if ($machineConfig.base_python) {
        & $machineConfig.base_python -m venv $taskEnvironment
    } else {
        # The voice stack is pinned to Python 3.10; the py launcher finds it without a hard-coded path.
        & py -3.10 -m venv $taskEnvironment
    }
}

$taskVenvPython = "$taskEnvironment\Scripts\python.exe"
& $taskVenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip.' }
& $taskVenvPython -m pip install --upgrade 'torch==2.11.0+cu128' 'torchaudio==2.11.0+cu128' --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw 'Could not install the CUDA PyTorch packages.' }
& $taskVenvPython -m pip install -r "$PSScriptRoot\requirements-voice.txt"
if ($LASTEXITCODE -ne 0) { throw 'Could not install the voice dependencies.' }
& $taskVenvPython -m pip install --no-deps 'chatterbox-tts==0.1.7'
if ($LASTEXITCODE -ne 0) { throw 'Could not install Chatterbox.' }
& $taskVenvPython "$PSScriptRoot\warmup_chatterbox.py" --output "$taskRuntime\chatterbox_warmup.wav"
if ($LASTEXITCODE -ne 0) { throw 'Chatterbox installed but failed its generation smoke test.' }
