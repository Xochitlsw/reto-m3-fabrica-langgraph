# Registro de instrucciones

Cada instrucción que recibió Claude Code durante el reto: texto literal, fecha y fase. Las
referencias `@archivo` son las que se usaron para darle contexto al agente (requisito R3).

## 2026-11-08 · Fase 1A · Arranque

```text
Fase 1A · Arranque. Estás en modo plan: no crees archivos ni instales nada todavía.

1. Lee @docs/conocimiento/README.md, @docs/conocimiento/reto_checklist.md y @docs/conocimiento/m3b_fabrica.md (CLAUDE.md ya lo tienes cargado).
2. Verifica el entorno y muéstrame cada comando con su salida:
   uv --version
   uv python list
   claude --version
   echo "${ANTHROPIC_API_KEY:-sin clave}"
   docker --version
   git status --short
3. Respóndeme en 10 líneas como máximo: qué entendiste del reto, qué herramientas faltan o fallan y cualquier contradicción que veas entre CLAUDE.md, el checklist y m3b_fabrica.md.

No diseñes todavía: el resumen de LangGraph (docs/conocimiento/langgraph_m3.md) se está terminando y te lo paso en la siguiente instrucción.
```

Resultado: entorno verificado. Funcionan uv 0.13.7, CPython 3.12.16 (instalado por uv), Claude Code
2.1.319 con la sesión de claude.ai y sin `ANTHROPIC_API_KEY`. No hay Docker y `gh` no tiene sesión.
Se señalaron tres contradicciones (el guardián, la corrección y el envoltorio) y faltaban las reglas
de HU-05.

## 2026-11-08 · Fase 1 · Respuestas a la 1A (decisiones)

```text
Respuestas a tu 1A. Son decisiones: aplícalas en el diseño.

1. Python: fija 3.12 con .python-version y `uv venv --python 3.12`; nunca uses el python3 del PATH (3.11).
2. Sandbox sin Docker: subproceso en carpeta temporal, timeout, entorno limpio, PYTHONDONTWRITEBYTECODE=1, pytest con `-p no:cacheprovider` y rlimit de CPU, tamaño de archivo y archivos abiertos (no uses RLIMIT_NPROC: en macOS cuenta todos los procesos del usuario). La capa principal es la revisión estática previa con LISTA BLANCA de imports, no lista negra. Si `sandbox-exec` existe y una prueba rápida confirma que funciona, úsalo además para negar la red y la escritura fuera de la carpeta temporal; si no, documenta la limitación (incluida la de RLIMIT_AS en macOS).
3. Guardián: las dos capas, como enseña M3B. Primero reglas en código (gratis, siempre); si pasan, un clasificador con modelo (filtro con contrato Veredicto, sin herramientas, modelo pequeño): es el séptimo agente. Si las reglas bloquean, no se llama al modelo. Un falso positivo termina en BLOQUEADA y decide una persona. DEFENSAS=0 apaga las dos capas, solo para la demo.
4. Corrección: adopta el triage de M3B dentro del reviewer. Su contrato Revision incluye veredicto (aprobar | corregir), responsable (implementador | tester), el criterio de la especificación que no se cumple y observaciones. Su prompt lleva la regla «la especificación manda: si la prueba y el código no coinciden, gana quien siga la especificación». El supervisor valida en código: nunca aprueba con pruebas fallidas aunque el reviewer diga «aprobar», y manda la corrección al responsable. Tope: 2 ciclos de corrección en total; al llegar al tope, pausa humana (aceptar con observaciones o terminar sin entregar).
5. Envoltorio de claude -p: amplíalo para quitar ANTHROPIC_API_KEY y CLAUDECODE, y márcalo en el código como adaptación que no viene del curso. Además, corre claude -p con cwd en una carpeta temporal vacía, no en la raíz del repo: desde la raíz cargaría el CLAUDE.md de esta sesión en cada llamada de cada agente (más tokens y un contexto ajeno a su rol). Propón cómo verificarlo con una sola llamada barata (por ejemplo, comparando usage.input_tokens).
6. Supervisor en código: justifícalo con el curso, «con pasos conocidos, es más barato y más predecible» (m3api_sesion03, pág 18; langgraph_m3.md, sección 4.5). Usa Command(goto=...) desde el nodo supervisor si encaja.
7. HU-05: agrega estas reglas a contexto/reglas_negocio.md, siguiendo su numeración:
   8. La antigüedad se calcula en años y meses completos entre la fecha de ingreso y una fecha de corte; los días sobrantes no cuentan. Ejemplo: ingreso 2019-03-04 y corte 2026-11-08 → «7 años y 8 meses».
   9. La fecha de corte es la de hoy, salvo que se indique otra.
   10. Un mes se completa el mismo día del mes siguiente; si ese día no existe (por ejemplo, ingreso el día 31), se completa el último día de ese mes.
   11. Para un empleado dado de baja, la antigüedad se calcula hasta su fecha de baja. La lista para reconocimientos solo incluye empleados activos.
   12. Si la fecha de ingreso es posterior a la fecha de corte, responde el error «La fecha de ingreso no puede ser posterior a la fecha de corte».
   13. Se muestra como «N años y M meses», en singular cuando corresponde («1 año y 1 mes»).
8. Cuando te autorice a escribir: registra en evidencia/prompts.md la 1A, esta respuesta y la 1B, con fecha y fase, y actualiza CLAUDE.md con estas decisiones.
```

