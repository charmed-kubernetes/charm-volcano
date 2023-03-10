"""Unit tests."""

import unittest

from ops.model import ActiveStatus
from ops.testing import Harness

from charm import CharmVolcano


class TestCharm(unittest.TestCase):
    """Volcano Controllers Charm Unit Tests."""

    def setUp(self):
        """Test setup."""
        self.harness = Harness(CharmVolcano)
        self.harness.set_leader(is_leader=True)
        self.harness.begin()

    def test_on_start(self):
        assert self.harness.charm.unit.status == ActiveStatus()
