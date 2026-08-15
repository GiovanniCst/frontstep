# frontstep-open.ps1 — opens a terminal in a project's folder.
#
# Windows runs this when a browser meets a `frontstep://…` URI, because a page
# served over http:// cannot start a program on the machine. Registered under
# HKCU (no administrator needed); see README.md next to this file.
#
# ⚠️ THIS SCRIPT IS THE ATTACK SURFACE, NOT A DETAIL.
# A protocol handler is global: ANY web page can invoke `frontstep://something`.
# The whole defence is in here, and it is four rules:
#
#   1. the roots are CONSTANTS below — the URI only carries a KEY that indexes
#      them, never a path;
#   2. the name goes through a strict regex: no `/`, `\`, `..`, spaces, no
#      leading dot, nothing past 64 characters;
#   3. the folder must ALREADY EXIST: this script creates nothing;
#   4. arguments are passed as an ARRAY to Start-Process, never concatenated
#      into a shell string — concatenation is what turns a handler into
#      arbitrary command execution (the known Steam and Zoom holes).
#
# With those, the worst a hostile site can do is open a terminal in a project
# folder that is already there.
#
# ---------------------------------------------------------------------------
# EDIT THESE FOUR CONSTANTS AND NOTHING ELSE.
# The keys of $ROOTS must match the `key` of your roots in frontstep.toml: that
# key is what travels in the URI, and it is all that travels.
# ---------------------------------------------------------------------------

$ROOTS = @{
    'projects' = '/home/you/projects'
    'home'     = '/home/you'
}
$DISTRO   = 'Ubuntu-22.04'                              # wsl.exe -l -q
$TERMINAL = 'C:\Program Files\WezTerm\wezterm-gui.exe'  # any terminal emulator
# WezTerm's native WSL domain, declared in its own config. Using it avoids
# invoking `wsl.exe`, which is a console process: on Windows 11 the console is
# handed to the "default terminal", and that is where an extra window per click
# came from.
$DOMAIN   = 'wsl:ubuntu-bash'

# The URI arrives in an ENVIRONMENT VARIABLE, not on the command line, so it
# never crosses a shell parser. frontstep-open.vbs sets it — that is what the
# registry invokes, because wscript allocates no console and powershell does.
$Uri = $env:FRONTSTEP_URI
if (-not $Uri) { $Uri = $args[0] }

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework

function Fail($message) {
    # A button that silently does nothing is worse than an error: this is seen.
    [System.Windows.MessageBox]::Show($message, 'Frontstep', 'OK', 'Warning') | Out-Null
    exit 1
}

# --- 1. the URI, through a regex that leaves no room -------------------------
# The only accepted shape: frontstep://<root>/<name>   (a trailing slash is fine)
$keys = ($ROOTS.Keys | ForEach-Object { [regex]::Escape($_) }) -join '|'
if ($Uri -notmatch "^frontstep://(?<root>$keys)/(?<name>[^/\\]{1,64})/?$") {
    Fail "Request not recognised:`n$Uri"
}
$root = $Matches['root']
$name = [System.Uri]::UnescapeDataString($Matches['name'])

# --- 2. the name: letters, digits, accents, dot, dash, underscore ------------
# Accents are genuinely needed: real project folders have them.
if ($name -notmatch '^[A-Za-z0-9\u00C0-\u024F][A-Za-z0-9\u00C0-\u024F._-]{0,63}$') {
    Fail "Project name not allowed: $name"
}
if ($name.Contains('..')) {
    Fail "Project name not allowed: $name"
}

$path = "$($ROOTS[$root])/$name"

# --- 3. the folder must exist: nothing is created here -----------------------
# The check goes through WSL's UNC path and NOT through `wsl.exe`: invoking a
# console process would pop up a window of the default terminal, which is
# exactly the noise being removed. Test-Path opens nothing.
$unc = '\\wsl.localhost\' + $DISTRO + $path.Replace('/', '\')
if (-not (Test-Path -LiteralPath $unc)) {
    Fail "The folder does not exist:`n$path"
}

if (-not (Test-Path $TERMINAL)) {
    Fail "The terminal is not where I expect it:`n$TERMINAL"
}

# --- 4. arguments as an array, never a shell string --------------------------
# `-- bash -l` is not redundant: without it WezTerm takes the GLOBAL
# `default_prog` from its config — on Windows that is `pwsh -NoLogo` — and tries
# to run it INSIDE the distro, where pwsh does not exist. The WSL domain's own
# default_prog does not win over the global one.
# The ABSOLUTE UNC path is passed, not the Linux one: WezTerm resolves `--cwd`
# against the WINDOWS current directory, and prefixes `C:` to a path starting
# with `/` — hence `--cd C:/home/you/…` and ERROR_PATH_NOT_FOUND. The UNC is the
# one already verified at step 3, so there is no second form of the path to keep
# in step.
Start-Process -FilePath $TERMINAL -ArgumentList @(
    'start', '--domain', $DOMAIN, '--cwd', $unc, '--', 'bash', '-l'
)