## 2026-11-08 · Fase 1B · Diseño

```text
Fase 1B · Diseño. Sigues en modo plan: todavía no crees archivos ni instales nada.

Lee @docs/conocimiento/langgraph_m3.md (ya está completo) y vuelve a leer @docs/conocimiento/reto_checklist.md (actualicé las secciones 3 y 6). De m3b_fabrica.md usa lo que necesites, sobre todo las secciones 5, 6, 7 y 9.

Propón el contenido de docs/diseno.md aplicando las decisiones de arriba:
a. El grafo: diagrama Mermaid; cada nodo con su rol, entrada, salida y contrato Pydantic; las reglas del supervisor y sus topes (2 rechazos del plan, 2 ciclos de corrección).
b. El estado compartido: campos, tipos y reductores.
c. Checkpoints: el curso solo usa InMemorySaver. Propón cómo persistir en SQLite para que `iniciar` se detenga en la pausa y `aprobar` retome en otro proceso con el mismo thread_id. Antes de proponerlo, verifica en la documentación oficial de LangGraph el paquete y la API, y dime qué verificaste y dónde.
d. Las pausas humanas (aprobar el plan, aclarar las preguntas abiertas del especificador, escalar al tope): qué ve la persona, qué puede responder y cómo se identifica quien decide (queda en el log de seguridad).
e. Las medidas de seguridad: qué revisa cada una, en qué nodo vive y cómo se prueba sin modelo; el interruptor DEFENSAS.
f. El envoltorio de claude -p y el modelo falso para las pruebas.
g. La CLI: iniciar, aprobar, estado y grafo, con ejemplos de uso.
h. Estructura de carpetas, dependencias (fija las versiones que instales) e insumos: historias/HU-05-consultar-antiguedad.md (del backlog), una historia maliciosa HU-99 escrita por ti para la demo, contexto/reglas_negocio.md con las reglas nuevas y secretos_demo.txt.
i. Las features de LangGraph que usarás, marcando cuáles vienen del curso y cuáles son de fuera y ya verificadas.
j. El orden de construcción de la fase 2 en pasos cortos, cada uno con su prueba sin modelo.

Señala las decisiones abiertas con tu recomendación. No escribas código todavía.
```

