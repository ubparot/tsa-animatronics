. "$PSScriptRoot\machine_paths.ps1"
$taskModels = $PinocchioOllamaModels
$env:OLLAMA_MODELS = $taskModels
$env:OLLAMA_NUM_CTX = '2048'
$env:OLLAMA_NUM_PREDICT = '96'
$env:OLLAMA_KEEP_ALIVE = '30m'

Start-PinocchioOllama

& python "$PSScriptRoot\pipeline.py" --model pinocchio-fast @args
