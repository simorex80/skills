$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

function Find-Interpreter([string]$name) {
    Get-Command $name -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty Source
}

$executable = Find-Interpreter python
$prefix = @()
if (!$executable -or $executable -like '*\Microsoft\WindowsApps\python.exe') {
    $executable = Find-Interpreter py
    $prefix = @('-3')
}
if (!$executable) {
    throw 'Remote LLM Wiki requires Python 3.10+ on PATH (python or py).'
}

$arguments = $prefix + (Join-Path $PSScriptRoot 'wiki.py') + $args
if ($PSVersionTable.PSVersion -ge [version]'7.3') {
    $PSNativeCommandArgumentPassing = 'Standard'
} else {
    # Encode one quoted Windows command-line argument, even when it is empty.
    $arguments = foreach ($argument in $arguments) {
        $escaped = [regex]::Replace($argument, '(\\*)("|\z)', {
            param($match)
            $slashes = $match.Groups[1].Value
            $suffix = if ($match.Groups[2].Value -eq '"') { '\"' } else { '' }
            $slashes + $slashes + $suffix
        })
        '"' + $escaped + '"'
    }
}
& $executable @arguments
exit $LASTEXITCODE