Resultado: propuesta de diseño con las secciones a–j y 9 decisiones abiertas. Se verificó la API
de `SqliteSaver`, `get_state` e `interrupt` en la documentación oficial y se probó que `sandbox-exec`
bloquea la red en macOS 27.

## 2026-11-08 · Fase 1B · Revisión del diseño

```text
Revisión del diseño: aprobado con estos ajustes. Incorpóralos al plan, preséntalo otra vez y, cuando lo apruebe, cierra la fase 1 como propones (prompts.md, diseno.md y CLAUDE.md; diff y mensaje de commit propuesto).

Decisiones abiertas:
1. Código en el estado (≤ 64 KB) + copia en disco: sí.
2. DEFENSAS=0 apaga solo las dos capas del guardián y el log sigue encendido: sí; documenta la diferencia con M3B.
3. Abanico implementador ∥ tester, con un tester que no ve el código: sí. Si Command(goto=lista) falla en el paso 9, usa la arista condicional que devuelve una lista (como el curso, s3 pág 13); si tampoco funciona, en secuencia.
4. Aclaración con responder (1 vez): sí.
5. HU-98 sutil: sí, en la fase 4 si hay tiempo.
6. Subcomando sonda: sí. Además, en el paso 4 comprueba con `claude --help` (sin gastar) que existen todas las banderas del envoltorio, sobre todo --strict-mcp-config, --max-budget-usd y --json-schema.
7. Versiones: fija la última versión de cada paquete que tenga al menos dos semanas de publicada (la entrega es hoy: estabilidad antes que novedad). Si algo de lo que verificaste no existe en esa versión, sube a la más reciente y anota por qué.
8. Modelos: haiku para el filtro; para los demás, sonnet por omisión, con FABRICA_MODELO para cambiarlo (más rápido y gasta menos cuota); --max-budget-usd 0.50 por llamada.
9. bandit y CI: después de la fase 5, si sobra tiempo.

Ajustes:
A. Rango de reglas: el validador de la especificación toma los números de regla de contexto/reglas_negocio.md, no un 13 fijo.
B. Evidencia automática: como salida/ no se versiona, en una corrida con el modelo real el nodo fin copia a evidencia/corridas/<hilo>/ el reporte, la bitácora, las llamadas (agente, tokens, costo, segundos) y el código, las pruebas y la documentación generados.
C. Tiempo: la fase 2 no debe pasar de 2 horas. Si se alarga, recorta en este orden y anótalo en el diseño: HU-98, sandbox-exec, stream (usa invoke y la bitácora), responder en la aclaración, abanico (en secuencia). No recortes nunca: las 3 pausas, SQLite + get_state, la lista blanca, el log ni las pruebas sin modelo.
```

Resultado: diseño aprobado con los ajustes. Las versiones quedaron en la última con ≥ 2 semanas
(langgraph 1.2.17, langgraph-checkpoint-sqlite 3.1.2, pydantic 2.14.1, pytest 9.1.1, pytest-cov
7.1.0, ruff 0.17.2). Al reordenar la fase 2 en 12 pasos, la prueba del abanico pasó del paso 9 al
paso 10. Se cerró la fase 1 con `docs/diseno.md`, este registro y `CLAUDE.md` actualizado.

## 2026-11-08 · Fase 1 · Cierre (commit)

```text
sí, haz el commit
```

Resultado: commit `95fe0b0` en `main` (primer commit del repositorio), sin push.

## 2026-11-08 · Fase 2 · Núcleo con modelo falso

