# Export the workbook's Checks and Forecast sheets to PDF through Excel (read-only, nothing is saved),
# then render them to PNG stills for the demo film. Called by demo/capture.py; needs Microsoft Excel.
$root = Split-Path $PSScriptRoot -Parent
$src = Join-Path $root "output\XAVI_valuation_model.xlsx"
$dir = Join-Path $PSScriptRoot "frames"
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
    $wb = $xl.Workbooks.Open($src, 0, $true)
    foreach ($name in @("Checks", "Forecast")) {
        $ws = $wb.Worksheets.Item($name)
        $ws.PageSetup.Orientation = 2; $ws.PageSetup.Zoom = $false; $ws.PageSetup.FitToPagesWide = 1; $ws.PageSetup.FitToPagesTall = 1
        foreach ($m in @("LeftMargin", "RightMargin", "TopMargin", "BottomMargin")) { $ws.PageSetup.$m = 18 }
        $ws.ExportAsFixedFormat(0, (Join-Path $dir "xl_$name.pdf"))
    }
    $wb.Close($false)
} finally {
    $xl.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
}
Push-Location $root
py -3.12 -c "import pymupdf, pathlib; [ (pymupdf.open(p)[0].get_pixmap(dpi=300).save(str(p.with_suffix('.png'))), p.unlink()) for p in pathlib.Path('demo/frames').glob('xl_*.pdf') ]"
Pop-Location
"excel stills exported"
