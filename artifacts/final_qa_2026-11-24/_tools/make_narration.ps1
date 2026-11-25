param(
  [Parameter(Mandatory=$true)][string]$TextFile,
  [Parameter(Mandatory=$true)][string]$OutFile,
  [Parameter(Mandatory=$true)][string]$Voice
)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice($Voice)
$s.Rate = 0
$s.Volume = 90
$text = Get-Content -Path $TextFile -Raw -Encoding UTF8
$s.SetOutputToWaveFile($OutFile)
$s.Speak($text)
$s.SetOutputToNull()
$s.Dispose()
Write-Output "NARRATION_OK $OutFile"