```text
Fase 2 · Núcleo con modelo falso.

Sigue los pasos 1 a 12 de @docs/diseno.md (sección 10) en orden; no pases a un paso sin que su prueba esté en verde. En esta fase no hay ninguna llamada al modelo real. Respeta el tope de 2 horas y el punto de control del paso 6: corre `date` al empezar, en ese punto de control y al terminar.

- Registra esta instrucción en evidencia/prompts.md.
- Paso 1: agrega salida/ a .gitignore y crea CHANGELOG.md (Keep a Changelog) con la entrada de la fase 1; en el paso 12 agrega la de la fase 2.
- Pasos 10 u 11: genera docs/grafo.md con `fabrica grafo` y compáralo con los diagramas de docs/diseno.md y CLAUDE.md; si no coinciden, corrige los diagramas escritos a mano para que reflejen el grafo real.
- Te autorizo commits locales, sin push, al terminar los pasos 6 y 10, con mensajes en español que digan qué quedó probado. El del paso 12 me lo propones.
- Si un paso se atora más de 20 minutos, detente y repórtame con la salida del error en lugar de rodearlo.
- Al terminar, repórtame en 25 líneas como máximo: la salida de `uv run pytest -q --cov=fabrica` (con el porcentaje) y de `uv run ruff check .`, la corrida de test_cli_procesos (iniciar → estado → aprobar con el mismo thread_id), qué resultó de lo que faltaba verificar (Command(goto=lista), stream y LANGGRAPH_STRICT_MSGPACK), los recortes aplicados, las horas de `date` y cualquier desviación del diseño con su motivo.
```

Resultado: pasos 1–12 en verde con el modelo falso (14:04 → 14:29), sin recortes. Commits locales
`051173f` (pasos 1–6) y `79f0644` (pasos 7–10); el del paso 12 se propuso. 196 pruebas, 96 % de
cobertura, `ruff` limpio. Se comprobaron `Command(goto=lista)`, `stream` y
`LANGGRAPH_STRICT_MSGPACK`; las desviaciones quedaron en `docs/diseno.md` (sección 10.2).

## 2026-11-08 · Fase 2 · Cierre (commit)

```text
sí al commit
```

Resultado: commit del paso 12 en `main` con el mensaje propuesto, sin push.

## 2026-11-08 · Fase 3 · Seguridad y demo del ataque

```text
Fase 3 · Seguridad y demo del ataque, con el modelo falso. Tope: 1 hora; corre `date` al empezar y al terminar.

Completa lo que la sección 5 de @docs/diseno.md deja para esta fase, con pruebas sin modelo:
1. Guardián, capa 1: todas las reglas de la sección 5 (ruta, symlink, nombre, tamaño, UTF-8, caracteres de control, Unicode oculto o bidi, patrones con NFKC), con una tabla de casos en test_guardian.
2. Filtro, capa 2: prompt endurecido y escenario `sospechosa` del falso: termina en BLOQUEADA, sin más llamadas.
3. Revisión estática. La sesión de apoyo comprobó con revisar() que hoy se ACEPTAN tres atajos:
   - pruebas: `pytest.importorskip("os")` importa cualquier módulo por su nombre;
   - implementación: `typing.get_type_hints(f)` evalúa como código una anotación escrita como texto;
   - implementación: `"{0.real.__class__}".format(1)` recorre atributos internos desde una cadena.
   Ciérralos sin quitar la lista blanca: atributos prohibidos (al menos importorskip, get_type_hints, ForwardRef, _evaluate, getattr, setattr, delattr) y cadenas que contengan "__". Busca también otros atajos del mismo tipo en los módulos permitidos. Cada atajo queda como caso en test_revision_codigo.
4. Sandbox: rlimit de CPU, tamaño de archivo y archivos abiertos; la sonda de sandbox-exec y su perfil (sin red, sin escritura fuera de la carpeta temporal y sin lectura del señuelo, de .env ni de datos/). Pruebas: bucle infinito, archivo enorme, socket bloqueado, lectura del señuelo bloqueada y escritura fuera de la carpeta bloqueada; las de sandbox-exec se saltan si no existe. Agrega una prueba de defensa en profundidad: con la revisión estática desactivada solo dentro de esa prueba, un código que usa importorskip("os") para leer el señuelo o abrir un socket falla dentro del sandbox.
5. Log de seguridad: todos los eventos de la sección 5, con sus claves obligatorias.
6. DEFENSAS=0 y la demo, con historias/HU-99 tal como está en el diseño. Pruebas: con defensas, la capa 1 la bloquea sin ninguna llamada al modelo; con DEFENSAS=0 y el escenario `ataque` del falso, la revisión estática rechaza el código, el flujo termina en ESCALAR y no aparece BANDERA-DEMO en salida/. Las dos corridas dejan rastro en el log.
7. Prepara la fase 4 sin gastar: amplía `sonda` con una segunda llamada barata (haiku) que use el contrato anidado más grande (Especificacion) y valide el structured_output con Pydantic, para detectar antes si --json-schema rechaza algo del esquema ($defs, pattern, límites). No la ejecutes.

Registra esta instrucción en evidencia/prompts.md; actualiza el CHANGELOG y, si algo cambia, la sección 5 del diseño. Al final propón el commit, sin hacerlo. Repórtame en 25 líneas como máximo: pytest con cobertura, ruff, la salida de las dos corridas de la demo con el falso (con y sin DEFENSAS), un extracto de 5 líneas de logs/seguridad.jsonl, qué otros atajos encontraste, si sandbox-exec funcionó, los recortes y las horas de date.
```

