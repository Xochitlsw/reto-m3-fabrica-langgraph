# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[versionado semántico](https://semver.org/lang/es/).

## [1.1.0] - 2026-11-08

Fase 6 · Ajustes finales (sin llamadas al modelo real).

### Agregado

- `README.md`: sección «Features de LangGraph» (feature → archivo y símbolo → curso o verificado) y
  sección «Integración continua».
- Integración continua: `.github/workflows/ci.yml` (GitHub Actions, `ubuntu-latest`, Python 3.12 con
  `uv`): `uv sync --frozen`, `ruff check` y `pytest` con cobertura. Las pruebas que dependen de
  macOS (`sandbox-exec`) o del binario `claude` se saltan solas en Linux.

### Cambiado

- Cobertura: `fail_under = 80` en `[tool.coverage.report]`. `uv run pytest --cov=fabrica` ahora falla
  si baja del 80 % (hoy: 96.7 %).

### No hecho (y por qué)

- **Subgrafo `seguridad_entrada`** (agrupar guardián y filtro, punto 4, opcional): no se hizo. Habría
  cambiado la salida de `draw_mermaid` (y por tanto `docs/grafo.md`), lo que rompe las aserciones de
  aristas y orden de nodos de `test_grafo`, y habría obligado a reencaminar «bloqueada → fin» en el
  grafo padre y a propagar el checkpointer al subgrafo, tocando las pruebas de SQLite entre procesos.
  El enunciado pedía no hacerlo si complicaba las pruebas existentes; esto las complicaba, para una
  mejora solo cosmética del grafo.

## [1.0.0] - 2026-11-08

Fase 5 · Documentación y publicación. Primera versión completa del reto.

### Agregado

- `README.md` pensado para el onboarding: qué hace la fábrica, el diagrama, la tabla de agentes y
  nodos, requisitos, instalación, uso de la CLI con un ejemplo real de `HU-05-real` (pausas,
  rechazo, aprobación y resultado), pruebas y `ruff`, las cinco medidas de seguridad y la demo
  (HU-98/HU-99), dónde está la evidencia, estructura, limitaciones y costos observados.
- `evidencia/reflexion.md`: borrador de la reflexión (qué funcionó, qué mejorar, lecciones,
  tiempos por fase y costo total) para que la persona lo edite.

### Verificado

- Docstrings completos en `fabrica/` (`ruff --select D100,D101,D102,D103,D104`: sin faltantes).
- `docs/conocimiento/`, `datos/`, `logs/`, `salida/` y `.env` quedan fuera del repositorio
  (`git check-ignore`); el único «secreto» versionado es el señuelo `secretos_demo.txt` (bandera
  falsa, a propósito). No hay secretos reales en el repo.

## [0.4.0] - 2026-11-08

Fase 4 · Corridas con el modelo real (gasta cuota de la suscripción).

### Agregado

- `historias/HU-98-soporte.md`: historia sutil para mostrar la capa 2 (el filtro con haiku la marca
  aunque pase las reglas de la capa 1).
- `evidencia/corridas/sonda.md` y `evidencia/corridas/HU-05-real/` (reporte, llamadas, código,
  pruebas y log de seguridad de la corrida real) y `evidencia/capturas/` con la corrida punta a punta.
- Pruebas sin modelo del hueco de la aclaración (`test_aclarar_continuar_conserva_el_comentario`,
  `test_aclarar_continuar_sin_comentario_no_guarda_nada`,
  `test_planificador_recibe_la_guia_de_la_aclaracion`). 247 pruebas, cobertura 97 %.

### Corregido

- **El comentario de «continuar» en la aclaración no llegaba al planificador** (hallado en la corrida
  real `HU-05-real`): se registraba en el log pero no entraba al estado, así que había que rechazar
  el plan para reintroducir esa guía. Ahora `nodo_aclarar` lo guarda en `respuestas_aclaracion` y el
  planificador lo incluye entre `<respuestas_operador>`. Diseño, sección 10.2, punto 8.

### Cambiado

- `ruff` excluye `evidencia/corridas` y `salida` (código generado por el modelo, no fuente del
  proyecto).

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
