from __future__ import annotations

import unittest
from decimal import Decimal

from projektstyring.backend.c5_importer import (
    parse_c5_survey_import,
)


PROJECT_ID = "VTESTSURVEY"

SURVEY_TEXT = """Projekt;Inst.nr;Inst.adresse;Brønd 1;Brønd 2;Brønd 1 ej åbnes;Brønd 2 ej åbnes;Eks. profil;Eks. dim.;Eks. mat.;Eks. længde;Ny dim.;Ny længde;Trafik;Brønd 1 dia.;Brønd 2 dia.;Brønd 1 dybde;Brønd 2 dybde;Ny profil;Ny dim. A;Ny dim. B;Ny mat.;Ny profil;Ny dim. A;Ny dim. B;Ny mat.;Opmåling udført;Bemærkning
VTESTSURVEY;1;Testvej 1;B100;B200;;x;Rund;250;Beton;12.5;300;13.2;Vej;1.0;1.2;2.1;2.4;Rund;310;320;PVC;Oval;0;;PE;Tester;Kontrol af endemål
VTESTSURVEY;2;Testvej 2;B300;B400;;;;;;;400;;;;;;;Rund;;;PVC;Rund;410;420;PE;Måler;Ingen længde
VTESTSURVEY;8;Testvej 8;B800;;;;;;;;;;;;;;;;;;;;;;;Tester;Kun én brønd
"""


class TestC5SurveyImport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.import_data = parse_c5_survey_import(
            SURVEY_TEXT,
            PROJECT_ID,
        )

        cls.installations = {
            str(installation.installation_no): installation
            for installation in cls.import_data.installations
        }

    def test_normal_stretch_has_correct_manholes(self):
        installation = self.installations["1"]

        self.assertEqual(
            len(installation.stretches),
            1,
        )

        stretch = installation.stretches[0]

        self.assertEqual(
            stretch.bottom_manhole_no,
            "B100",
        )
        self.assertEqual(
            stretch.top_manhole_no,
            "B200",
        )

    def test_positive_and_zero_dimensions_are_preserved(self):
        stretch = self.installations["1"].stretches[0]
        survey = stretch.survey

        self.assertIsNotNone(survey)

        self.assertEqual(
            survey.bottom_dimension_a_mm,
            Decimal("310"),
        )
        self.assertEqual(
            survey.bottom_dimension_b_mm,
            Decimal("320"),
        )
        self.assertEqual(
            survey.top_dimension_a_mm,
            Decimal("0"),
        )
        self.assertIsNone(
            survey.top_dimension_b_mm,
        )

    def test_duplicate_endpoint_headers_map_to_correct_ends(self):
        survey = self.installations["1"].stretches[0].survey

        self.assertIsNotNone(survey)

        self.assertEqual(
            survey.bottom_profile,
            "Rund",
        )
        self.assertEqual(
            survey.bottom_material,
            "PVC",
        )
        self.assertEqual(
            survey.top_profile,
            "Oval",
        )
        self.assertEqual(
            survey.top_material,
            "PE",
        )

    def test_measured_by_and_notes_are_preserved(self):
        stretch = self.installations["1"].stretches[0]
        survey = stretch.survey

        self.assertIsNotNone(survey)

        self.assertEqual(
            survey.measured_by,
            "Tester",
        )
        self.assertEqual(
            survey.notes,
            "Kontrol af endemål",
        )
        self.assertEqual(
            stretch.notes,
            "Kontrol af endemål",
        )

    def test_single_manhole_installation_has_no_stretch(self):
        installation = self.installations["8"]

        self.assertEqual(
            installation.stretches,
            [],
        )

        manhole_numbers = {
            manhole.manhole_no
            for manhole in self.import_data.manholes
        }

        self.assertIn(
            "B800",
            manhole_numbers,
        )

    def test_missing_length_becomes_zero_on_stretch(self):
        stretch = self.installations["2"].stretches[0]

        self.assertEqual(
            stretch.length_m,
            Decimal("0"),
        )

        self.assertIsNotNone(
            stretch.survey,
        )
        self.assertIsNone(
            stretch.survey.existing_length_m,
        )
        self.assertIsNone(
            stretch.survey.planned_length_m,
        )


if __name__ == "__main__":
    unittest.main()
