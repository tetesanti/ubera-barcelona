# Rescate del histórico de Claude a Obsidian

`rescate_claude.py` (Python 3, solo biblioteca estándar):

- Lee los transcripts reales de Claude Code (`%USERPROFILE%\.claude\projects\**\*.jsonl`). No los borra ni los modifica.
- Busca cada sesión en uno o varios vaults (solo lectura) y la clasifica como `YA_ESTA_EN_OBSIDIAN`, `PARCIALMENTE_GUARDADA`, `NO_ESTA_EN_OBSIDIAN` o `NO_RECUPERABLE`.
- Con `--escribir` crea una nota por sesión en `<vault>\CLAUDE_HISTORICO\sesiones\`. Nunca sobrescribe: si el archivo ya existe, crea `__v2`, `__v3`…
- Redacta secretos (claves API, tokens de GitHub/Telegram/JWT, contraseñas) antes de escribir.
- No guarda el razonamiento interno (bloques `thinking`).
- Las notas llevan frontmatter YAML, la etiqueta `graphify/pendiente` y un enlace a `[[CLAUDE_ESTADO_MAESTRO_24SEP2026]]`, listas para Graphify.

## Uso en el PC

```powershell
mkdir I:\CEREBRO\claude_rescate
# copia aquí rescate_claude.py

# 1) Simulación (no escribe en Obsidian)
py I:\CEREBRO\claude_rescate\rescate_claude.py rescate --vault I:\CEREBRO\obsidian_vault --vault I:\CEREBRO\obsidian_vault_titan --buscar I:\CEREBRO --informe I:\CEREBRO\claude_rescate\simulacion.json

# 2) Rescate real en el vault que elijas (no fusiona)
py I:\CEREBRO\claude_rescate\rescate_claude.py rescate --vault I:\CEREBRO\obsidian_vault --vault I:\CEREBRO\obsidian_vault_titan --destino I:\CEREBRO\<VAULT_ELEGIDO> --buscar I:\CEREBRO --escribir

# 3) Autoguardado futuro (hace backup de settings.json y solo AÑADE hooks)
py I:\CEREBRO\claude_rescate\rescate_claude.py instalar-hooks --destino I:\CEREBRO\<VAULT_ELEGIDO>
```

Es seguro volver a ejecutar el paso 2: las sesiones que ya tienen nota salen como `YA_ESTA_EN_OBSIDIAN` y no se duplican.

## Autoguardado

Los hooks de Claude Code llaman a `rescate_claude.py checkpoint` y escriben en `<vault>\CLAUDE_HISTORICO\checkpoints\`:

| Evento | Cuándo se guarda |
|---|---|
| `PreCompact` | Justo antes de que Claude compacte por el límite de tokens. |
| `SessionEnd` | Al cerrar la sesión. |
| `Stop` | Al final de cada turno, como mucho cada 20 min (`--intervalo-min`). |

Cada checkpoint es un archivo nuevo. Si el hook falla, no interrumpe la sesión de Claude.
