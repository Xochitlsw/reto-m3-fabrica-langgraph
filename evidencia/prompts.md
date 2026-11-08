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
