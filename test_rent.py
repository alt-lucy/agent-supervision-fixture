import unittest

from rent import format_gbp, weekly_to_monthly


class WeeklyToMonthlyTest(unittest.TestCase):
    def test_converts_using_52_weeks_over_12_months(self):
        self.assertEqual(weekly_to_monthly(120.00), 520.00)

    def test_rounds_to_pence(self):
        self.assertEqual(weekly_to_monthly(99.99), 433.29)


class FormatGbpTest(unittest.TestCase):
    def test_formats_with_pound_sign_and_thousands_separator(self):
        self.assertEqual(format_gbp(1234.5), "£1,234.50")


if __name__ == "__main__":
    unittest.main()
