' frontstep-open.vbs — a console-free launcher for frontstep-open.ps1
'
' Why it exists: the registry cannot invoke powershell.exe directly, because
' powershell ALWAYS ALLOCATES A CONSOLE — even with -WindowStyle Hidden — and on
' Windows 11 that console is handed to the "default terminal". A Windows
' Terminal window appeared on every click, with its own configuration error on
' top of it. wscript.exe allocates no console at all.
'
' The URI travels in an ENVIRONMENT VARIABLE and not on the command line: that
' way it never crosses a shell parser, and there is no way to inject a command
' into it with a pair of quotes. The PowerShell script reads it from there.

Dim sh, env, script, command

Set sh = CreateObject("WScript.Shell")

' Where you put frontstep-open.ps1. Change it if you keep it elsewhere.
script = sh.ExpandEnvironmentStrings("%USERPROFILE%\bin\frontstep-open.ps1")

If WScript.Arguments.Count = 0 Then WScript.Quit 1

Set env = sh.Environment("Process")
env("FRONTSTEP_URI") = WScript.Arguments(0)

command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & _
          Chr(34) & script & Chr(34)

' 0 = hidden window, False = do not wait
sh.Run command, 0, False
