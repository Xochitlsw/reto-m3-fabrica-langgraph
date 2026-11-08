"""Punto de entrada: ``python -m fabrica``.

``LANGGRAPH_STRICT_MSGPACK`` se fija antes de importar langgraph, porque langgraph la lee al
importarse: el checkpointer solo deserializa tipos permitidos (el estado solo tiene primitivos).
"""

import os
import sys

os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"

from fabrica.cli import main  # noqa: E402 - después de fijar la variable

if __name__ == "__main__":
    sys.exit(main())
