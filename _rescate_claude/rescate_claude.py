#!/usr/bin/env python3
"""
rescate_claude.py - Rescate del historico de Claude Code a Obsidian (solo stdlib).

Seguridad:
  - SOLO LEE los transcripts de Claude (~/.claude/projects/**/*.jsonl). Nunca los borra ni modifica.
  - Nunca sobrescribe: si la nota ya existe, crea <nombre>__v2.md, __v3.md...
  - No escribe nada sin --escribir (por defecto es simulacion / dry-run).
  - Redacta secretos (API keys, tokens, passwords) antes de escribir.
  - No guarda razonamiento interno (bloques "thinking"): solo mensajes, acciones y resultados.
  - No fusiona vaults: busca en todos los --vault, escribe solo en --destino.

Modos:
  rescate     Inventario + comparacion con Obsidian + notas por sesion.
  checkpoint  Para hooks de Claude Code (PreCompact / SessionEnd / Stop): lee el JSON del
              hook por stdin y guarda un checkpoint de la sesion actual.

Ejemplos (Windows):
  py rescate_claude.py rescate --vault I:\\CEREBRO\\obsidian_vault --vault I:\\CEREBRO\\obsidian_vault_titan
  py rescate_claude.py rescate --vault I:\\CEREBRO\\obsidian_vault --vault I:\\CEREBRO\\obsidian_vault_titan ^
       --destino I:\\CEREBRO\\obsidian_vault_titan --buscar I:\\CEREBRO --escribir
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

CARPETA = "CLAUDE_HISTORICO"
MAESTRO = "CLAUDE_ESTADO_MAESTRO_24SEP2026"
MAX_TXT = 1500          # recorte por mensaje en la nota
MAX_ITEMS = 60          # max elementos por lista

# ---------------------------------------------------------------- redaccion de secretos
SECRETOS = [
    (re.compile(r"sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{16,}"), "sk-***REDACTADO***"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "gh*_***REDACTADO***"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_***REDACTADO***"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "xox*-***REDACTADO***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***REDACTADO***"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "AIza***REDACTADO***"),
    (re.compile(r"nvapi-[A-Za-z0-9_\-]{20,}"), "nvapi-***REDACTADO***"),
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b"), "***TELEGRAM_TOKEN_REDACTADO***"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "***JWT_REDACTADO***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"), r"\1***REDACTADO***"),
    (re.compile(r"(?i)((?:api[_-]?key|apikey|token|secret|password|passwd|contrase(?:ñ|n)a|pwd)[\"']?\s*[:=]\s*[\"']?)[^\s\"',;]{4,}"),
     r"\1***REDACTADO***"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"), "***CLAVE_PRIVADA_REDACTADA***"),
]


def redactar(txt):
    if not txt:
        return txt
    for rx, rep in SECRETOS:
        txt = rx.sub(rep, txt)
    return txt


def recortar(txt, n=MAX_TXT):
    txt = (txt or "").strip()
    return txt if len(txt) <= n else txt[:n] + f"\n…[recortado, {len(txt) - n} caracteres más en el transcript original]"


# ---------------------------------------------------------------- lectura de transcripts
def texto_de(content):
    """Devuelve el texto visible de un content (str o lista de bloques). Ignora 'thinking'."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    out = []
    for b in content:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text", ""))
    return "\n".join(out)


