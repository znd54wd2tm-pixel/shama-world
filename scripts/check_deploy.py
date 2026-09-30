from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
required = [
    "render.yaml", "requirements.txt", "routes.py", "bot.py", "config.py",
    "database.py", "seed_data.py", "web/index.html",
]
missing = [p for p in required if not (ROOT / p).is_file()]
if missing:
    raise SystemExit(f"Missing required files: {missing}")
for path in ROOT.rglob("*.py"):
    if ".venv" in path.parts:
        continue
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
print("SHAMA WORLD deploy smoke check: OK")
