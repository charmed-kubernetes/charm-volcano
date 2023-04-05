import unittest.mock as mock

from tls_client import TLSRelation, TLSSelfSigned


def test_self_signed_available(harness):
    self_signed = TLSSelfSigned(harness.charm)
    assert "gen-admission-certs.sh" in self_signed._binary
    assert "--service" in self_signed._args
    assert "--namespace" in self_signed._args
    assert self_signed.available is True


def test_self_signed_prepare(harness):
    mock_container = mock.MagicMock()
    mock_container.exec().wait_output.return_value = "stdout", "stderr"
    with mock.patch.object(TLSSelfSigned, "_content") as mock_content:
        self_signed = TLSSelfSigned(harness.charm)
        self_signed.prepare(mock_container)
    mock_container.push.assert_called_once_with(
        self_signed._binary,
        mock_content,
        permissions=0o755,
        user_id=0,
        group_id=0,
    )


def test_relation_available(harness):
    mock_cert_relation = mock.MagicMock()
    charm = harness.charm
    relation = TLSRelation(charm, mock_cert_relation)

    mock_cert_relation.server_certs_map = {}
    assert relation.available is False, "common_name key should not exist in the server_certs_map"

    mock_cert_relation.server_certs_map = {f"{charm.app.name}.{charm.model.name}"}
    assert relation.available is True, "common_name key should exist in the server_certs_map"


def test_relation_request(harness):
    mock_cert_relation = mock.MagicMock()
    charm = harness.charm
    relation = TLSRelation(charm, mock_cert_relation)

    relation.request()
    mock_cert_relation.request_server_cert.assert_called_once_with(
        relation._common_name, relation._sans
    )


def test_relation_prepare(harness):
    mock_container = mock.MagicMock()
    mock_cert_relation = mock.MagicMock()
    charm = harness.charm
    relation = TLSRelation(charm, mock_cert_relation)

    relation.prepare(mock_container)
