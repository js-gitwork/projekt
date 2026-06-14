from projektstyring.backend.models import Installation
from projektstyring.backend.planner import generer_aktiviteter, print_plan


inst = Installation(
    id="INST-001",
    projekt_id="P-100",
    rækkefølge=1
)

inst = generer_aktiviteter(inst)
print_plan(inst)
