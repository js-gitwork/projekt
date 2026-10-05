
from __future__ import annotations

import unittest
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

from projektstyring.backend.importers.import_result import (
    ImportExecutionResult,
)
from projektstyring.backend.importers.manhole_importer import (
    ManholeImporter,
)
from projektstyring.backend.importers.technical_asset_mapper import (
    ManholeKey,
    MappedManhole,
    TechnicalAssetImportPlan,
)


PROJECT_ID = "TEST_DEPTH_IMPORT"


class MemoryManholeRepository:
    """Test-repository uden databaseforbindelse."""

    def __init__(self):
        self.manholes = {}
        self.next_id = 1

    def get_manhole_by_number(self, project_id, manhole_no):
        key = (project_id, manhole_no)

        if key not in self.manholes:
            raise FileNotFoundError(manhole_no)

        return deepcopy(self.manholes[key])

    def create_manhole(
        self,
        project_id,
        manhole_no,
        *,
        diameter_m=None,
        depth_m=None,
        profile="",
        material="",
        active=True,
        notes="",
        metadata=None,
    ):
        key = (project_id, manhole_no)

        if key in self.manholes:
            raise ValueError("Brønden findes allerede.")

        record = {
            "id": self.next_id,
            "project_id": project_id,
            "manhole_no": manhole_no,
            "diameter_m": (
                float(diameter_m)
                if diameter_m is not None
                else None
            ),
            "depth_m": (
                float(depth_m)
                if depth_m is not None
                else None
            ),
            "profile": profile,
            "material": material,
            "active": active,
            "notes": notes,
            "metadata": deepcopy(metadata or {}),
        }

        self.next_id += 1
        self.manholes[key] = record

        return deepcopy(record)

    def update_manhole(self, manhole_id, updates):
        for record in self.manholes.values():
            if record["id"] != manhole_id:
                continue

            for key, value in updates.items():
                if key in {"depth_m", "diameter_m"}:
                    record[key] = (
                        float(value)
                        if value is not None
                        else None
                    )
                else:
                    record[key] = deepcopy(value)

            return deepcopy(record)

        raise FileNotFoundError(manhole_id)


def make_manhole(number, depth, import_type, observations=None):
    if observations is None:
        observations = (
            [str(depth)]
            if depth is not None
            else []
        )

    source = SimpleNamespace(
        manhole_no=number,
        diameter_m=None,
        depth_m=(
            Decimal(str(depth))
            if depth is not None
            else None
        ),
        profile="",
        material="",
        active=True,
        notes="",
        metadata={
            "source": "c5_csv",
            "import_type": import_type,
            "depth_authoritative": (
                import_type == "project_overview"
            ),
            "depth_source": (
                "c5_project_overview"
                if import_type == "project_overview"
                else "c5_manhole_overview"
            ),
            "depth_observations_m": observations,
        },
    )

    return MappedManhole(
        key=ManholeKey(PROJECT_ID, number),
        source=source,
    )


class TestManholeImporterDepth(unittest.TestCase):

    def setUp(self):
        self.repo = MemoryManholeRepository()
        self.importer = ManholeImporter()

    def run_import(self, import_type, *manholes):
        plan = TechnicalAssetImportPlan(
            project_id=PROJECT_ID,
            source="c5_csv",
            import_type=import_type,
            manholes=list(manholes),
        )

        result = ImportExecutionResult(
            project_id=PROJECT_ID,
            source="c5_csv",
        )

        self.importer.execute(
            repo=self.repo,
            plan=plan,
            result=result,
        )

        return result

    def get_manhole(self, number="B001"):
        return self.repo.get_manhole_by_number(
            PROJECT_ID,
            number,
        )

    def test_secondary_can_create_new_manhole(self):
        result = self.run_import(
            "manhole_overview",
            make_manhole(
                "B001", "2.14", "manhole_overview"
            ),
        )

        self.assertEqual(result.created, 1)
        self.assertEqual(
            self.get_manhole()["depth_m"],
            2.14,
        )

    def test_project_overview_takes_authority(self):
        self.run_import(
            "manhole_overview",
            make_manhole(
                "B001", "2.14", "manhole_overview"
            ),
        )

        self.run_import(
            "project_overview",
            make_manhole(
                "B001", "2.19", "project_overview"
            ),
        )

        record = self.get_manhole()

        self.assertEqual(record["depth_m"], 2.19)
        self.assertEqual(
            record["metadata"]["depth_source"],
            "c5_project_overview",
        )
        self.assertTrue(
            record["metadata"]["depth_authoritative"]
        )

    def test_secondary_cannot_overwrite_authority(self):
        self.test_project_overview_takes_authority()

        result = self.run_import(
            "manhole_overview",
            make_manhole(
                "B001", "2.13", "manhole_overview"
            ),
        )

        record = self.get_manhole()

        self.assertEqual(record["depth_m"], 2.19)
        self.assertEqual(
            record["metadata"]["depth_source"],
            "c5_project_overview",
        )
        self.assertEqual(len(result.conflicts), 1)
        self.assertFalse(
            result.conflicts[0].blocks_import
        )

    def test_empty_import_preserves_depth(self):
        self.run_import(
            "project_overview",
            make_manhole(
                "B001", "2.19", "project_overview"
            ),
        )

        self.run_import(
            "project_overview",
            make_manhole(
                "B001", None, "project_overview"
            ),
        )

        self.assertEqual(
            self.get_manhole()["depth_m"],
            2.19,
        )

    def test_conflicting_observations_preserve_depth(self):
        self.run_import(
            "project_overview",
            make_manhole(
                "B001", "2.19", "project_overview"
            ),
        )

        result = self.run_import(
            "project_overview",
            make_manhole(
                "B001",
                None,
                "project_overview",
                observations=["2.14", "2.19"],
            ),
        )

        self.assertEqual(
            self.get_manhole()["depth_m"],
            2.19,
        )
        self.assertEqual(len(result.conflicts), 1)

    def test_zero_is_not_a_depth(self):
        self.run_import(
            "project_overview",
            make_manhole(
                "B001", "2.19", "project_overview"
            ),
        )

        self.run_import(
            "project_overview",
            make_manhole(
                "B001",
                None,
                "project_overview",
                observations=["0", "-1"],
            ),
        )

        self.assertEqual(
            self.get_manhole()["depth_m"],
            2.19,
        )

    def test_same_manhole_is_not_duplicated(self):
        item = make_manhole(
            "B001", "2.19", "project_overview"
        )

        self.run_import("project_overview", item)
        result = self.run_import(
            "project_overview",
            item,
        )

        self.assertEqual(len(self.repo.manholes), 1)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.unchanged, 1)


if __name__ == "__main__":
    unittest.main()
