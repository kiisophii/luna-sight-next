<#
Card 14 - split run of the 948 m (ppd 32) map: compute only a row range on this machine.

Same store (data/processed/gmaps_ppd32/), same DEMs / ephemeris / settings as run_ppd32_overnight.ps1
(global_maps.py refuses to resume if the parameter signature differs). Rows already marked done
are skipped. Keeps the PC awake, logs to data/processed/logs/ppd32_rows_<start>_<stop>_<time>.log,
and resumes after a crash (finished rows are kept). It never uses --restart and NEVER exports:
the whole-Moon export runs only after both machines' rows are merged (5760/5760).

When the range is complete it saves the values of -KeepRow (default 3103, the overlap row computed
on both machines) to data/processed/gmaps_ppd32_row<row>_<host>.npz + .json for comparison.

    powershell -ExecutionPolicy Bypass -File pipeline\run_ppd32_rows.ps1 -Rows 0:3104 -Threads 16
    powershell -ExecutionPolicy Bypass -File pipeline\run_ppd32_rows.ps1 -Rows 0:3104 -CheckOnly

-Rows is START:STOP with STOP exclusive (0:3104 = rows 0..3103). Stop with Ctrl+C; rerun to continue.
#>
param(
    [Parameter(Mandatory = $true)][string]$Rows,
    [int]$Threads = 16,
    [int]$KeepRow = 3103,
    [switch]$CheckOnly,
    [switch]$AllowBattery,
    [int]$Retries = 3,
    [double]$MinFreeGB = 5
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
if ($Rows -notmatch '^(\d+):(\d+)$') { Write-Host "-Rows must be START:STOP, got '$Rows'"; exit 2 }
$R0, $R1 = [int]$Matches[1], [int]$Matches[2]
$LogDir = Join-Path $Root 'data\processed\logs'
New-Item -ItemType Directory -Force $LogDir | Out-Null
$Log = Join-Path $LogDir ("ppd32_rows_{0}_{1}_{2}.log" -f $R0, $R1, (Get-Date -Format 'yyyyMMdd_HHmmss'))
function Log([string]$m) { $line = "{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m; Write-Host $line; Add-Content -Path $Log -Value $line -Encoding utf8 }

Log "card 14 ppd 32 split run, rows $R0`:$R1 (stop exclusive: last row $($R1 - 1)) - log $Log"
# ---------------------------------------------------------------- pre-flight
$fail = @()
if (-not (Test-Path $Py)) { $fail += "missing $Py" }
if ($KeepRow -lt $R0 -or $KeepRow -ge $R1) { $fail += "-KeepRow $KeepRow is outside rows $R0`:$R1" }
$eph = Get-Content (Join-Path $Root 'web\data\ephem.json') -Raw | ConvertFrom-Json
if ($eph.mock -ne $false) { $fail += 'web/data/ephem.json is mock - refusing to compute' } else { Log "ephemeris: $($eph.source), n=$($eph.n), mock=false" }
foreach ($f in 'data\raw\global\ldem_64_float.img', 'data\raw\global\ldem_16_float.img') { if (-not (Test-Path (Join-Path $Root $f))) { $fail += "missing $f" } }
$store = Join-Path $Root 'data\processed\gmaps_ppd32\meta.json'
if (-not (Test-Path $store)) { $fail += 'no existing ppd32 store (data/processed/gmaps_ppd32/meta.json)' }
else {
    $sig = (Get-Content $store -Raw | ConvertFrom-Json).signature
    Log ("store: near {0}, far {1}, step {2} h, ephem mock {3}, sha1 {4}" -f $sig.near.name, $sig.far.name, $sig.ephem.step_h, $sig.ephem.mock, $sig.ephem.sha1_12)
    if ($sig.ephem.mock -ne $false -or $sig.ephem.step_h -ne 3) { $fail += 'existing ppd32 store was made with other settings' }
}
$drive = (Get-Item $Root).PSDrive
$freeGB = [math]::Round($drive.Free / 1GB, 1)
Log "free disk on $($drive.Name): $freeGB GB"
if ($freeGB -lt $MinFreeGB) { $fail += "only $freeGB GB free" }
$bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
if ($bat) {
    Log ("battery {0} %, status {1} (2 = on AC)" -f $bat.EstimatedChargeRemaining, $bat.BatteryStatus)
    if ($bat.BatteryStatus -ne 2 -and -not $AllowBattery) { $fail += 'not on AC power - plug in the charger (or pass -AllowBattery)' }
}
$dup = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'global_maps\.py\s+run' }
if ($dup) { $fail += 'another global_maps.py run is already running (PID ' + (($dup | ForEach-Object { $_.ProcessId }) -join ', ') + ') - stop it first (Ctrl+C in its window)' }
$nCores = [Environment]::ProcessorCount
$t = [math]::Min($Threads, $nCores)
Log "threads: $t of $nCores logical CPUs"
# Native python calls only from here on; 'Stop' would turn their stderr lines into terminating errors (PS 5.1).
$ErrorActionPreference = 'Continue'
$rangeCode = "import numpy as np; d = np.load(r'data/processed/gmaps_ppd32/done.npy', mmap_mode='r'); print(int(d[$R0`:$R1].sum()), $R1 - $R0, int(d.sum()))"
function RangeDone { $o = (& $Py -c $rangeCode) -split ' '; return [int]$o[0], [int]$o[1], [int]$o[2] }
$rd = RangeDone
Log ("range {0}:{1}: {2}/{3} rows done; whole store {4}/5760" -f $R0, $R1, $rd[0], $rd[1], $rd[2])
if ($fail.Count) { $fail | ForEach-Object { Log "PRE-FLIGHT FAIL: $_" }; exit 2 }
if ($CheckOnly) { Log 'pre-flight OK (check only, nothing computed)'; exit 0 }

# ---------------------------------------------------------------- keep awake while running
Add-Type -Namespace Win -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[void][Win.Power]::SetThreadExecutionState([Convert]::ToUInt32('80000001', 16))   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
try {
    $ok = $false
    for ($i = 1; $i -le $Retries -and -not $ok; $i++) {
        Log "run attempt $i/$Retries"
        $t0 = Get-Date
        & $Py -u pipeline\global_maps.py run --ppd 32 --step-h 3 --rows "$R0`:$R1" --threads "$t" 2>&1 | ForEach-Object { Log "$_" }
        $code = $LASTEXITCODE
        $rd = RangeDone
        Log ("attempt {0} exit code {1} after {2:N1} h; range {3}/{4} rows done; whole store {5}/5760" -f $i, $code, ((Get-Date) - $t0).TotalHours, $rd[0], $rd[1], $rd[2])
        if ($code -eq 0 -and $rd[0] -eq $rd[1]) { $ok = $true } elseif ($i -lt $Retries) { Log 'resuming in 60 s (finished rows are kept)'; Start-Sleep 60 }
    }
    if (-not $ok) { Log 'NOT FINISHED - rerun this script to continue; see the log above for the error'; exit 1 }
    # ---- keep the overlap row for the cross-machine comparison (read-only on the store)
    $tag = $env:COMPUTERNAME.ToLower()
    $keepCode = @"
import json, numpy as np, pathlib
d = pathlib.Path('data/processed/gmaps_ppd32'); r = $KeepRow
assert np.load(d / 'done.npy', mmap_mode='r')[r] == 1, 'row not done'
out = {f: np.array(np.load(d / f'{f}.npy', mmap_mode='r')[r]) for f in ('sun', 'earth', 'both', 'h0', 'maskmax')}
p = pathlib.Path('data/processed/gmaps_ppd32_row{}_$tag.npz'.format(r)); np.savez(p, **out)
meta = json.loads((d / 'meta.json').read_text())
info = dict(row=r, host='$tag', rows_run='$R0`:$R1', signature=meta['signature'],
            stats={f: dict(nan=int(np.isnan(v).sum()), mean=float(np.nanmean(v)), min=float(np.nanmin(v)), max=float(np.nanmax(v))) for f, v in out.items()})
p.with_suffix('.json').write_text(json.dumps(info, indent=1))
print('saved', p, {f: round(s['mean'], 6) for f, s in info['stats'].items()})
"@
    & $Py -c $keepCode 2>&1 | ForEach-Object { Log "row $KeepRow`: $_" }
    Log "RANGE DONE rows $R0`:$R1 - no export here (export only after merging to 5760/5760)"
} finally {
    [void][Win.Power]::SetThreadExecutionState([Convert]::ToUInt32('80000000', 16))   # back to normal sleep rules
}
