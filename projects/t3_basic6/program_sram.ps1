param(
    [Parameter(Mandatory = $true)][string]$BitPath
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$bit = (Resolve-Path -LiteralPath $BitPath).Path
if ([IO.Path]::GetExtension($bit) -ne '.bit') {
    throw "Expected a .bit file: $bit"
}
$tdBin = 'E:\qianrufpga\TD\bin'
$server = Get-Process -Name hwserver -ErrorAction SilentlyContinue
if (-not $server) {
    Start-Process -FilePath (Join-Path $tdBin 'hwserver.exe') `
        -ArgumentList @('-r','-s','5555','-f','12','-v','-w','5556','-i','0') `
        -WindowStyle Hidden
    Start-Sleep -Seconds 2
}
$env:T3_BIT_PATH = $bit.Replace('\', '/')
try {
    & (Join-Path $tdBin 'bw_commands_prompt.exe') `
        (Join-Path $root 'program_sram.tcl').Replace('\', '/')
    if ($LASTEXITCODE -ne 0) { throw "BitWriter exited with $LASTEXITCODE" }
} finally {
    Remove-Item Env:\T3_BIT_PATH -ErrorAction SilentlyContinue
}
