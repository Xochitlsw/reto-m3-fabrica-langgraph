# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[versionado semántico](https://semver.org/lang/es/).

## [0.2.0] - 2026-11-08

Fase 2 · Núcleo LangGraph con modelo falso. Ninguna llamada al modelo real.

### Agregado

- Proyecto con Python 3.12 (`.python-version`), `pyproject.toml` con versiones fijas
  (langgraph 1.2.17, langgraph-checkpoint-sqlite 3.1.2, pydantic 2.14.1; pytest 9.1.1,
  pytest-cov 7.1.0, ruff 0.17.2), `exclude-newer` y `uv.lock`.
- Insumos: `historias/HU-05-consultar-antiguedad.md`, `contexto/reglas_negocio.md` (reglas 1–13),
  `config/operadores.json` y el señuelo `secretos_demo.txt`; `.claude/settings.json` con `deny`.
- `fabrica/estado.py` (`EstadoFabrica` con reductores) y `fabrica/contratos.py` (contratos
  Pydantic y validadores; las reglas citadas se leen de `reglas_negocio.md`).
- `fabrica/modelo.py`: envoltorio de `claude -p` sin herramientas ni MCP, sin `ANTHROPIC_API_KEY`
  ni `CLAUDECODE`, con `cwd` temporal, sonnet/haiku y `--max-budget-usd`.
- `fabrica/falso.py`: modelo falso sin memoria con 8 escenarios y un `antiguedad.py` real.
- `fabrica/seguridad/`: log de seguridad, revisión estática con AST y lista blanca, sandbox básico
  (carpeta temporal, entorno limpio, timeout, JUnit) y guardián mínimo (ruta y tamaño).
- 7 prompts endurecidos (`fabrica/prompts/`) y 7 agentes con contrato, validador y un reintento.
- `fabrica/supervisor.py` (`decidir`, reglas R0–R15 con `Command`), `fabrica/humano.py` (3 pausas
  con `interrupt`) y `fabrica/grafo.py` (grafo, nodo `fin`, evidencia automática).
- CLI `python -m fabrica` con `iniciar`, `aprobar`, `estado`, `grafo` y `sonda`, sobre
  `SqliteSaver` y con `LANGGRAPH_STRICT_MSGPACK=true`; `docs/grafo.md` generado.
- 196 pruebas sin modelo (cobertura 96 %), incluida la reanudación en procesos distintos.

### Cambiado

- El planificador no puede repetir el plan que la persona rechazó: sin esta regla el rechazo
  seguía vigente y el flujo daba vueltas hasta el tope R0.
- `CLAUDE.md`: el diagrama refleja el grafo real (`fin → END`, nombres de los nodos).

## [0.1.0] - 2026-11-08

Fase 1 · Arranque y diseño.

### Agregado

- `docs/diseno.md`: diseño aprobado de la fábrica (grafo, contratos, reglas del supervisor, estado,
  checkpoints en SQLite, pausas humanas, seguridad, envoltorio de `claude -p`, CLI, estructura,
  dependencias, features de LangGraph y orden de construcción de la fase 2).
- `evidencia/prompts.md`: registro literal de las instrucciones, con fecha y fase.
- `CLAUDE.md`: arquitectura, las cinco medidas de seguridad, convenciones y reglas de trabajo.
