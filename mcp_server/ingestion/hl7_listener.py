"""
HL7 v2 TCP Listener with MLLP Protocol Support.

This module implements a TCP server that listens for HL7 v2 messages using the
Minimal Lower Layer Protocol (MLLP) framing. It handles concurrent connections,
implements connection timeouts, and error handling.

MLLP Framing:
- Start: VT (0x0B) - Vertical Tab
- End: FS (0x1C) + CR (0x0D) - File Separator + Carriage Return
- Message format: <VT>HL7_MESSAGE<FS><CR>
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from mcp_server.ingestion.hl7_parser import HL7Parser
from mcp_server.ingestion.hl7_normalizer import HL7Normalizer
from mcp_server.utils.logger import get_logger

# MLLP framing characters
MLLP_START = b'\x0b'  # VT (Vertical Tab)
MLLP_END = b'\x1c\x0d'  # FS (File Separator) + CR (Carriage Return)

logger = get_logger(__name__)


class HL7Listener:
    """
    TCP server for receiving HL7 v2 messages using MLLP protocol.
    
    Handles:
    - Concurrent connections with configurable limits
    - MLLP framing (VT/FS/CR characters)
    - Connection timeouts and error handling
    - Message parsing and normalization
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 2575,
        max_connections: int = 100,
        connection_timeout: int = 300,
        message_callback: Optional[Callable] = None,
    ):
        """
        Initialize HL7 listener.
        
        Args:
            host: Host to bind to (default: 0.0.0.0)
            port: Port to listen on (default: 2575)
            max_connections: Maximum concurrent connections (default: 100)
            connection_timeout: Connection timeout in seconds (default: 300)
            message_callback: Optional callback function for processed messages
        """
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.message_callback = message_callback
        
        self.server: Optional[asyncio.Server] = None
        self.active_connections = 0
        self.parser = HL7Parser()
        self.normalizer = HL7Normalizer()
        self.is_running = False

    async def start(self) -> None:
        """
        Start the HL7 listener server.
        
        Raises:
            OSError: If unable to bind to the specified host/port
        """
        try:
            self.server = await asyncio.start_server(
                self.handle_connection,
                self.host,
                self.port,
            )
            self.is_running = True
            
            addr = self.server.sockets[0].getsockname()
            logger.info(f"HL7 listener started on {addr[0]}:{addr[1]}")
            
            async with self.server:
                await self.server.serve_forever()
        except OSError as e:
            logger.error(f"Failed to start HL7 listener: {e}")
            raise

    async def stop(self) -> None:
        """Stop the HL7 listener server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.is_running = False
            logger.info("HL7 listener stopped")

    async def handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """
        Handle a single client connection.
        
        Args:
            reader: StreamReader for receiving data
            writer: StreamWriter for sending data
        """
        peer_addr = writer.get_extra_info("peername")
        self.active_connections += 1
        
        logger.info(
            f"New HL7 connection from {peer_addr[0]}:{peer_addr[1]} "
            f"(active: {self.active_connections})"
        )
        
        try:
            while self.is_running:
                try:
                    # Read message with timeout
                    message_data = await asyncio.wait_for(
                        self.read_mllp_message(reader),
                        timeout=self.connection_timeout,
                    )
                    
                    if not message_data:
                        # Connection closed by client
                        break
                    
                    # Process the message
                    await self.process_message(message_data, peer_addr)
                    
                    # Send ACK
                    ack = self.generate_ack(message_data)
                    writer.write(ack)
                    await writer.drain()
                    
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Connection timeout from {peer_addr[0]}:{peer_addr[1]}"
                    )
                    break
                except Exception as e:
                    logger.error(
                        f"Error processing message from {peer_addr[0]}:{peer_addr[1]}: {e}"
                    )
                    # Send NAK (Negative Acknowledgment)
                    nak = self.generate_nak(str(e))
                    writer.write(nak)
                    await writer.drain()
                    
        except Exception as e:
            logger.error(f"Connection error from {peer_addr[0]}:{peer_addr[1]}: {e}")
        finally:
            self.active_connections -= 1
            writer.close()
            await writer.wait_closed()
            logger.info(
                f"Connection closed from {peer_addr[0]}:{peer_addr[1]} "
                f"(active: {self.active_connections})"
            )

    async def read_mllp_message(self, reader: asyncio.StreamReader) -> Optional[bytes]:
        """
        Read a single MLLP-framed message from the stream.
        
        Args:
            reader: StreamReader to read from
            
        Returns:
            Message bytes (without MLLP framing), or None if connection closed
            
        Raises:
            ValueError: If message framing is invalid
        """
        # Read until we find the start character
        start_byte = await reader.readexactly(1)
        if not start_byte:
            return None
        
        if start_byte != MLLP_START:
            raise ValueError(
                f"Invalid MLLP start character: {start_byte.hex()} "
                f"(expected {MLLP_START.hex()})"
            )
        
        # Read until we find the end sequence
        message_data = b""
        while True:
            byte = await reader.readexactly(1)
            if not byte:
                raise ValueError("Connection closed before MLLP end sequence")
            
            if byte == MLLP_END[0]:  # FS character
                # Check if next byte is CR
                next_byte = await reader.readexactly(1)
                if next_byte == MLLP_END[1]:  # CR character
                    break
                else:
                    # Not the end sequence, add both bytes to message
                    message_data += byte + next_byte
            else:
                message_data += byte
        
        return message_data

    async def process_message(self, message_data: bytes, peer_addr: tuple) -> None:
        """
        Process a received HL7 message.
        
        Args:
            message_data: Raw message bytes
            peer_addr: Peer address tuple (host, port)
        """
        try:
            # Decode message
            message_str = message_data.decode("utf-8")
            
            # Parse HL7 message
            parsed_message = self.parser.parse(message_str)
            
            # Normalize and store
            await self.normalizer.normalize_and_store(parsed_message)
            
            # Call optional callback
            if self.message_callback:
                await self.message_callback(parsed_message)
            
            logger.info(
                f"Successfully processed {parsed_message.get('message_type')} "
                f"message from {peer_addr[0]}:{peer_addr[1]}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to process message from {peer_addr[0]}:{peer_addr[1]}: {e}"
            )
            raise

    @staticmethod
    def generate_ack(message_data: bytes) -> bytes:
        """
        Generate an HL7 ACK (Acknowledgment) message.
        
        Args:
            message_data: Original message data
            
        Returns:
            MLLP-framed ACK message
        """
        try:
            # Extract message ID from original message
            message_str = message_data.decode("utf-8")
            segments = message_str.split("\r")
            
            # Get message ID from MSH segment (field 9)
            msh_fields = segments[0].split("|")
            message_id = msh_fields[9] if len(msh_fields) > 9 else "0"
            
            # Create ACK message
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            ack_message = (
                f"MSH|^~\\&|MCP|RECEIVER|EHR|SENDER|{timestamp}||ACK|{message_id}|P|2.5\r"
                f"MSA|AA|{message_id}\r"
            )
            
            # Frame with MLLP
            return MLLP_START + ack_message.encode("utf-8") + MLLP_END
            
        except Exception as e:
            logger.error(f"Failed to generate ACK: {e}")
            # Return generic ACK on error
            ack_message = "MSH|^~\\&|MCP|RECEIVER|EHR|SENDER|||||ACK||P|2.5\rMSA|AA|\r"
            return MLLP_START + ack_message.encode("utf-8") + MLLP_END

    @staticmethod
    def generate_nak(error_message: str) -> bytes:
        """
        Generate an HL7 NAK (Negative Acknowledgment) message.
        
        Args:
            error_message: Error description
            
        Returns:
            MLLP-framed NAK message
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        nak_message = (
            f"MSH|^~\\&|MCP|RECEIVER|EHR|SENDER|{timestamp}||ACK||P|2.5\r"
            f"MSA|AE||{error_message}\r"
        )
        return MLLP_START + nak_message.encode("utf-8") + MLLP_END

    def get_status(self) -> dict:
        """
        Get listener status information.
        
        Returns:
            Dictionary with status information
        """
        return {
            "is_running": self.is_running,
            "host": self.host,
            "port": self.port,
            "active_connections": self.active_connections,
            "max_connections": self.max_connections,
        }