def leer_sesion(path):
    s = {
        "archivo": str(path), "session_id": path.stem, "titulo": None, "cwd": None, "rama": None,
        "version": None, "inicio": None, "fin": None, "subagente": "subagents" in path.parts,
        "usuario": [], "asistente": [], "resumenes": [], "comandos": [], "archivos": set(),
        "errores": [], "lineas_malas": 0, "mensajes": 0,
    }
    tool_names = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for linea in fh:
            try:
                d = json.loads(linea)
            except Exception:
                s["lineas_malas"] += 1
                continue
            t = d.get("type")
            if t in ("ai-title", "summary"):
                s["titulo"] = d.get("aiTitle") or d.get("summary") or s["titulo"]
                if t == "summary" and d.get("summary"):
                    s["resumenes"].append(d["summary"])
                continue
            if t not in ("user", "assistant"):
                continue
            ts = d.get("timestamp")
            if ts:
                s["inicio"] = s["inicio"] or ts
                s["fin"] = ts
            s["cwd"] = s["cwd"] or d.get("cwd")
            s["rama"] = d.get("gitBranch") or s["rama"]
            s["version"] = d.get("version") or s["version"]
            if d.get("sessionId"):
                s["session_id"] = d["sessionId"]
            msg = d.get("message") or {}
            content = msg.get("content")
            s["mensajes"] += 1
            if t == "user":
                if d.get("isCompactSummary"):
                    s["resumenes"].append(texto_de(content))
                    continue
                if d.get("isMeta"):
                    continue
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                            c = b.get("content")
                            c = c if isinstance(c, str) else texto_de(c)
                            s["errores"].append((ts, tool_names.get(b.get("tool_use_id"), "?"), c))
                txt = texto_de(content)
                if txt.strip() and not txt.lstrip().startswith("<"):
                    s["usuario"].append((ts, txt))
            else:
                if isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict) or b.get("type") != "tool_use":
                            continue
                        name, inp = b.get("name", "?"), b.get("input") or {}
                        tool_names[b.get("id")] = name
                        fp = inp.get("file_path") or inp.get("notebook_path")
                        if name in ("Edit", "Write", "MultiEdit", "NotebookEdit") and fp:
                            s["archivos"].add(fp)
                        cmd = inp.get("command")
                        if cmd and name in ("Bash", "PowerShell"):
                            s["comandos"].append((ts, name, inp.get("description") or "", cmd))
                txt = texto_de(content)
                if txt.strip():
                    s["asistente"].append((ts, txt))
    return s


RX_PUERTO = re.compile(r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0)[:](\d{2,5})|\bpuerto\s+(\d{2,5})|\bport\s+(\d{2,5})", re.I)
RX_RUTA = re.compile(r"\b[A-Z]:\\[^\s\"'`<>|*?]+", re.I)
RX_BACKUP = re.compile(r"[^\s\"'`]*(?:BACKUP|\.bak|backup_)[^\s\"'`]*", re.I)
RX_CORR = re.compile(r"correlation[_ ]?id[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_\-]{4,})", re.I)
RX_PASSFAIL = re.compile(r"^.*\b(PASS|FAIL|BLOCKED|UNVERIFIED|E2E\w*)\b.*$", re.M)


def extraer(s):
    todo = "\n".join([t for _, t in s["usuario"]] + [t for _, t in s["asistente"]] +
                     [c for *_, c in s["comandos"]] + s["resumenes"])
    puertos = sorted({p for m in RX_PUERTO.findall(todo) for p in m if p}, key=int)
    rutas = sorted({r.rstrip(".,;:)") for r in RX_RUTA.findall(todo)})
    backups = sorted({b.rstrip(".,;:)") for b in RX_BACKUP.findall(todo)})
    corr = sorted(set(RX_CORR.findall(todo)))
    pf = []
    for _, t in s["asistente"]:
        pf += [m.group(0).strip() for m in RX_PASSFAIL.finditer(t)]
    return puertos, rutas[:MAX_ITEMS * 2], backups[:MAX_ITEMS], corr[:MAX_ITEMS], list(dict.fromkeys(pf))[-MAX_ITEMS:]


# ---------------------------------------------------------------- comparacion con Obsidian
def indexar_vaults(vaults):
    """Devuelve {ruta_nota: texto} de todos los .md de los vaults (solo lectura)."""
    idx = {}
    for v in vaults:
        v = Path(v)
        if not v.exists():
            print(f"[AVISO] vault no existe: {v}", file=sys.stderr)
            continue
        for p in v.rglob("*.md"):
            if ".obsidian" in p.parts or ".trash" in p.parts:
                continue
            try:
                idx[str(p)] = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
    return idx


