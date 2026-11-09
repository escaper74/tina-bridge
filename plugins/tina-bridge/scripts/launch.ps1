$ErrorActionPreference = 'Stop'
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
[Console]::InputEncoding = $OutputEncoding
[Console]::OutputEncoding = $OutputEncoding
$pluginRoot = Split-Path -Parent $PSScriptRoot
$tinaLocalData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { [Environment]::GetFolderPath('LocalApplicationData') }
$tinaData = Join-Path $tinaLocalData 'TinaBridge'
$tinaConfig = if ($env:TINA_CONFIG) { $env:TINA_CONFIG } else { Join-Path $tinaData 'settings.json' }
$tinaConfig = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($tinaConfig))
$tinaSettings = if (Test-Path -LiteralPath $tinaConfig) { Get-Content -LiteralPath $tinaConfig -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
$tinaPython = if ($env:TINA_PYTHON) { $env:TINA_PYTHON } elseif ($tinaSettings -and $tinaSettings.python) { $tinaSettings.python } else { Join-Path $tinaData 'venv/Scripts/python.exe' }
$tinaPython = [Environment]::ExpandEnvironmentVariables($tinaPython)
if (-not [IO.Path]::IsPathRooted($tinaPython)) { $tinaPython = Join-Path (Split-Path -Parent $tinaConfig) $tinaPython }
if (-not (Test-Path -LiteralPath $tinaPython -PathType Leaf)) {
    [Console]::Error.WriteLine('TINA Bridge runtime is not installed. Run setup.py from the plugin folder first.')
    exit 1
}
& $tinaPython -X utf8 (Join-Path $pluginRoot 'server/mcp_entry.py')
exit $LASTEXITCODE
