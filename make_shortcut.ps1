$P = "$PSScriptRoot\launch_prefire.cmd"
$S = "$([Environment]::GetFolderPath('Desktop'))\Prefire.lnk"
$I = "$PSScriptRoot\prefire.ico"

$WScript = New-Object -ComObject WScript.Shell
$Shortcut = $WScript.CreateShortcut($S)
$Shortcut.TargetPath  = $P
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.IconLocation = $I
$Shortcut.Save()