def estado_en_obsidian(s, idx):
    sid = s["session_id"]
    completas, menciones = [], []
    for ruta, txt in idx.items():
        if sid in txt or sid[:8] in Path(ruta).name:
            completa = re.search(r'^session_id:\s*"?' + re.escape(sid), txt, re.M)
            (completas if completa else menciones).append(ruta)
    if completas:
        return "YA_ESTA_EN_OBSIDIAN", completas + menciones
    if menciones:
        return "PARCIALMENTE_GUARDADA", menciones
    # busqueda debil por titulo
    t = (s["titulo"] or "").strip()
    if len(t) > 12:
        debil = [r for r, txt in idx.items() if t in txt]
        if debil:
            return "PARCIALMENTE_GUARDADA", debil
    return "NO_ESTA_EN_OBSIDIAN", []


# ---------------------------------------------------------------- nota Markdown
def lista(items, fmt=lambda x: x, vacio="_(nada detectado automáticamente)_"):
    items = list(items)
    if not items:
        return vacio
    return "\n".join(f"- {fmt(i)}" for i in items[:MAX_ITEMS]) + (
        f"\n- …y {len(items) - MAX_ITEMS} más" if len(items) > MAX_ITEMS else "")


def nota_sesion(s, estado, donde, tipo="rescate"):
    puertos, rutas, backups, corr, pf = extraer(s)
    fecha = (s["inicio"] or "")[:10]
    titulo = redactar(s["titulo"] or "(sin título)")
    ult_asist = s["asistente"][-1][1] if s["asistente"] else ""
    objetivos = [t for _, t in s["usuario"][:3]]
    fm = {
        "tipo": f"claude_sesion_{tipo}", "session_id": s["session_id"], "titulo": titulo,
        "fecha_inicio": s["inicio"], "fecha_fin": s["fin"], "cwd": s["cwd"], "rama_git": s["rama"],
        "claude_code_version": s["version"], "subagente": s["subagente"],
        "estado_obsidian_previo": estado, "fuente": s["archivo"],
        "generado": dt.datetime.now().isoformat(timespec="seconds"),
        "tags": ["claude/historico", f"claude/{tipo}", "graphify/pendiente"],
    }
    y = "---\n" + "\n".join(
        f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fm.items()) + "\n---\n"
    R = lambda x: redactar(recortar(x))
    partes = [
        y,
        f"# {titulo}\n",
        f"Vinculado a: [[{MAESTRO}]]\n",
        "> Nota generada automáticamente desde el transcript real. Las secciones marcadas "
        "*(revisar)* son extracción automática: Hermes/Ollama deben completarlas sin inventar.\n",
        "## FECHA/HORA\n" + f"- Inicio: {s['inicio']}\n- Fin: {s['fin']}\n",
        "## SESIÓN/ORIGEN\n" + f"- session_id: `{s['session_id']}`\n- Directorio: `{s['cwd']}`\n"
        f"- Rama git: `{s['rama']}`\n- Transcript: `{s['archivo']}`\n- Mensajes: {s['mensajes']}"
        f" (líneas ilegibles: {s['lineas_malas']})\n",
        "## OBJETIVOS *(primeros mensajes del usuario)*\n" + lista(objetivos, lambda t: R(t).replace("\n", "\n  ")),
        "\n## RESÚMENES DE COMPACTACIÓN *(los escribió Claude al llegar al límite de contexto; muy valiosos)*\n"
        + lista(s["resumenes"], lambda t: R(t).replace("\n", "\n  "), "_(ninguno)_"),
        "\n## DECISIONES *(revisar)*\n_(Pendiente de extracción por Hermes/Ollama a partir de las secciones de abajo.)_\n",
        "## CAMBIOS REALIZADOS / ARCHIVOS MODIFICADOS\n" + lista(sorted(s["archivos"]), lambda f: f"`{redactar(f)}`"),
        "\n## PRUEBAS / COMANDOS EJECUTADOS\n" + lista(
            s["comandos"], lambda c: f"{c[0]} [{c[1]}] {redactar(c[2])}: `{redactar(recortar(c[3], 300)).replace(chr(10), ' ⏎ ')}`"),
        "\n## PASS/FAIL *(líneas detectadas en las respuestas)*\n" + lista(pf, lambda l: redactar(l)),
        "\n## ERRORES *(resultados de herramientas con error)*\n" + lista(
            s["errores"], lambda e: f"{e[0]} [{e[1]}] {redactar(recortar(e[2], 400)).replace(chr(10), ' ⏎ ')}"),
        "\n## BACKUPS mencionados\n" + lista(backups, lambda b: f"`{redactar(b)}`"),
        "\n## CONFIGURACIONES — puertos / rutas / correlation IDs\n"
        f"- Puertos: {', '.join(puertos) or '—'}\n- correlation_id: {', '.join(corr) or '—'}\n"
        + lista(rutas, lambda r: f"`{redactar(r)}`", "- Rutas: —"),
        "\n## TAREAS PENDIENTES / BLOQUEOS / SIGUIENTE ACCIÓN *(último mensaje de Claude — revisar)*\n"
        + (R(ult_asist) or "_(sin respuesta final)_"),
        "\n## CONVERSACIÓN (texto visible, sin razonamiento interno)\n",
    ]
    conv = sorted([(ts or "", "USUARIO", t) for ts, t in s["usuario"]] +
                  [(ts or "", "CLAUDE", t) for ts, t in s["asistente"]])
    for ts, quien, t in conv:
        partes.append(f"**{quien}** · {ts}\n\n{R(t)}\n")
    if donde:
        partes.append("\n## YA EXISTÍA EN OBSIDIAN\n" + lista(donde, lambda r: f"`{r}`"))
    return "\n".join(partes)


