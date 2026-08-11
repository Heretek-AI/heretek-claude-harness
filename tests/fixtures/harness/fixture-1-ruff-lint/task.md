# Fix ruff violation

The file `app.py` has a ruff violation: `import os; os.path.join(...)` should
use `pathlib.Path`. Fix it.

Expected: 1-line diff replacing the import + the call site.
