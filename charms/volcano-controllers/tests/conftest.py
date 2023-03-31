from unittest.mock import MagicMock, patch

import lightkube
import pytest
from ops.testing import Harness

from charm import CharmVolcano


@pytest.fixture(autouse=True)
def lightkube_client():
    # Prevent any unit test from actually invoking any lightkube api
    client = MagicMock()
    with patch.object(lightkube.Client, "__new__", return_value=client):
        yield client


@pytest.fixture(scope="function")
def harness(request):
    """Test setup."""
    harness = Harness(CharmVolcano)
    harness.set_leader(is_leader=True)
    harness.set_model_name(request.node.originalname)
    harness.begin()
    yield harness
    harness.cleanup()
