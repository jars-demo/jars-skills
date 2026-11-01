---
name: disk-cleanup
description: Auditing and recovering disk space on a developer Windows machine: scans known cache and temp locations with a fast read-only dir /s script, identifies safe-to-clean locations (uv, pip, npm, Windows Update, TEMP), relocates tool caches to a dedicated drive using environment variables and config files, and sets up a monthly maintenance script. Use when your C drive is filling up, you want to find what is using disk space, clean up Python or Node caches, move caches to another drive, set UV_CACHE_DIR or pip cache-dir, audit disk usage, or set up a CacheStore folder structure.
---

## disk-cleanup

Audit first. Clean only what you understand. Never delete without reading the plan.

### 1. Check drive status

```powershell
$drive = Get-PSDrive C
$used  = [math]::Round($drive.Used  / 1GB, 2)
$free  = [math]::Round($drive.Free  / 1GB, 2)
$total = [math]::Round(($drive.Used + $drive.Free) / 1GB, 2)
Write-Host "Total : $total GB"
Write-Host "Used  : $used GB"
Write-Host "Free  : $free GB"
Write-Host "Used% : $([math]::Round($used/$total*100,1))%"
```

Above 85% used = danger zone. Windows page file, system restore, and temp writes
all need headroom.

---

### 2. Scan all known cache locations — read-only

Use `cmd /c dir /s` instead of `Get-ChildItem -Recurse`. It is 10–50× faster because
it runs natively in the cmd process without PowerShell object overhead.

```powershell
# READ-ONLY — does not modify or delete anything
function Get-SizeMB($path) {
    if (-not (Test-Path $path)) { return $null }
    $lines   = & cmd /c "dir /s /a `"$path`" 2>nul"
    $summary = $lines | Select-String "File\(s\)" | Select-Object -Last 1
    if ($summary -match "([\d,]+)\s+bytes") {
        $bytes = [long]($matches[1] -replace ',', '')
        return [math]::Round($bytes / 1MB, 1)
    }
    return 0
}

$locations = [ordered]@{
    "User TEMP"                       = $env:TEMP
    "Windows Temp"                    = "C:\Windows\Temp"
    "Windows Prefetch"                = "C:\Windows\Prefetch"
    "Windows Update Download Cache"   = "C:\Windows\SoftwareDistribution\Download"
    "User Downloads"                  = "$env:USERPROFILE\Downloads"
    "uv cache"                        = "$env:LOCALAPPDATA\uv\cache"
    "pip cache"                       = "$env:LOCALAPPDATA\pip\cache"
    "npm cache"                       = "$env:APPDATA\npm-cache"
    "pnpm store"                      = "$env:LOCALAPPDATA\pnpm\store"
    "yarn cache"                      = "$env:LOCALAPPDATA\Yarn\cache"
    "VS Code extensions"              = "$env:USERPROFILE\.vscode\extensions"
    "Docker (LocalAppData)"           = "$env:LOCALAPPDATA\Docker"
    "JetBrains cache"                 = "$env:LOCALAPPDATA\JetBrains"
    "Chrome cache"                    = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache"
    "Windows Error Reporting"         = "C:\ProgramData\Microsoft\Windows\WER\ReportArchive"
    "Recycle Bin"                     = "C:\`$Recycle.Bin"
}

Write-Host ("{0,-45} {1,10}   Path" -f "Location", "Size")
Write-Host ("-" * 90)
foreach ($key in $locations.Keys) {
    $path = $locations[$key]
    $mb   = Get-SizeMB $path
    $disp = if ($null -eq $mb) { "(not found)" } elseif ($mb -eq 0) { "0 MB" } else { "$mb MB" }
    Write-Host ("{0,-45} {1,10}   {2}" -f $key, $disp, $path)
}
```

**Note on locale:** `dir` uses the system digit separator (`,` on US/UK, `.` on some
European locales). Change `-replace ','` to `-replace '\.'` if on a European locale.

---

### 3. Safe-to-clean locations

These are always safe — nothing breaks, everything regenerates automatically:

| Location | Clear command | Regenerates when |
|----------|--------------|-----------------|
| `uv` cache | `uv cache clean` | Next `uv sync` or `uv pip install` |
| `pip` cache | `pip cache purge` | Next `pip install` |
| `npm` cache | `npm cache clean --force` | Next `npm install` |
| `yarn` cache | `yarn cache clean` | Next `yarn install` |
| User TEMP | `Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue` | Continuously |
| Windows Prefetch | Delete contents | After first app launches (1–2 days) |

**Stop Windows Update service before clearing its cache:**
```powershell
Stop-Service wuauserv -Force ; Stop-Service bits -Force
Remove-Item "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue
Start-Service bits ; Start-Service wuauserv
```

**Never delete manually:**
- `C:\Windows\WinSxS` — use `dism /online /cleanup-image /startcomponentcleanup`
- `C:\pagefile.sys` — virtual memory, removing causes blue screen
- `C:\hiberfil.sys` — hibernate file, use `powercfg /h off` to remove safely
- `AppData\Roaming` bulk delete — loses app settings and auth tokens
- `pnpm store` directly — use `pnpm store prune` only

---

### 4. Relocate caches to a dedicated drive

The permanent fix: move all tool caches off C onto a dedicated folder on another drive.
Create a `CacheStore` root:

```
D:\CacheStore\   (or E:\CacheStore\, whatever your secondary drive is)
  uv\
  pip\
  npm\
  huggingface\   ← AI models
  ollama\        ← Local LLMs
  docker\
  gradle\
