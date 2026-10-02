# Sube a GitHub las tandas nuevas que deja la tarea de Claude en esta carpeta (todos los clientes).
# Solo sube contenido (posts, calendarios, planes, guías, tandas). Nunca .env, media/ ni alta/.
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$log = Join-Path $PSScriptRoot "sincronizar.log"
function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm') $m" | Add-Content -LiteralPath $log -Encoding utf8 }
function GitOk {
    $ErrorActionPreference = "Continue"
    $out = (& git.exe @args 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "git $($args -join ' ') -> $out" }
}
try {
    GitOk pull --rebase --autostash -q
    $files = Get-ChildItem -Path clientes -Recurse -File -Include *.json, *.md |
        Where-Object { $_.FullName -match '\\content\\' -or $_.Name -eq 'marca.json' -or $_.FullName -match '\\biblioteca\\index.json$' } |
        ForEach-Object { Resolve-Path -Relative $_.FullName }
    if ($files) { GitOk add -- $files }
    & git.exe diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        GitOk commit -q -m "Nueva tanda de contenido (tarea automática)"
        GitOk push -q
        Log "Subido a GitHub: $(& git.exe log -1 --format=%h)"
    } else { Log "Sin cambios que subir." }
} catch { Log "ERROR: $_" }
