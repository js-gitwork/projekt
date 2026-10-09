import unittest

from projektstyring.vpmanhole.service import (
    normalize_installation_no,
)


class TestVPManholeManholeFilter(unittest.TestCase):

    def test_c5_installation_numbers(self):
        cases = {
            "1,0": "1",
            "2,0": "2",
            "3.0": "3",
            "1": "1",
            2: "2",
            "": "",
        }

        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(
                    normalize_installation_no(value),
                    expected,
                )

    def test_different_installations_remain_distinct(self):
        self.assertNotEqual(
            normalize_installation_no("1,0"),
            normalize_installation_no("2,0"),
        )


if __name__ == "__main__":
    unittest.main()