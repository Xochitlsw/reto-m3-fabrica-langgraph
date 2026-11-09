# Reflexión · Reto M3 · Fábrica de software multiagente

## Qué funcionó

- **El supervisor en código.** Tener las reglas R0–R15 en una función pura (`decidir(estado)`) hizo el flujo predecible y barato. No hubo un supervisor «que razona» dando vueltas. Lo que más me sorprendió fue poder probar cada decisión del flujo sin gastar una sola llamada: una tabla con una fila por regla. Cuando algo fallaba, sabía exactamente qué regla revisar, algo imposible si quien decide es un modelo.
- **El modelo propone y el código decide.** Cada salida del modelo pasó por un contrato Pydantic y un validador antes de usarse. Varias veces el modelo propuso algo que el código corrigió o rechazó, sin problema.
- **La pausa humana sirvió para algo real.** En `HU-05-real`, el primer plan devolvía la lista como `(numero, antigüedad)` **sin el nombre del empleado**. Lo vi en la pausa de aprobación, rechacé el plan con el ajuste, y el planificador lo rehízo. Sin la pausa, el entregable habría salido incompleto. (De paso, esto destapó un hueco: el comentario que había dejado al «continuar» la aclaración no llegaba al planificador; lo corregí en la fase 4 con pruebas sin modelo.)
- **El triage del reviewer.** El reviewer no solo dijo «corregir»: nombró al **responsable** (el
  tester) y el **criterio** (C-13). El supervisor mandó la corrección solo a quien tocaba y, en el siguiente ciclo, el sandbox pasó de 31/32 a 33/33.
- **La revisión estática atajó un intento real.** No fue teoría: el **primer intento del tester** en `HU-05-real` usó `__dict__` y la lista blanca lo rechazó (`atributo interno prohibido: __dict__`); el reintento, ya limpio, pasó. Quedó en el log de seguridad del hilo.
- **Las dos capas del guardián, cada una en su lugar.** `HU-99` (inyección directa) la frenó la
  **capa 1** sin gastar una sola llamada al modelo (0.0000 USD). `HU-98` (una petición sutil de
  exfiltración, sin palabras sospechosas) pasó las reglas y la detuvo el **filtro con haiku**
  (0.0003 USD). Ver las dos capas trabajar por separado fue la mejor demostración de defensa en
  profundidad.

## Qué mejorar

- **El guion de la corrida real.** Supuse que `iniciar` se detendría en la pausa del plan, pero el especificador hizo preguntas y la primera pausa fue la de **aclaración**. Las seis preguntas del especificador me obligaron a decidir reglas de negocio que nadie había escrito: la fecha de corte, las bajas, el formato. Aprendí que una historia de usuario «simple» esconde decisiones de producto. Falta documentar que el número de pausas depende de la historia.
- **Cobertura de la aclaración.** El hueco del comentario de «continuar» existía desde la fase 2 y solo apareció con una persona real usándolo. Faltaba una prueba sin modelo de ese camino; ahora está.
- **Qué haría distinto.** Escribiría las reglas de negocio de la historia antes de empezar, no en medio de la corrida. Y probaría HU-98 desde el principio, porque fue la que mejor mostró que una lista de palabras prohibidas no basta.

## Lecciones aprendidas

- **Trabajar por fases con evidencia** (prompt literal en `evidencia/prompts.md`, pruebas en verde, commit propuesto) mantuvo el reto manejable y auditable.
- **Las pruebas sin modelo son el andamio.** 247 pruebas con un modelo falso permitieron construir y refactorizar sin gastar cuota; el modelo real se usó solo al final, a propósito y con aviso.
- **Reproducir antes de corregir.** El hueco de la aclaración se arregló bien porque primero se
  escribió la prueba que lo mostraba en rojo.
- **Una nota sobre las herramientas de IA que usé para construir esto.** Durante la fase 3 (seguridad y demo del ataque), las protecciones de **Claude Opus 5.5** pausaron una vez el trabajo: el asunto —escribir un guardián contra inyección de prompts y una demo de ataque— se parecía lo suficiente a una petición maliciosa como para detener la respuesta. Se resolvió **cambiando a Claude Opus 4.8** y
  **planteando las tareas desde la defensa** (endurecer el guardián, bloquear la fuga del señuelo,
  dejar rastro en el log), que es lo que de verdad eran. La lección: el trabajo de seguridad
  defensiva se explica mejor por su objetivo (proteger) que por el ataque que simula.

## Tiempos por fase (según `date`)

| Fase | Qué | Inicio → fin | Modelo real |
| --- | --- | --- | --- |
| 1 | Arranque y diseño | (antes de las 14:04; no cronometrada con `date`) | no |
| 2 | Núcleo LangGraph | 14:04 → 14:29 (~25 min; tope 2 h) | no |
| 3 | Seguridad y demo del ataque | 14:38 → 15:40 (~1 h 2 min; tope 1 h) | no |
| 4 | Corridas con el modelo real | 15:56 → 16:56 (~1 h) | **sí** |
| 5 | Documentación y publicación | 17:11 → 17:15 (~4 min; tope 45 min) | no |

## Costo total (modelo real)

| Corrida | Costo |
| --- | --- |
| `sonda` (envoltorio, 2× haiku) | ~0.0018 USD |
| `HU-05-real` → LISTA (12 llamadas) | 1.2629 USD |
| `HU-98-real` → filtro (1× haiku) | 0.0003 USD |
| `HU-99-real` → capa 1 (0 llamadas) | 0.0000 USD |
| **Total** | **~1.265 USD** |

Todo el resto del desarrollo —247 pruebas, la demo con y sin defensas, los refactors— corrió con el
**modelo falso**, sin costo.

---

**Lo que me llevo del Módulo 3.** Me llevo otra forma de pensar la seguridad con IA: no confiar en que el modelo se porte bien, sino poner capas que funcionen aunque no lo haga. Ver a HU-99 bloqueada sin gastar una llamada y a HU-98 detenida por el filtro me convenció más que cualquier explicación.
