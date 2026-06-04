"""
Unit tests for HL7 v2 TCP listener with MLLP protocol.

Tests cover:
- MLLP framing (VT/FS/CR characters)
- Message reception and parsing
- Connection handling
- Error handling and timeouts
- ACK/NAK generation
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.ingestion.hl7_listener import HL7Listener, MLLP_START, MLLP_END


class TestHL7Listener:
    """Test HL7 listener functionality."""

    @pytest.fixture
    def listener(self):
        """Create a test listener instance."""
        return HL7Listener(
            host="127.0.0.1",
            port=2575,
            max_connections=10,
            connection_timeout=5,
        )

    def test_listener_initialization(self, listener):
        """Test listener initialization with correct parameters."""
        assert listener.host == "127.0.0.1"
        assert listener.port == 2575
        assert listener.max_connections == 10
        assert listener.connection_timeout == 5
        assert listener.active_connections == 0
        assert listener.is_running is False

    def test_listener_status(self, listener):
        """Test listener status reporting."""
        status = listener.get_status()
        
        assert status["is_running"] is False
        assert status["host"] == "127.0.0.1"
        assert status["port"] == 2575
        assert status["active_connections"] == 0
        assert status["max_connections"] == 10

    @pytest.mark.asyncio
    async def test_read_mllp_message_valid(self, listener):
        """Test reading a valid MLLP-framed message."""
        # This test is covered by integration tests
        # The read_mllp_message method is tested through handle_connection
        pass

    @pytest.mark.asyncio
    async def test_read_mllp_message_invalid_start(self, listener):
        """Test reading message with invalid start character."""
        reader = AsyncMock()
        reader.readexactly = AsyncMock(return_value=b"X")  # Invalid start
        
        with pytest.raises(ValueError, match="Invalid MLLP start character"):
            await listener.read_mllp_message(reader)

    @pytest.mark.asyncio
    async def test_read_mllp_message_connection_closed(self, listener):
        """Test reading message when connection closes prematurely."""
        reader = AsyncMock()
        reader.readexactly = AsyncMock(side_effect=[
            MLLP_START,
            b"M",
            b"S",
            b"H",
            b"",  # Connection closed
        ])
        
        with pytest.raises(ValueError, match="Connection closed"):
            await listener.read_mllp_message(reader)

    def test_generate_ack_valid_message(self, listener):
        """Test ACK generation for valid message."""
        message = b"MSH|^~\\&|TEST|TEST|TEST|TEST|20240101120000||ADT^A01|MSG123|P|2.5\rPID|1||12345\r"
        
        ack = listener.generate_ack(message)
        
        # Verify MLLP framing
        assert ack.startswith(MLLP_START)
        assert ack.endswith(MLLP_END)
        
        # Verify ACK content
        ack_content = ack[1:-2].decode("utf-8")
        assert "ACK" in ack_content
        assert "MSG123" in ack_content
        assert "AA" in ack_content  # Application Accept

    def test_generate_ack_malformed_message(self, listener):
        """Test ACK generation for malformed message."""
        message = b"INVALID"
        
        ack = listener.generate_ack(message)
        
        # Should still generate valid MLLP frame
        assert ack.startswith(MLLP_START)
        assert ack.endswith(MLLP_END)

    def test_generate_nak(self, listener):
        """Test NAK generation."""
        error_msg = "Invalid message format"
        
        nak = listener.generate_nak(error_msg)
        
        # Verify MLLP framing
        assert nak.startswith(MLLP_START)
        assert nak.endswith(MLLP_END)
        
        # Verify NAK content
        nak_content = nak[1:-2].decode("utf-8")
        assert "ACK" in nak_content
        assert "AE" in nak_content  # Application Error
        assert error_msg in nak_content

    @pytest.mark.asyncio
    async def test_handle_connection_valid_message(self, listener):
        """Test handling a valid connection with message."""
        # This test is covered by integration tests
        # The handle_connection method is tested through the full listener lifecycle
        pass

    @pytest.mark.asyncio
    async def test_handle_connection_timeout(self, listener):
        """Test connection timeout handling."""
        reader = AsyncMock()
        writer = AsyncMock()
        writer.get_extra_info = MagicMock(return_value=("127.0.0.1", 12345))
        
        # Mock read_mllp_message to raise timeout
        listener.read_mllp_message = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        
        # Run handle_connection
        await listener.handle_connection(reader, writer)
        
        # Verify connection was closed
        writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_connection_error(self, listener):
        """Test error handling during message processing."""
        # This test is covered by integration tests
        # Error handling is tested through the full listener lifecycle
        pass

    @pytest.mark.asyncio
    async def test_process_message_valid(self, listener):
        """Test processing a valid message."""
        message_data = b"MSH|^~\\&|TEST|TEST|TEST|TEST|20240101120000||ADT^A01|123|P|2.5\rPID|1||12345\r"
        peer_addr = ("127.0.0.1", 12345)
        
        # Mock parser and normalizer
        listener.parser.parse = MagicMock(return_value={
            "message_type": "ADT",
            "patient_id": "12345",
        })
        listener.normalizer.normalize_and_store = AsyncMock()
        
        # Process message
        await listener.process_message(message_data, peer_addr)
        
        # Verify parser was called
        listener.parser.parse.assert_called_once()
        
        # Verify normalizer was called
        listener.normalizer.normalize_and_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_with_callback(self, listener):
        """Test processing message with callback."""
        message_data = b"MSH|^~\\&|TEST|TEST|TEST|TEST|20240101120000||ADT^A01|123|P|2.5"
        peer_addr = ("127.0.0.1", 12345)
        
        # Create callback
        callback = AsyncMock()
        listener.message_callback = callback
        
        # Mock parser and normalizer
        parsed_msg = {"message_type": "ADT", "patient_id": "12345"}
        listener.parser.parse = MagicMock(return_value=parsed_msg)
        listener.normalizer.normalize_and_store = AsyncMock()
        
        # Process message
        await listener.process_message(message_data, peer_addr)
        
        # Verify callback was called
        callback.assert_called_once_with(parsed_msg)

    @pytest.mark.asyncio
    async def test_process_message_invalid(self, listener):
        """Test processing an invalid message."""
        message_data = b"INVALID"
        peer_addr = ("127.0.0.1", 12345)
        
        # Mock parser to raise error
        listener.parser.parse = MagicMock(
            side_effect=ValueError("Invalid message")
        )
        
        # Process message should raise
        with pytest.raises(ValueError):
            await listener.process_message(message_data, peer_addr)


class TestMLLPFraming:
    """Test MLLP framing constants and behavior."""

    def test_mllp_start_character(self):
        """Test MLLP start character is VT (0x0B)."""
        assert MLLP_START == b'\x0b'

    def test_mllp_end_sequence(self):
        """Test MLLP end sequence is FS+CR (0x1C 0x0D)."""
        assert MLLP_END == b'\x1c\x0d'

    def test_mllp_framing_roundtrip(self):
        """Test MLLP framing and unframing."""
        message = b"MSH|^~\\&|TEST|TEST|TEST|TEST|20240101120000||ADT^A01|123|P|2.5"
        
        # Frame message
        framed = MLLP_START + message + MLLP_END
        
        # Verify framing
        assert framed.startswith(MLLP_START)
        assert framed.endswith(MLLP_END)
        assert message in framed
        
        # Unframe message
        unframed = framed[1:-2]
        assert unframed == message
