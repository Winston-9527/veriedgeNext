import unittest

from prototype.examples.run_end_to_end_demo import run_demo


class EndToEndDemoTest(unittest.TestCase):
    def test_demo_records_disputed_settlement(self):
        result = run_demo()
        self.assertTrue(result["placement_commitment"]["admitted"])
        self.assertEqual(result["ppd_delivery"]["access_package_count"], 3)
        self.assertEqual(result["tstc_challenge"]["first_mismatch_checkpoint"], "C2")
        self.assertEqual(result["settlement"]["status"], "disputed")


if __name__ == "__main__":
    unittest.main()

