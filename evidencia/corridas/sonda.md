# Sonda · verificación del envoltorio de `claude -p`

Fase 4, punto 1. Dos llamadas reales baratas con **haiku** para verificar el envoltorio
antes de las corridas de la fase 4. No llama a ningún agente de la fábrica.

- Fecha: 2026-11-08, ~15:57 CST
- Modelo: `haiku` (ambas llamadas)
- Confirmación de gasto: sí (bandera `--si`, tras confirmación explícita)

## Comando

```bash
uv run python -m fabrica sonda --si
```

## Salida completa

```text
[1/2] tools: [] · mcp_servers: []
      tokens de entrada: 949 · turnos: 1 · costo: 0.0003193 USD · resultado: 'ok'
[2/2] --json-schema aceptado; Especificacion válida (2 criterios); validador: sin problemas · costo: 0.001437 USD
```

## Lectura de los resultados

| Verificación | Resultado |
| --- | --- |
| **[1/2] cwd limpio** | `tools: []` y `mcp_servers: []`: el envoltorio corre sin herramientas integradas ni conectores MCP. |
| **Tokens de entrada** | **949**, muy por debajo de los ~1 900 tokens que sumaría `CLAUDE.md` (6 649 B). Confirma que, con el `cwd` temporal y el entorno sin `CLAUDECODE`, **no se carga `CLAUDE.md`**. |
| **[2/2] `--json-schema` con `Especificacion`** | **Aceptado**: el contrato anidado más grande (con `$defs`, `pattern` y límites) no fue rechazado por la CLI. |
| **structured_output** | Cumple el contrato `Especificacion` (2 criterios) y pasa el validador de negocio (`validar_especificacion`: sin problemas). |

## Costo

| Llamada | Costo (USD) |
| --- | --- |
| [1/2] cwd limpio (`stream-json`) | 0.0003193 |
| [2/2] esquema (`--json-schema`) | 0.0014370 |
| **Total** | **0.0017563** |

Tope previsto: ~0.15 USD. Gasto real: **~0.0018 USD** (menos de un centavo).