```

**Relocate uv cache:**
```powershell
# Clear old cache first — no point moving 10 GB of stale data
uv cache clean

# Set permanently at user level
[System.Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "D:\CacheStore\uv", "User")

# Apply in current session too
$env:UV_CACHE_DIR = "D:\CacheStore\uv"

# Verify
uv cache dir   # should print D:\CacheStore\uv
```

**Relocate pip cache:**
```powershell
pip cache purge
pip config set global.cache-dir "D:\CacheStore\pip"
pip cache dir   # should print D:\CacheStore\pip
```

**Relocate npm cache:**
```powershell
npm cache clean --force
npm config set cache "D:\CacheStore\npm"
npm config get cache   # verify
```

**Future tools — the standard pattern:**
```powershell
# 1. Create the folder
New-Item -ItemType Directory -Path "D:\CacheStore\<toolname>" -Force

# 2. Set env var (user scope)
[System.Environment]::SetEnvironmentVariable("<TOOL_CACHE_VAR>", "D:\CacheStore\<toolname>", "User")

# 3. Apply in current session
$env:<TOOL_CACHE_VAR> = "D:\CacheStore\<toolname>"

# 4. Verify — check tool docs for the verification command
```

Common env vars for future caches:
```
HF_HOME          → D:\CacheStore\huggingface   (HuggingFace models)
OLLAMA_MODELS    → D:\CacheStore\ollama        (Ollama local LLMs)
GRADLE_USER_HOME → D:\CacheStore\gradle        (Gradle builds)
CARGO_HOME       → D:\CacheStore\cargo         (Rust packages)
```

---

### 5. Why env vars don't show immediately in a running terminal

After setting `UV_CACHE_DIR` via System Properties or `SetEnvironmentVariable`, a
running terminal still shows the old value. This is expected — not a bug.

When Windows launches a process, it hands it a **snapshot copy** of the environment
at launch time. The process holds its own private copy. Changing the registry (which
is what System Properties does) does not push into already-running processes.

```
Registry (source of truth)  ←  updated immediately
Running terminal            ←  still has the old snapshot (won't update)
New terminal opened after   ←  gets the new value ✅
```

Fix: close the terminal and open a new one. Or apply in the current session manually:
```powershell
$env:UV_CACHE_DIR = "D:\CacheStore\uv"   # current session only
```

---

### 6. Verify everything is pointing correctly

```powershell
Write-Host "=== Cache locations ==="
Write-Host "uv  : $(uv cache dir)"
Write-Host "pip : $(pip cache dir)"
Write-Host "npm : $(npm config get cache)"
Write-Host ""
Write-Host "=== UV_CACHE_DIR env var ==="
Write-Host "Session : $env:UV_CACHE_DIR"
Write-Host "User    : $([System.Environment]::GetEnvironmentVariable('UV_CACHE_DIR','User'))"
Write-Host "System  : $([System.Environment]::GetEnvironmentVariable('UV_CACHE_DIR','Machine'))"
Write-Host ""
$drive = Get-PSDrive C
Write-Host "C drive free: $([math]::Round($drive.Free/1GB,2)) GB"
```

---

### 7. Monthly maintenance script

```powershell
# maintenance.ps1 — run once a month
Write-Host "=== Cache Maintenance ===" 
Write-Host "Date: $(Get-Date -Format 'yyyy-MM-dd')`n"

$before = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
Write-Host "C drive free before: $before GB"

uv cache clean
pip cache purge
Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue

$after = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
Write-Host "C drive free after : $after GB"
Write-Host "Freed              : $([math]::Round($after - $before, 2)) GB"
```

Add to Windows Task Scheduler to run on the 1st of each month automatically.

### Rules

- Always scan before cleaning. Run the read-only script first, review, then act.
- Never present a plan and execute in the same step — show findings, get approval, then run.
- `pnpm store` must be cleaned with `pnpm store prune` only — it uses hard links, manual
  deletion breaks installed packages.
- Relocating a cache does not move existing files — clear first, then set the new path.
- User-scope env vars are sufficient for personal dev tools. System-scope is for
  machine-wide tooling only.
- After setting an env var, open a new terminal to pick it up — running processes hold
  a snapshot of the environment from their launch time.