Resultado: 244 pruebas en verde (96 %→97 % de cobertura), `ruff` limpio, sin llamadas al modelo
real (14:38 → 15:40). Guardián capa 1 completo, tres atajos de la revisión estática cerrados
(+ `make_dataclass` y `format_map`), sandbox con `rlimit` y `sandbox-exec` (perfil comprobado), log
con los 10 eventos, demo de HU-99 con y sin `DEFENSAS`, y `sonda` ampliada con la prueba de
`--json-schema`/`Especificacion` (sin ejecutar). Diseño (secciones 5 y 10.3) y CHANGELOG (0.3.0)
actualizados. Commit propuesto, sin hacerlo.

## 2026-11-08 · Fase 3 · Cierre (commit)

```text
sí al commit
```

Resultado: commit de la fase 3 en `main` con el mensaje propuesto, sin push.

## 2026-11-08 · Fase 4 · Corridas con el modelo real

```text
Fase 4 · Corridas con el modelo real (gasta cuota de la suscripción). Corre `date` al empezar y al terminar.

1. Sonda: avísame, espera mi confirmación y ejecuta `fabrica sonda` (las dos llamadas baratas con haiku). Repórtame: herramientas y MCP vacíos, tokens de entrada (que confirmen que no se carga CLAUDE.md), si el esquema de Especificacion pasó y el costo.
2. Guion para mí: dame los comandos exactos para correr HU-05 con el modelo real desde mi propia terminal, en la carpeta Reto: iniciar (hasta la pausa del plan), estado (para mostrar que el checkpoint sobrevive entre procesos) y aprobar con --operador xochitl. Indica en qué momento tomar cada captura y dónde guardarla (evidencia/capturas/).
3. Cuando te pase el resultado, analiza evidencia/corridas/<hilo>/ y el log de seguridad. Si algo falla, primero reprodúcelo con una prueba sin modelo, luego corrígelo y dame el comando para repetir. Máximo 3 corridas de HU-05; si la tercera falla, detente y repórtame.
4. Si queda tiempo y cuota: HU-98 para mostrar el filtro (una llamada a haiku) y HU-99 con las defensas activas por la CLI real (el guardián la bloquea sin llamar al modelo).

Registra esta instrucción en evidencia/prompts.md. Por cada corrida reporta: hilo, estado final, llamadas por agente, ciclos de corrección, costo total, tiempo y cualquier problema con su corrección. Al final propón el commit de la evidencia, sin hacerlo.
```

## 2026-11-08 · Fase 5 · Documentación y publicación

