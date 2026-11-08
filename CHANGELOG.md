# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[versionado semántico](https://semver.org/lang/es/).

## [0.3.0] - 2026-11-08

Fase 3 · Seguridad completa y demo del ataque. Ninguna llamada al modelo real.

### Agregado

- Guardián, capa 1 completa (`fabrica/seguridad/guardian.py`): además de la ruta y el tamaño,
  UTF-8 estricto, caracteres de control, Unicode oculto o bidireccional (U+200B–200F, U+202A–202E,
  U+2066–2069, U+FEFF) y patrones de inyección normalizados con NFKC; marca URLs y bloques de código.
- `historias/HU-99-exportar-antiguedad.md`: la historia maliciosa de la demo (tal como el diseño).
- Sandbox endurecido: `rlimit` de CPU (30 s), tamaño de archivo (5 MB) y descriptores (128) con un
  `preexec_fn`, sin `RLIMIT_NPROC`; sonda cacheada de `sandbox-exec` y su perfil SBPL (niega la red,
  la escritura fuera de la carpeta temporal y la lectura del señuelo, `.env` y `datos/`).
- Pruebas sin modelo: `test_guardian` (tabla de casos), ampliaciones de `test_revision_codigo`,
  `test_sandbox` (rlimit, sandbox-exec y defensa en profundidad), `test_log` (los 10 eventos) y la
  demo de HU-99 en `test_grafo` (con y sin `DEFENSAS`). 244 pruebas, cobertura 97 %.
- `sonda` hace una segunda llamada barata que prueba `--json-schema` con `Especificacion` y valida
  el `structured_output` con Pydantic (preparación de la fase 4; no se ejecuta).

### Cambiado

- Revisión estática: se cierran tres atajos que la lista blanca aceptaba (`pytest.importorskip`,
  `typing.get_type_hints`, `"{0.real.__class__}".format(...)`) y otros del mismo tipo
  (`make_dataclass`, `str.format_map`) con un conjunto de atributos prohibidos y la regla de que
  ninguna cadena contenga `__`. No se quitó la lista blanca de imports.
- `DEFENSAS=0` apaga la detección de inyección de la capa 1 y el filtro, pero **no** el límite de
  ruta, tamaño y UTF-8 (`revisar_ruta`): así el señuelo nunca se lee y HU-99 puede llegar a los
  agentes para la demo de defensa en profundidad. Precisión anotada en el diseño (sección 10.3).

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
