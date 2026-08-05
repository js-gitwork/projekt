from projektstyring.backend.decision_service import (
    approve_simulation,
)


def approve_decision(
    simulation,
    approved_by,
):
    try:
        return approve_simulation(
            simulation=simulation,
            approved_by=approved_by,
        )

    except ValueError as error:
        return {
            "ok": False,
            "answer": str(error),
        }

    except Exception as error:
        return {
            "ok": False,
            "answer": (
                "Beslutningen kunne ikke gemmes. "
                "Alle databaseændringer er rullet tilbage.\n\n"
                f"Teknisk fejl: {error}"
            ),
        }