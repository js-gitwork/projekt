from __future__ import annotations

import unittest
from pathlib import Path

from projektstyring.backend.c5_importer import (
    parse_c5_project_overview_import,
)


PROJECT_ID = "V166220"
FIXTURE_PATH = (
    Path(__file__).parent / "v166220_c5_fixture.txt"
)


class TestC5InstallationStretches(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c5_text = FIXTURE_PATH.read_text(
            encoding="utf-8"
        )

        cls.import_data = parse_c5_project_overview_import(
            cls.c5_text,
            PROJECT_ID,
        )

        cls.installations = {
            str(installation.installation_no): installation
            for installation in cls.import_data.installations
        }

    def test_installation_16_has_four_stretches(self):
        installation = self.installations["16"]

        stretches = [
            (
                stretch.bottom_manhole_no,
                stretch.top_manhole_no,
            )
            for stretch in installation.stretches
        ]

        self.assertEqual(
            stretches,
            [
                ("F56430F", "F56440F"),
                ("F56410F", "F56415F"),
                ("F56415F", "F56420F"),
                ("F56420F", "F56430F"),
            ],
        )

    def test_installation_28_has_two_stretches(self):
        installation = self.installations["28"]

        stretches = [
            (
                stretch.bottom_manhole_no,
                stretch.top_manhole_no,
            )
            for stretch in installation.stretches
        ]

        self.assertEqual(
            stretches,
            [
                ("F56540F", "F56550F"),
                ("F56550F", "F56560F"),
            ],
        )

    def test_installation_16_and_28_do_not_mix(self):
        installation_16 = self.installations["16"]
        installation_28 = self.installations["28"]

        stretches_16 = {
            (
                stretch.bottom_manhole_no,
                stretch.top_manhole_no,
            )
            for stretch in installation_16.stretches
        }

        stretches_28 = {
            (
                stretch.bottom_manhole_no,
                stretch.top_manhole_no,
            )
            for stretch in installation_28.stretches
        }

        self.assertTrue(
            stretches_16.isdisjoint(stretches_28)
        )


if __name__ == "__main__":
    unittest.main()