def escribir_sin_pisar(path, txt):
    path.parent.mkdir(parents=True, exist_ok=True)
    final, n = path, 1
    while final.exists():
        n += 1
        final = path.with_name(f"{path.stem}__v{n}{path.suffix}")
    with open(final, "x", encoding="utf-8") as fh:   # 'x' = falla si existe: nunca sobrescribe
        fh.write(txt)
    return final


def nombre_nota(s):
    fecha = (s["inicio"] or "0000-00-00")[:10]
    t = re.sub(r"[^\w\-]+", "_", (s["titulo"] or "sesion"), flags=re.UNICODE).strip("_")[:50]
    return f"{fecha}_{s['session_id'][:8]}_{t}.md"


# ---------------------------------------------------------------- inventario de otros archivos
PATRON_REL = re.compile(r"claude|session|sesion|transcript|checkpoint|titan_tasks|bandeja|dispatcher|handoff|resumen", re.I)


def inventario_archivos(raices, limite=5000):
    out = []
    for r in raices:
        r = Path(r)
        if not r.exists():
            continue
        for dirpath, dirnames, files in os.walk(r):
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__", ".venv", "venv")]
            for f in files:
                if PATRON_REL.search(f) or PATRON_REL.search(dirpath):
                    p = Path(dirpath) / f
                    try:
                        st = p.stat()
                        out.append((str(p), st.st_size, dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")))
                    except OSError:
                        pass
                    if len(out) >= limite:
                        return out
    return out


# ---------------------------------------------------------------- modos
def raiz_claude():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))


