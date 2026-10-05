from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import unittest

from projektstyring.backend.importers.work_importer import WorkImporter


class WorkImporterStateTest(unittest.TestCase):
    def test_import_metadata_change_is_not_new_work_state(self):
        existing = {
            "status": "completed",
            "quantity": Decimal("1"),
            "unit": "stk",
            "performed_date": date(2026, 8, 27),
            "performed_by": "JAN",
            "team_id": None,
            "notes": "",
            "metadata": {
                "source": "c5_csv",
            },
        }

        source = SimpleNamespace(
            status="completed",
            quantity=Decimal("1"),
            unit="stk",
            performed_date=date(2026, 8, 27),
            performed_by="JAN",
            team_id=None,
            notes="",
            metadata={
                "source": "c5_csv",
                "renovation_flag": "Ja",
                "ds437_flag": "",
                "renovation_type": "total",
                "installation_no": "2",
            },
        )

        self.assertTrue(
            WorkImporter._same_work_state(
                existing,
                source,
            )
        )


if __name__ == "__main__":
    unittest.main()
