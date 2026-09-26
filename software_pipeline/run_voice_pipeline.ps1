. "$PSScriptRoot\machine_paths.ps1"
$taskOllama = $PinocchioOllama
$taskVenvPython = $PinocchioRuntimePython
$taskRuntime = $PinocchioRuntime
$env:OLLAMA_MODELS = $PinocchioOllamaModels
$env:HF_HOME = "$taskRuntime\hf-cache"
$env:HF_HUB_OFFLINE = '1'
$env:OLLAMA_NUM_CTX = '2048'
$env:OLLAMA_NUM_PREDICT = '96'
$env:OLLAMA_KEEP_ALIVE = '30m'

try {
    Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri 'http://127.0.0.1:11434/api/tags' | Out-Null
} catch {
    Start-Process -FilePath $taskOllama -ArgumentList 'serve' -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

& $taskVenvPython "$PSScriptRoot\voice_pipeline.py" @args
