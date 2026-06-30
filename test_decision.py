from projektstyring.backend.decision_engine import simulate_project_start_change
import json

result = simulate_project_start_change(
    "V165460",
    "2026-07-06",
)

print(json.dumps(result, indent=2, ensure_ascii=False))
