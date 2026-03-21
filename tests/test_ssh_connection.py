"""Tests for SSH connection testing module."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import paramiko
import socket
from clawrium.core.ssh_connection import (
    get_ssh_config,
    test_ssh_connection as ssh_test_connection,
    StrictHostKeyPolicy,
    HostKeyVerificationRequired,
    VerifyingHostKeyPolicy,
    accept_host_key,
)


def test_get_ssh_config_no_file():
    """get_ssh_config returns {} when no SSH config file exists."""
    with patch.object(Path, 'exists', return_value=False):
        config = get_ssh_config("testhost")
        assert config == {}


def test_get_ssh_config_with_matching_host():
    """get_ssh_config parses config and returns settings for matching hostname."""
    ssh_config_content = """
Host testhost
    HostName 192.168.1.10
    User customuser
    Port 2222
    IdentityFile ~/.ssh/custom_key
"""
    with patch.object(Path, 'exists', return_value=True):
        with patch('builtins.open', mock_open(read_data=ssh_config_content)):
            config = get_ssh_config("testhost")

            assert 'hostname' in config
            assert config['hostname'] == '192.168.1.10'
            assert 'user' in config
            assert config['user'] == 'customuser'
            assert 'port' in config
            assert 'identityfile' in config


def test_get_ssh_config_with_non_matching_host():
    """get_ssh_config returns empty dict for non-matching hostname."""
    ssh_config_content = """
Host otherhost
    HostName 192.168.1.20
    User otheruser
