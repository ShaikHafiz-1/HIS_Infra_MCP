"""
RabbitMQ Connector for Hospital Clinical Intelligence MCP Platform.

Provides async message queue integration with graceful degradation when
RabbitMQ is unavailable. Supports HL7, FHIR, DICOM, and device telemetry
message queues with dead-letter routing and retry logic.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from mcp_server.utils.logger import get_logger

# Optional aio_pika import with graceful fallback
try:
    import aio_pika
    from aio_pika import ExchangeType, Message, DeliveryMode
    HAS_AIOPIKA = True
except ImportError:
    HAS_AIOPIKA = False

logger = get_logger(__name__)

# Queue names
QUEUE_HL7 = "hl7_messages"
QUEUE_FHIR = "fhir_resources"
QUEUE_DICOM = "dicom_metadata"
QUEUE_DEVICE = "device_telemetry"
QUEUE_DEAD_LETTER = "dead_letter"

ALL_QUEUES = [QUEUE_HL7, QUEUE_FHIR, QUEUE_DICOM, QUEUE_DEVICE]

# Retry configuration
MAX_RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0  # seconds, doubles each attempt


class RabbitMQConnector:
    """
    Async RabbitMQ connector with graceful degradation.

    When RabbitMQ or aio_pika is unavailable the connector logs a warning
    and operates in a no-op / in-memory mode so the rest of the application
    continues to function normally.
    """

    def __init__(self, rabbitmq_url: Optional[str] = None):
        """
        Initialise the connector.

        Args:
            rabbitmq_url: AMQP connection URL. Defaults to settings value.
        """
        if rabbitmq_url is None:
            from config import settings
            rabbitmq_url = settings.rabbitmq_url

        self._url = rabbitmq_url
        self._connection: Optional[Any] = None
        self._channel: Optional[Any] = None
        self._connected: bool = False
        self._queues: Dict[str, Any] = {}
        # Simulated per-queue counters used when MQ is unavailable
        self._simulated_counts: Dict[str, int] = {q: 0 for q in ALL_QUEUES + [QUEUE_DEAD_LETTER]}

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """
        Establish connection to RabbitMQ with retry and exponential backoff.

        Returns:
            True if connected, False if graceful degradation is active.
        """
        if not HAS_AIOPIKA:
            logger.warning(
                "aio_pika is not installed. RabbitMQ integration is disabled. "
                "Install it with: pip install aio_pika"
            )
            return False

        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                logger.info(
                    f"Connecting to RabbitMQ (attempt {attempt}/{MAX_RETRY_ATTEMPTS}): {self._url}"
                )
                self._connection = await aio_pika.connect_robust(self._url)
                self._channel = await self._connection.channel()
                await self._channel.set_qos(prefetch_count=10)

                await self._declare_queues()

                self._connected = True
                logger.info("Successfully connected to RabbitMQ")
                return True

            except Exception as exc:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                if attempt < MAX_RETRY_ATTEMPTS:
                    logger.warning(
                        f"RabbitMQ connection attempt {attempt} failed: {exc}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.warning(
                        f"RabbitMQ unavailable after {MAX_RETRY_ATTEMPTS} attempts: {exc}. "
                        "Operating in degraded mode (no message queue)."
                    )

        self._connected = False
        return False

    async def _declare_queues(self) -> None:
        """Declare all required queues and the dead-letter exchange."""
        if not self._channel:
            return

        # Dead-letter exchange
        dlx = await self._channel.declare_exchange(
            "dead_letter_exchange",
            ExchangeType.DIRECT,
            durable=True,
        )

        # Dead-letter queue
        dlq = await self._channel.declare_queue(
            QUEUE_DEAD_LETTER,
            durable=True,
        )
        await dlq.bind(dlx, routing_key=QUEUE_DEAD_LETTER)
        self._queues[QUEUE_DEAD_LETTER] = dlq

        # Main queues with dead-letter routing
        for queue_name in ALL_QUEUES:
            queue = await self._channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "dead_letter_exchange",
                    "x-dead-letter-routing-key": QUEUE_DEAD_LETTER,
                    "x-message-ttl": 86_400_000,  # 24 hours in ms
                },
            )
            self._queues[queue_name] = queue
            logger.debug(f"Declared queue: {queue_name}")

    async def disconnect(self) -> None:
        """Gracefully close the RabbitMQ connection."""
        if self._connection and self._connected:
            try:
                await self._connection.close()
                logger.info("RabbitMQ connection closed")
            except Exception as exc:
                logger.warning(f"Error closing RabbitMQ connection: {exc}")
            finally:
                self._connected = False
                self._connection = None
                self._channel = None
                self._queues.clear()

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish_message(
        self,
        queue_name: str,
        message: Dict[str, Any],
        retry_count: int = 0,
    ) -> bool:
        """
        Publish a message to the specified queue.

        Args:
            queue_name: Target queue name.
            message: Message payload (will be JSON-encoded).
            retry_count: Internal retry counter (do not set manually).

        Returns:
            True if published (or simulated), False on unrecoverable error.
        """
        if not self._connected or not HAS_AIOPIKA:
            # Graceful degradation: log and increment simulated counter
            self._simulated_counts[queue_name] = (
                self._simulated_counts.get(queue_name, 0) + 1
            )
            logger.debug(
                f"[SIMULATED] Would publish to '{queue_name}': "
                f"{json.dumps(message)[:200]}"
            )
            return True

        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                body = json.dumps(message, default=str).encode()
                mq_message = Message(
                    body=body,
                    delivery_mode=DeliveryMode.PERSISTENT,
                    content_type="application/json",
                    headers={
                        "retry_count": retry_count,
                        "published_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                # Use default exchange with queue name as routing key
                await self._channel.default_exchange.publish(
                    mq_message,
                    routing_key=queue_name,
                )
                logger.debug(f"Published message to '{queue_name}' (size={len(body)}B)")
                return True

            except Exception as exc:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                if attempt < MAX_RETRY_ATTEMPTS:
                    logger.warning(
                        f"Publish to '{queue_name}' attempt {attempt} failed: {exc}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Failed to publish to '{queue_name}' after {MAX_RETRY_ATTEMPTS} "
                        f"attempts: {exc}"
                    )

        return False

    # ------------------------------------------------------------------
    # Consuming
    # ------------------------------------------------------------------

    async def consume_messages(
        self,
        queue_name: str,
        callback: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """
        Begin consuming messages from the specified queue.

        Args:
            queue_name: Queue to consume from.
            callback: Async callable invoked for each message.
                      Should accept a single dict argument.
        """
        if not self._connected or not HAS_AIOPIKA:
            logger.warning(
                f"RabbitMQ unavailable – cannot consume from '{queue_name}'. "
                "Graceful degradation is active."
            )
            return

        queue = self._queues.get(queue_name)
        if not queue:
            logger.error(f"Queue '{queue_name}' not found. Was connect() called?")
            return

        async def on_message(message: "aio_pika.IncomingMessage") -> None:
            async with message.process(requeue=False):
                try:
                    payload = json.loads(message.body.decode())
                    await callback(payload)
                except json.JSONDecodeError as exc:
                    logger.error(f"Invalid JSON in message from '{queue_name}': {exc}")
                except Exception as exc:
                    retry_count = (message.headers or {}).get("retry_count", 0)
                    if retry_count < MAX_RETRY_ATTEMPTS:
                        logger.warning(
                            f"Callback error for '{queue_name}' message "
                            f"(retry {retry_count + 1}/{MAX_RETRY_ATTEMPTS}): {exc}"
                        )
                        await self.publish_message(
                            queue_name,
                            json.loads(message.body.decode()),
                            retry_count=retry_count + 1,
                        )
                    else:
                        logger.error(
                            f"Message from '{queue_name}' exceeded max retries, "
                            f"routing to dead-letter: {exc}"
                        )
                        await self.publish_message(
                            QUEUE_DEAD_LETTER,
                            {
                                "original_queue": queue_name,
                                "error": str(exc),
                                "body": message.body.decode(errors="replace"),
                            },
                        )

        await queue.consume(on_message)
        logger.info(f"Started consuming from queue: {queue_name}")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """
        Return health status of the RabbitMQ connection.

        Returns:
            Dict with status, connected, and queue information.
        """
        if not HAS_AIOPIKA:
            return {
                "status": "degraded",
                "connected": False,
                "reason": "aio_pika not installed",
                "queues": list(ALL_QUEUES),
            }

        if not self._connected or self._connection is None:
            return {
                "status": "degraded",
                "connected": False,
                "reason": "Not connected to RabbitMQ",
                "queues": list(ALL_QUEUES),
            }

        try:
            # A closed connection raises immediately
            if self._connection.is_closed:
                self._connected = False
                return {
                    "status": "degraded",
                    "connected": False,
                    "reason": "Connection closed",
                    "queues": list(ALL_QUEUES),
                }
            return {
                "status": "healthy",
                "connected": True,
                "url": self._url.split("@")[-1],  # hide credentials
                "queues": list(self._queues.keys()),
            }
        except Exception as exc:
            return {
                "status": "degraded",
                "connected": False,
                "reason": str(exc),
                "queues": list(ALL_QUEUES),
            }

    # ------------------------------------------------------------------
    # Queue statistics
    # ------------------------------------------------------------------

    async def get_queue_stats(self) -> Dict[str, int]:
        """
        Return approximate message counts per queue.

        When RabbitMQ is unavailable the simulated counters (total published
        since process start) are returned instead.

        Returns:
            Dict mapping queue name to message count.
        """
        if not self._connected or not HAS_AIOPIKA:
            logger.debug("Returning simulated queue stats (MQ unavailable)")
            return dict(self._simulated_counts)

        stats: Dict[str, int] = {}
        for name, queue in self._queues.items():
            try:
                # aio_pika exposes declaration info; re-declare passively
                info = await self._channel.declare_queue(name, passive=True)
                stats[name] = info.declaration_result.message_count
            except Exception:
                stats[name] = 0
        return stats


# ---------------------------------------------------------------------------
# Message processor
# ---------------------------------------------------------------------------

class MessageQueueProcessor:
    """
    Processes messages from each clinical data queue.

    In a production system each method would persist the payload to the
    appropriate data store. For now each method logs what it would do.
    """

    def __init__(self, connector: RabbitMQConnector):
        self._connector = connector

    async def process_hl7_message(self, message: Dict[str, Any]) -> None:
        """
        Process an HL7 v2 message from the queue.

        Args:
            message: Decoded message payload.
        """
        msg_type = message.get("message_type", "unknown")
        patient_id = message.get("patient_id", "unknown")
        logger.info(
            f"[HL7] Processing message type={msg_type} patient_id={patient_id} "
            f"keys={list(message.keys())}"
        )
        # TODO: persist to database via HL7Normalizer pipeline

    async def process_fhir_resource(self, message: Dict[str, Any]) -> None:
        """
        Process a FHIR resource from the queue.

        Args:
            message: Decoded FHIR resource payload.
        """
        resource_type = message.get("resourceType", "unknown")
        resource_id = message.get("id", "unknown")
        logger.info(
            f"[FHIR] Processing resource resourceType={resource_type} id={resource_id}"
        )
        # TODO: persist to database via FHIRMapper pipeline

    async def process_dicom_metadata(self, message: Dict[str, Any]) -> None:
        """
        Process DICOM metadata from the queue.

        Args:
            message: Decoded DICOM metadata payload.
        """
        study_uid = message.get("StudyInstanceUID", "unknown")
        modality = message.get("Modality", "unknown")
        logger.info(
            f"[DICOM] Processing study StudyInstanceUID={study_uid} Modality={modality}"
        )
        # TODO: persist to database via DICOMNormalizer pipeline

    async def process_device_telemetry(self, message: Dict[str, Any]) -> None:
        """
        Process device telemetry from the queue.

        Args:
            message: Decoded device telemetry payload.
        """
        device_id = message.get("device_id", "unknown")
        event_type = message.get("event_type", "unknown")
        logger.info(
            f"[DEVICE] Processing telemetry device_id={device_id} event_type={event_type}"
        )
        # TODO: persist to database via DeviceTelemetry pipeline

    async def get_queue_stats(self) -> Dict[str, int]:
        """
        Return queue depth statistics.

        Returns:
            Dict mapping queue name to approximate message count.
        """
        return await self._connector.get_queue_stats()

    async def start_consumers(self) -> None:
        """Register all message-type consumers with the connector."""
        await self._connector.consume_messages(QUEUE_HL7, self.process_hl7_message)
        await self._connector.consume_messages(QUEUE_FHIR, self.process_fhir_resource)
        await self._connector.consume_messages(QUEUE_DICOM, self.process_dicom_metadata)
        await self._connector.consume_messages(QUEUE_DEVICE, self.process_device_telemetry)
        logger.info("All message queue consumers registered")


# ---------------------------------------------------------------------------
# Module-level singleton instances
# ---------------------------------------------------------------------------

rabbitmq_connector = RabbitMQConnector()
message_queue_processor = MessageQueueProcessor(rabbitmq_connector)
