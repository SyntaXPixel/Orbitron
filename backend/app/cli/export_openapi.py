import json
from pathlib import Path
from app.main import app
from app.config import BACKEND_DIR

def export_openapi():
    out_dir = BACKEND_DIR / ".runtime"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "openapi.json"
    schema = app.openapi()
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"OpenAPI schema successfully exported to {out_file}")

if __name__ == "__main__":
    export_openapi()
