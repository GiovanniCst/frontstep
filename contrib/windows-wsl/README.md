# The `frontstep://` handler — Windows + WSL

> ⚠️ **You almost certainly do not need this any more.** The Terminal button now
> asks the SERVER to open a terminal, and the server runs on your machine, so it
> works with nothing installed and nothing registered. This handler is what the
> button falls back to when the server may not open one itself: `launch = false`
> in your configuration, a `bind` that is not a loopback address, or Frontstep
> running in a container. If none of those is you, skip this directory.

The **Terminal** button on a card opens a terminal in that project's folder.

A page served over `http://` cannot start a program on your machine — that is a
browser barrier, not a limitation of Frontstep. Where the server cannot do it
either, the button becomes a link to a custom URI scheme,
`frontstep://<root>/<project>`, which the operating system hands to a script you
install yourself. Same mechanism VS Code, Zoom and Slack use for their own
schemes.

**This is optional and it is the only part of Frontstep tied to one platform.**
Nothing else needs it. **Path** copies the path for you to paste, and in the
same fallback the **Editor** button becomes a `vscode://` link, which needs
nothing of ours installed but does assume a VS Code family editor. If you skip
this, the page tells you so when the Terminal button turns out to lead nowhere.

## What is in here

| File | What it does |
|---|---|
| `frontstep-open.ps1` | validates the URI and opens the terminal. **All the security is in this file** |
| `frontstep-open.vbs` | launches the above without a console window — the registry cannot invoke PowerShell directly without one appearing |

## Install

1. Copy both files to `%USERPROFILE%\bin\`.
2. Open `frontstep-open.ps1` and edit **the four constants at the top**: your
   roots (the keys must match the `key` of the roots in your `frontstep.toml`),
   the WSL distro, the terminal, and the terminal's WSL domain.
3. Register the scheme — no administrator needed, it is all under `HKCU`:

```bat
reg add "HKCU\Software\Classes\frontstep" /ve /d "URL:Frontstep Protocol" /f
reg add "HKCU\Software\Classes\frontstep" /v "URL Protocol" /d "" /f
reg add "HKCU\Software\Classes\frontstep\shell\open\command" /ve /d "\"C:\Windows\System32\wscript.exe\" \"%%USERPROFILE%%\bin\frontstep-open.vbs\" \"%%1\"" /f
```

Uninstall:

```bat
reg delete "HKCU\Software\Classes\frontstep" /f
```

## ⚠️ Read this before installing

A protocol handler is **global**: any web page you visit can invoke
`frontstep://something`, not only your dashboard. That is the price of this
route, and it is why the whole defence sits inside `frontstep-open.ps1`:

- **the roots are constants in the script** — the URI carries a key that indexes
  them, never a path;
- **the project name goes through a strict regex** — no `/`, `\`, `..`, spaces
  or leading dot, 64 characters at most;
- **the folder must already exist** — the script creates nothing;
- **arguments are passed as an array**, never concatenated into a shell string.
  Concatenation is what has turned handlers into arbitrary command execution
  before.

With those four, the worst a hostile page can do is open a terminal in a folder
you already have.

## If it does not work

The script says so in a message box rather than failing silently — an
unrecognised URI, a folder that is not there, a terminal that is not where it
says. If **nothing at all** happens, the scheme is not registered: check the
`reg add` above, and note that the browser asks for confirmation the first time.

Four traps met while building this, worth knowing if you adapt it to another
terminal:

| Symptom | Actual cause |
|---|---|
| a stray Windows Terminal window, sometimes with an error in it | the registry was launching `powershell.exe`, which **always allocates a console**; on Windows 11 the console goes to the "default terminal". Hence the `.vbs` and `wscript` |
| two terminal windows | invoking `wsl.exe` by hand instead of the terminal's **native WSL domain** |
| `execvpe(pwsh.exe) failed` | the WSL domain's `default_prog` does not win over the global one: pass `-- bash -l` |
| `--cwd C:/home/you/…` | WezTerm resolves `--cwd` against the **Windows** current directory and prefixes `C:` to a Linux path. Pass the absolute UNC path instead |
