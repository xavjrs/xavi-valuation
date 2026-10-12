# Recalculate output/XAVI_valuation_model.xlsx in Microsoft Excel (iterative calculation on) and save it,
# so formula results are cached in the file for verify_excel.py and any viewer.
param([string]$Path = (Join-Path $PSScriptRoot "output\XAVI_valuation_model.xlsx"))
$full = (Resolve-Path $Path).Path
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
    $wb = $xl.Workbooks.Open($full)
    $xl.Iteration = $true
    $xl.MaxIterations = 10000
    $xl.MaxChange = 1e-10
    $xl.CalculateFull()
    $xl.CalculateFull()
    $wb.Save()
    $wb.Close($false)
    "recalculated: $full"
} finally {
    $xl.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
}
