. "$PSScriptRoot\machine_paths.ps1"
$taskVenvPython = $PinocchioRuntimePython
$taskRuntime = $PinocchioRuntime
$env:OLLAMA_MODELS = $PinocchioOllamaModels
$env:HF_HOME = "$taskRuntime\hf-cache"
$env:HF_HUB_OFFLINE = '1'
$env:OLLAMA_NUM_CTX = '2048'
$env:OLLAMA_NUM_PREDICT = '96'
$env:OLLAMA_KEEP_ALIVE = '30m'

Start-PinocchioOllama
Use-PinocchioVoiceGpu

& $taskVenvPython "$PSScriptRoot\voice_pipeline.py" @args
