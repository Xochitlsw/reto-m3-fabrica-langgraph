"""Los 7 agentes con modelo. Cada uno tiene su prompt en ``fabrica/prompts/<agente>.md``."""

from fabrica.agentes.documentador import Documentador
from fabrica.agentes.especificador import Especificador
from fabrica.agentes.filtro import Filtro
from fabrica.agentes.implementador import Implementador
from fabrica.agentes.planificador import Planificador
from fabrica.agentes.reviewer import Reviewer
from fabrica.agentes.tester import Tester

AGENTES = {a.nombre: a for a in (Filtro(), Especificador(), Planificador(), Implementador(),
                                 Tester(), Reviewer(), Documentador())}

__all__ = ["AGENTES"]