def modo_rescate(a):
    proyectos = [Path(p) for p in (a.proyectos or [raiz_claude() / "projects"])]
    jsonls = sorted({p for d in proyectos if d.exists() for p in d.rglob("*.jsonl")})
    print(f"Transcripts encontrados: {len(jsonls)} en {[str(p) for p in proyectos]}")
    idx = indexar_vaults(a.vault)
    print(f"Notas .md indexadas en vaults: {len(idx)}")
    ahora = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    filas, cont = [], {}
    destino = Path(a.destino) / CARPETA if a.destino else None
    if a.escribir and not destino:
        sys.exit("ERROR: --escribir requiere --destino (no se elige vault automáticamente).")
    for p in jsonls:
        try:
            s = leer_sesion(p)
        except Exception as e:
            filas.append({"archivo": str(p), "estado": "NO_RECUPERABLE", "motivo": repr(e)})
            cont["NO_RECUPERABLE"] = cont.get("NO_RECUPERABLE", 0) + 1
            continue
        if not s["usuario"] and not s["asistente"] and not s["resumenes"]:
            estado, donde = "NO_RECUPERABLE", []
        else:
            estado, donde = estado_en_obsidian(s, idx)
        cont[estado] = cont.get(estado, 0) + 1
        fila = {"session_id": s["session_id"], "titulo": s["titulo"], "inicio": s["inicio"], "fin": s["fin"],
                "cwd": s["cwd"], "mensajes": s["mensajes"], "estado": estado, "en": donde[:5], "archivo": str(p)}
        if a.escribir and estado in ("NO_ESTA_EN_OBSIDIAN", "PARCIALMENTE_GUARDADA"):
            ruta = escribir_sin_pisar(destino / "sesiones" / nombre_nota(s), nota_sesion(s, estado, donde))
            fila["nota_nueva"] = str(ruta)
            cont["NUEVAS_GUARDADAS"] = cont.get("NUEVAS_GUARDADAS", 0) + 1
        filas.append(fila)
    otros = inventario_archivos(a.buscar) if a.buscar else []
    informe = {"generado": ahora, "transcripts": len(jsonls), "conteo": cont, "sesiones": filas,
               "otros_archivos_relacionados": otros}
    print(json.dumps(cont, ensure_ascii=False, indent=2))
    if a.escribir:
        destino.mkdir(parents=True, exist_ok=True)
        escribir_sin_pisar(destino / "informes" / f"rescate_{ahora}.json",
                           redactar(json.dumps(informe, ensure_ascii=False, indent=1)))
        filas_md = "\n".join(
            f"| {f.get('inicio', '')[:16] if f.get('inicio') else ''} | `{(f.get('session_id') or '')[:8]}` | "
            f"{redactar((f.get('titulo') or '').replace('|', '/'))[:60]} | {f['estado']} | "
            f"{('[[' + Path(f['nota_nueva']).stem + ']]') if f.get('nota_nueva') else ''} |"
            for f in sorted(filas, key=lambda f: f.get("inicio") or ""))
        idx_md = (f"---\ntipo: claude_indice\ngenerado: {ahora}\ntags: [claude/historico, graphify/pendiente]\n---\n"
                  f"# Índice histórico Claude ({ahora})\n\n[[{MAESTRO}]]\n\n"
                  f"```\n{json.dumps(cont, ensure_ascii=False, indent=1)}\n```\n\n"
                  "| Inicio | Sesión | Título | Estado previo | Nota |\n|---|---|---|---|---|\n" + filas_md +
                  (f"\n\n## Otros archivos relacionados encontrados ({len(otros)})\n" +
                   "\n".join(f"- `{redactar(r)}` · {sz} B · {m}" for r, sz, m in otros[:2000]) if otros else ""))
        print("Índice:", escribir_sin_pisar(destino / f"INDICE_CLAUDE_HISTORICO_{ahora}.md", idx_md))
    else:
        salida = Path(a.informe or f"rescate_simulacion_{ahora}.json")
        salida.write_text(redactar(json.dumps(informe, ensure_ascii=False, indent=1)), encoding="utf-8")
        print(f"SIMULACIÓN: no se ha escrito nada en Obsidian. Informe: {salida.resolve()}")


