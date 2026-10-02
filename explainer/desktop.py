"""Open the Windows folder/file picker on the local desktop."""
import base64
import json
import os
import subprocess
import threading
import shutil

_picker_lock = threading.Lock()

def pick(kind):
    if os.name != 'nt': raise ValueError('Native picking is available on Windows; enter a source path instead')
    if not _picker_lock.acquire(blocking=False): raise ValueError('A file picker is already open')
    try:
        dialog = ('$dialog=New-Object System.Windows.Forms.FolderBrowserDialog; '
                  '$dialog.Description="Choose a folder"; $dialog.ShowNewFolderButton=$true; '
                  'if($dialog.PSObject.Properties["AutoUpgradeEnabled"]){$dialog.AutoUpgradeEnabled=$true}; '
                  '$property="SelectedPath"') if kind == 'folder' else (
                  '$dialog=New-Object System.Windows.Forms.OpenFileDialog; $dialog.Multiselect=$true; '
                  '$dialog.Title="Choose lesson sources"; $property="FileNames"')
        script = ('$ErrorActionPreference="Stop"; [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false); '
                  'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::EnableVisualStyles(); '
                  '$owner=New-Object System.Windows.Forms.Form; $owner.TopMost=$true; '
                  + dialog + '; if($dialog.ShowDialog($owner) -eq "OK") {'
                  '@{paths=@($dialog.$property)} | ConvertTo-Json -Compress'
                  '} else { \'{"paths":[]}\' }; $dialog.Dispose(); $owner.Dispose()')
        encoded = base64.b64encode(script.encode('utf-16le')).decode()
        result = subprocess.run([shutil.which('pwsh') or 'powershell.exe', '-NoProfile', '-STA', '-WindowStyle', 'Hidden', '-EncodedCommand', encoded],
                                capture_output=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode: raise ValueError('The native picker could not open; enter the path instead')
        return json.loads(result.stdout.decode('utf-8-sig', errors='replace'))
    except subprocess.TimeoutExpired:
        raise ValueError('The file picker timed out')
    finally: _picker_lock.release()
