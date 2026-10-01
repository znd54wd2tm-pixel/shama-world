from pathlib import Path
import ast
import yaml
ROOT=Path(__file__).resolve().parents[1]
required=["render.yaml","requirements.txt","routes.py","bot.py","config.py","database.py","seed_data.py","web/index.html","services/game.py"]
missing=[p for p in required if not (ROOT/p).is_file()]
if missing: raise SystemExit(f"Missing required files: {missing}")
for path in ROOT.rglob("*.py"):
    if ".venv" not in path.parts: ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
render=yaml.safe_load((ROOT/"render.yaml").read_text(encoding="utf-8")); service=render["services"][0]
assert service["type"]=="web" and service["runtime"]=="python" and service["numInstances"]==1
assert service["healthCheckPath"]=="/health" and service["disk"]["mountPath"]=="/var/data"
print("SHAMA WORLD deploy smoke check: OK")
