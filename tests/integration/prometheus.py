"""Prometheus utility class for integration tests."""
from typing import Optional

import requests


class Prometheus:
    """A class which abstracts access to a running instance of Prometheus."""

    def __init__(
        self,
        host: Optional[str] = "localhost",
    ):
        """Make a new instance of the Prometheus API management utility.

        Args:
            host: Optional host address of Prometheus application, defaults
            to `localhost`
        """
        self.base_uri = f"http://{host}/cos-prometheus-0"

    async def is_ready(self) -> bool:
        """Check if the Prometheus application is ready by sending a health request.

        Returns:
            bool: True if Prometheus is ready, False otherwise.

        """
        res = await self.health()
        return "Prometheus Server is Ready." in res

    async def health(self) -> str:
        """Check the Prometheus readiness status using the MGMT API.

        Queries the API to see whether Prometheus is ready to serve traffic
        (i.e., respond to queries).

        Returns:
            str: An empty string if Prometheus is not up, otherwise a string
            containing "Prometheus is Ready".

        Raises:
            AssertionError: If the HTTP response status code is not 200.

        """
        api_path = "-/ready"
        uri = f"{self.base_uri}/{api_path}"

        response = requests.get(uri)

        assert (
            response.status_code == 200
        ), f"Failed to get health endpoint: {response.text}"
        return response.text

    async def get_metrics(self) -> list:
        """Get all metrics reported to Prometheus.

        Returns:
            list: A list of the found metrics, if any.

        Raises:
            AssertionError: If the HTTP response status code is not 200.

        """
        api_path = "api/v1/label/__name__/values"
        uri = f"{self.base_uri}/{api_path}"
        params = {"match[]": ['{__name__=~".+", job!="prometheus"}']}

        response = requests.get(uri, params=params)

        assert response.status_code == 200, f"Failed to get metrics: {response.text}"
        return response.json()["data"]
