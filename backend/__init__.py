# Mark backend as a package for imports
# When other modules accidentally use bare `import models` or `import database`
# we want them to resolve to the package versions.  This is especially useful
# when the working directory is `backend/` and the package is executed as a
# script – otherwise Python would load a fresh top-level module and you get
# duplicate SQLAlchemy metadata objects.

import sys
from importlib import import_module

for alias in ("models", "database", "models_draft_value", "utils", "core", "services", "routers", "schemas"):
    if alias not in sys.modules:
        try:
            sys.modules[alias] = import_module(f"backend.{alias}")
        except ImportError:
            # safe to ignore during early import when backend isn't fully
            # installable; the normal package imports will still work later.
            pass
