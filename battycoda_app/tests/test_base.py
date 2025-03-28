"""
Base test case for all Battycoda tests
"""

from django.test import TestCase

from battycoda_app.tests.test_settings import all_patches


class BattycodaTestCase(TestCase):
    """Base test case that applies all necessary patches for testing"""

    @classmethod
    def setUpClass(cls):
        """Start all patches before any tests run"""
        super().setUpClass()

        # Start all patches
        for patch in all_patches:
            patch.start()

    @classmethod
    def tearDownClass(cls):
        """Stop all patches after all tests are done"""
        # Stop all patches
        for patch in all_patches:
            patch.stop()

        super().tearDownClass()
