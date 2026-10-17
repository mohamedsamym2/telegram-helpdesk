Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
Set colProcesses = objWMIService.ExecQuery("Select * from Win32_Process Where Name = 'ITSupportHelpdesk.exe'")

If colProcesses.Count = 0 Then
    Set objProcess = objWMIService.Get("Win32_Process")
    exePath = scriptDir & "\ITSupportHelpdesk.exe"
    intReturn = objProcess.Create(exePath, scriptDir, Null, intProcessID)
End If