def modo_checkpoint(a):
    """Hook de Claude Code. Nunca falla ruidosamente: un hook roto no debe bloquear a Claude."""
    try:
        datos = json.load(sys.stdin)
    except Exception:
        datos = {}
    tp = datos.get("transcript_path")
    evento = datos.get("hook_event_name", "manual")
    if not tp or not Path(tp).exists():
        return
    destino = Path(a.destino) / CARPETA / "checkpoints"
    sid = datos.get("session_id") or Path(tp).stem
    marca = destino / f".ultimo_{sid[:8]}"
    if evento == "Stop" and marca.exists():
        edad = dt.datetime.now().timestamp() - marca.stat().st_mtime
        if edad < a.intervalo_min * 60:
            return   # throttle: en Stop solo cada N minutos
    s = leer_sesion(Path(tp))
    if not s["usuario"] and not s["asistente"]:
        return
    ahora = dt.datetime.now().strftime("%Y%m%d_%H%M")
    ruta = escribir_sin_pisar(destino / f"{ahora}_{sid[:8]}_{evento}.md",
                              nota_sesion(s, "checkpoint", [], tipo="checkpoint"))
    marca.parent.mkdir(parents=True, exist_ok=True)
    marca.write_text(str(ruta), encoding="utf-8")


def modo_instalar_hooks(a):
    """Añade (sin quitar nada) hooks PreCompact/SessionEnd/Stop a ~/.claude/settings.json, con backup previo."""
    cfg = raiz_claude() / "settings.json"
    datos = {}
    if cfg.exists():
        datos = json.loads(cfg.read_text(encoding="utf-8") or "{}")
        bak = escribir_sin_pisar(cfg.with_name(f"settings_BACKUP_{dt.datetime.now():%Y%m%d_%H%M%S}.json"),
                                 cfg.read_text(encoding="utf-8"))
        print("Backup:", bak)
    py = sys.executable.replace("\\", "/")
    script = str(Path(__file__).resolve()).replace("\\", "/")
    dest = str(Path(a.destino)).replace("\\", "/")
    cmd = f'"{py}" "{script}" checkpoint --destino "{dest}" --intervalo-min {a.intervalo_min}'
    hooks = datos.setdefault("hooks", {})
    for evento in ("PreCompact", "SessionEnd", "Stop"):
        grupos = hooks.setdefault(evento, [])
        if any("rescate_claude.py" in h.get("command", "") for g in grupos for h in g.get("hooks", [])):
            print(f"{evento}: ya instalado, no se toca")
            continue
        grupos.append({"hooks": [{"type": "command", "command": cmd, "timeout": 60}]})
        print(f"{evento}: añadido")
    if a.simular:
        print(json.dumps(datos, ensure_ascii=False, indent=2))
        return
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK:", cfg)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="modo", required=True)
    r = sub.add_parser("rescate")
    r.add_argument("--vault", action="append", default=[], help="vault a consultar (repetible, solo lectura)")
    r.add_argument("--destino", help="vault donde escribir CLAUDE_HISTORICO/")
    r.add_argument("--proyectos", action="append", help="carpeta(s) de transcripts; defecto ~/.claude/projects")
    r.add_argument("--buscar", action="append", help="raíces extra a inventariar (p.ej. I:\\CEREBRO); solo lista")
    r.add_argument("--escribir", action="store_true", help="escribir de verdad (sin esto: simulación)")
    r.add_argument("--informe", help="ruta del informe JSON en simulación")
    c = sub.add_parser("checkpoint")
    c.add_argument("--destino", required=True)
    c.add_argument("--intervalo-min", type=int, default=20, dest="intervalo_min")
    h = sub.add_parser("instalar-hooks")
    h.add_argument("--destino", required=True)
    h.add_argument("--intervalo-min", type=int, default=20, dest="intervalo_min")
    h.add_argument("--simular", action="store_true")
    a = ap.parse_args()
    if a.modo == "rescate":
        modo_rescate(a)
    elif a.modo == "instalar-hooks":
        modo_instalar_hooks(a)
    else:
        try:
            modo_checkpoint(a)
        except Exception as e:  # el hook nunca debe romper la sesión
            print(f"[rescate_claude checkpoint] {e!r}", file=sys.stderr)


if __name__ == "__main__":
    main()
