"""Grafana utility class for integration tests."""
from typing import Optional

import requests


class Grafana:
    """A class which abstracts access to a running instance of Grafana."""

    def __init__(
        self,
        ops_test,
        host: Optional[str] = "localhost",
        username: Optional[str] = "admin",
        password: Optional[str] = "",
    ):
        """Make a new instance of the Grafana API management utility.

        Args:
            ops_test (str): The name of the operation to be performed.
            host (str, optional): The hostname or IP address of the Grafana
            application server.Defaults to "localhost".
            username (str, optional): The username for authenticating with the
            Grafana application. Defaults to "admin".
            password (str, optional): The password for authenticating with the
            Grafana application. Defaults to "".
        """
        self.ops_test = ops_test
        self.base_uri = "http://{}/cos-grafana".format(host)
        self.username = username
        self.password = password

    async def is_ready(self) -> bool:
        """Send a request to check readiness.

        Returns:
          True if Grafana is ready (returned database information OK); False otherwise.
        """
        res = await self.health()
        return res.get("database", "") == "ok" or False

    async def health(self) -> dict:
        """Get the health status of the Grafana application.

        Returns:
            dict: A dictionary containing the health status of the Grafana application.

        Raises:
            AssertionError: If the HTTP response status code is not 200.

        """
        api_path = "api/health"
        uri = "{}/{}".format(self.base_uri, api_path)

        response = requests.get(uri, auth=(self.username, self.password))

        assert (
            response.status_code == 200
        ), f"Failed to get health endpoint: {response.text}"
        return response.json()

    async def dashboards_all(self) -> list:
        """Get all dashboards that are not starred.

        Returns:
            list: A list of dashboards.

        Raises:
            AssertionError: If the HTTP response status code is not 200.

        """
        api_path = "api/search"
        uri = "{}/{}?starred=false".format(self.base_uri, api_path)

        response = requests.get(uri, auth=(self.username, self.password))

        assert (
            response.status_code == 200
        ), f"Failed to get dashboards endpoint: {response.text}"
        return response.json()