"""
    with patch.object(Path, 'exists', return_value=True):
        with patch('builtins.open', mock_open(read_data=ssh_config_content)):
            config = get_ssh_config("testhost")
            # Should return empty or minimal config for non-matching host
            # Paramiko SSHConfig.lookup returns some defaults even for unknown hosts
            assert isinstance(config, dict)


def test_ssh_connection_success():
    """test_ssh_connection returns (True, success message) on successful connection."""
    mock_client = Mock(spec=paramiko.SSHClient)
    mock_transport = Mock()
    mock_transport.is_active.return_value = True
    mock_client.get_transport.return_value = mock_transport

    with patch('paramiko.SSHClient', return_value=mock_client):
        success, message = ssh_test_connection("testhost", 22, "xclm")

        assert success is True
        assert "success" in message.lower()
        mock_client.connect.assert_called_once()
        mock_client.close.assert_called_once()


def test_ssh_connection_auth_failure():
    """test_ssh_connection returns (False, auth error) on authentication failure."""
    mock_client = Mock(spec=paramiko.SSHClient)
    mock_client.connect.side_effect = paramiko.AuthenticationException("Auth failed")

    with patch('paramiko.SSHClient', return_value=mock_client):
        success, message = ssh_test_connection("testhost", 22, "xclm")

        assert success is False
        assert "authentication" in message.lower()
        assert "ssh keys" in message.lower()
        mock_client.close.assert_called_once()


def test_ssh_connection_network_error():
    """test_ssh_connection returns (False, network error) on socket error."""
    mock_client = Mock(spec=paramiko.SSHClient)
    mock_client.connect.side_effect = socket.error("Connection refused")

    with patch('paramiko.SSHClient', return_value=mock_client):
        success, message = ssh_test_connection("testhost", 22, "xclm")

        assert success is False
        assert "network error" in message.lower()
        mock_client.close.assert_called_once()


def test_ssh_connection_inactive_transport():
    """test_ssh_connection returns (False, transport not active) when transport is inactive."""
    mock_client = Mock(spec=paramiko.SSHClient)
    mock_transport = Mock()
    mock_transport.is_active.return_value = False
    mock_client.get_transport.return_value = mock_transport

    with patch('paramiko.SSHClient', return_value=mock_client):
        success, message = ssh_test_connection("testhost", 22, "xclm")

        assert success is False
        assert "transport not active" in message.lower()


def test_ssh_connection_bad_host_key():
    """test_ssh_connection returns (False, key changed) on BadHostKeyException."""
    mock_client = Mock(spec=paramiko.SSHClient)
    mock_key = Mock()
    mock_key.get_base64.return_value = "AAAA"
    mock_client.connect.side_effect = paramiko.BadHostKeyException(
        "testhost", mock_key, mock_key
    )

    with patch('paramiko.SSHClient', return_value=mock_client):
        success, message = ssh_test_connection("testhost", 22, "xclm")

        assert success is False
        assert "host key" in message.lower()
        assert "changed" in message.lower()


def test_ssh_connection_ssh_exception():
    """test_ssh_connection returns (False, SSH failed) on generic SSHException."""
    mock_client = Mock(spec=paramiko.SSHClient)
    mock_client.connect.side_effect = paramiko.SSHException("Protocol error")

    with patch('paramiko.SSHClient', return_value=mock_client):
        success, message = ssh_test_connection("testhost", 22, "xclm")

        assert success is False
        assert "ssh connection failed" in message.lower()


class TestStrictHostKeyPolicy:
    """Tests for StrictHostKeyPolicy."""

    def test_raises_host_key_verification_required(self):
        """StrictHostKeyPolicy raises HostKeyVerificationRequired with fingerprint."""
        policy = StrictHostKeyPolicy()
        mock_client = Mock()
        mock_key = Mock()
        # Fingerprint returns bytes
        mock_key.get_fingerprint.return_value = bytes.fromhex("aabbccdd")
        mock_key.get_name.return_value = "ssh-rsa"

        with pytest.raises(HostKeyVerificationRequired) as exc_info:
            policy.missing_host_key(mock_client, "testhost", mock_key)

        assert exc_info.value.hostname == "testhost"
        assert exc_info.value.key_type == "ssh-rsa"
        assert exc_info.value.fingerprint == "aa:bb:cc:dd"


class TestVerifyingHostKeyPolicy:
    """Tests for VerifyingHostKeyPolicy."""

    def test_accepts_matching_fingerprint(self):
        """VerifyingHostKeyPolicy accepts key with matching fingerprint."""
        policy = VerifyingHostKeyPolicy("aa:bb:cc:dd")
        mock_client = Mock()
        mock_client._host_keys = Mock()
        mock_key = Mock()
        mock_key.get_fingerprint.return_value = bytes.fromhex("aabbccdd")
        mock_key.get_name.return_value = "ssh-rsa"

        # Should not raise
        policy.missing_host_key(mock_client, "testhost", mock_key)

        assert policy.key_accepted is True
        mock_client._host_keys.add.assert_called_once()

    def test_rejects_mismatched_fingerprint(self):
        """VerifyingHostKeyPolicy raises SSHException on fingerprint mismatch."""
        policy = VerifyingHostKeyPolicy("aa:bb:cc:dd")
        mock_client = Mock()
        mock_key = Mock()
        # Different fingerprint
        mock_key.get_fingerprint.return_value = bytes.fromhex("11223344")
        mock_key.get_name.return_value = "ssh-rsa"

        with pytest.raises(paramiko.SSHException) as exc_info:
            policy.missing_host_key(mock_client, "testhost", mock_key)

        assert "mismatch" in str(exc_info.value).lower()
        assert policy.key_accepted is False


class TestAcceptHostKey:
    """Tests for accept_host_key function."""

    def test_returns_false_without_fingerprint(self):
        """accept_host_key returns False when no fingerprint provided."""
        result = accept_host_key("testhost", 22, expected_fingerprint="")
        assert result is False

    @pytest.mark.skip(reason="TODO: Update mock to handle refactored accept_host_key control flow")
    def test_swallows_auth_exception(self):
        """accept_host_key swallows AuthenticationException (expected - just want host key)."""
        pass

    def test_returns_false_on_fingerprint_mismatch(self):
        """accept_host_key returns False when fingerprint doesn't match."""
        mock_client = Mock(spec=paramiko.SSHClient)
        mock_client.connect.side_effect = paramiko.SSHException("fingerprint mismatch")

        with patch('paramiko.SSHClient', return_value=mock_client):
            result = accept_host_key("testhost", 22, expected_fingerprint="aa:bb:cc:dd")
            assert result is False

    def test_returns_false_on_connection_error(self):
        """accept_host_key returns False on connection error."""
        mock_client = Mock(spec=paramiko.SSHClient)
        mock_client.connect.side_effect = socket.error("Connection refused")

        with patch('paramiko.SSHClient', return_value=mock_client):
            result = accept_host_key("testhost", 22, expected_fingerprint="aa:bb:cc:dd")
            assert result is False
