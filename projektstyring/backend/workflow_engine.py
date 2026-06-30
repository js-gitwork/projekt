from dataclasses import dataclass


@dataclass
class WorkflowField:
    name: str
    required: bool = True
    prompt: str = ""
    reason: str = ""


PROJECT_CREATION_WORKFLOW = [
    WorkflowField(
        "project_id",
        prompt="Hvad er projektets V-nummer?",
    ),
    WorkflowField(
        "name",
        prompt="Hvad skal projektet hedde?",
    ),
    WorkflowField(
        "customer",
        prompt="Hvem er kunden?",
    ),
    WorkflowField(
        "city",
        prompt="Hvilken by eller hvilket område ligger projektet i?",
    ),
    WorkflowField(
        "start_date",
        prompt="Hvornår starter projektet?",
    ),
    WorkflowField(
        "installation_count",
        prompt="Hvor mange installationer er der?",
    ),
]