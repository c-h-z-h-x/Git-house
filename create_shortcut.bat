@echo off
:: 为 start.bat 创建桌面快捷方式（带自定义图标）
:: 以管理员身份运行一次即可

set TARGET=%~dp0start.bat
set ICON=%%SystemRoot%%\System32\imageres.dll
set ICON_INDEX=94

set SHORTCUT=%USERPROFILE%\Desktop\Git-house.lnk

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$ws = New-Object -ComObject WScript.Shell;" ^
"$sc = $ws.CreateShortcut('%SHORTCUT%');" ^
"$sc.TargetPath = '%TARGET%';" ^
"$sc.WorkingDirectory = '%~dp0';" ^
"$sc.Description = '复习资料助手 - 一键启动';" ^
"$sc.IconLocation = '%ICON%, %ICON_INDEX%';" ^
"$sc.Save();"

echo 快捷方式已创建到桌面：Git-house.lnk
pause