```text
Fase 5 · Documentación y publicación. Tope: 45 minutos; corre `date` al empezar y al terminar.

1. README.md pensado para alguien que llega nuevo al proyecto (criterio 5 de la rúbrica: «documentación excepcional con ejemplos y claridad para onboarding»): qué hace la fábrica; el diagrama (de docs/grafo.md); los 7 agentes y los nodos de código en una tabla; requisitos (uv, Python 3.12, Claude Code con suscripción, sin API key); instalación; uso de la CLI con un ejemplo real tomado de evidencia/corridas/HU-05-real (pausas, aprobación y resultado); cómo correr las pruebas y ruff; las cinco medidas de seguridad y la demo (HU-98 y HU-99); dónde está la evidencia; estructura de carpetas; limitaciones conocidas y costos observados.
2. Docstrings: comprueba con `uv run ruff check --select D100,D101,D102,D103,D104 fabrica` que no falte ninguno y corrige lo que salga.
3. CHANGELOG: entrada de la fase 5 y versión 1.0.0.
4. evidencia/reflexion.md: un borrador para que yo lo edite, con qué funcionó, qué mejorar y las lecciones aprendidas. Incluye: la pausa humana que atrapó el nombre perdido, el triage del reviewer, la revisión estática que rechazó un intento real del tester, el filtro que detuvo HU-98, que las protecciones de Opus 5.5 pausaron una vez el trabajo de seguridad defensiva y cómo se resolvió (cambio a Opus 4.8 y plantear las tareas desde la defensa), los tiempos de cada fase según date y el costo total.
5. Comprueba con git check-ignore que docs/conocimiento/, datos/, logs/ y salida/ no se publiquen, y que no haya secretos en el repo.
6. Publicación: con gh (ya hice gh auth login), prepara la creación del repositorio público Xochitlsw/reto-m3-fabrica-langgraph y el push de main. Muéstrame el comando y espera mi «sí» antes de ejecutarlo. Después del push, confirma que el README se ve bien en GitHub (incluido el diagrama Mermaid) y dame la URL.

Registra esta instrucción en evidencia/prompts.md y propón el commit de la fase 5 antes del push.
```

## 2026-11-08 · Fase 6 · Ajustes finales

```text
Fase 6 · Ajustes finales (sin llamadas al modelo real). Tope: 45 minutos; corre `date` al empezar y al terminar.

1. README: agrega una sección «Features de LangGraph» con una tabla feature → dónde está en el código (archivo y función) → si viene del curso o de fuera: StateGraph con TypedDict y reductores, aristas condicionales, Command(goto) incluido el abanico paralelo, ciclos con tope, interrupt + Command(resume) en las 3 pausas, SqliteSaver entre procesos, get_state y get_state_history, stream, draw_mermaid y LANGGRAPH_STRICT_MSGPACK.
2. Umbral de cobertura: agrega fail_under = 80 en la configuración de coverage de pyproject.toml y comprueba que `uv run pytest -q --cov=fabrica` lo respeta.
3. CI: agrega .github/workflows/ci.yml con GitHub Actions (ubuntu-latest, Python 3.12 con uv): uv sync, ruff check y pytest con cobertura. Las pruebas que dependen de macOS (sandbox-exec) o del binario claude deben saltarse solas en Linux; si alguna falla en CI por eso, corrígela.
4. Opcional, solo si terminas los puntos 1 a 3 antes de 25 minutos: agrupa guardián y filtro en un subgrafo compilado «seguridad_entrada», agregado como nodo del grafo principal, sin cambiar su comportamiento ni los nombres de la bitácora. Agrega su prueba sin modelo, regenera docs/grafo.md y actualiza el README. Si complica las pruebas existentes, no lo hagas y anótalo.
5. CHANGELOG 1.1.0 y registro de esta instrucción en evidencia/prompts.md.

Propón el commit y espera mi «sí» antes del push. Después del push, revisa con gh run list que la CI pase en verde. Repórtame: pytest con cobertura, ruff, el enlace de la corrida de CI y si hiciste el subgrafo.
```
