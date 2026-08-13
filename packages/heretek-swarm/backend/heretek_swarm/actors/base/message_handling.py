"""
Message handling module for AgentActor.

This module contains:
- Message sending methods (send, send_to_actor, send_with_reply, broadcast)
- Message processing (_process_mailbox, process_message, put_message)
- Default message handlers (_handle_*)
- LLM integration (run_with_llm)
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.actors.base.core import ActorMessage, AgentActor
from heretek_swarm.observability.prometheus_native import (
    ACTOR_PROCESSING_DURATION,
    record_actor_processing,
)

logger = structlog.get_logger("AgentActor")


class AgentActorMessageHandling(AgentActor):
    """Mixin class for message handling functionality."""

    def _record_agent_interaction(self, from_agent: str, to_agent: str) -> None:
        """
        Record agent-to-agent interaction for consciousness metrics.

        Uses lazy import to avoid circular imports with the consciousness plugin.
        This is non-fatal: consciousness tracking failures must not break message delivery.
        """
        try:
            # Lazy import to avoid circular dependency
            from heretek_swarm.api.consciousness import get_consciousness_plugin

            plugin = get_consciousness_plugin()
            plugin.record_interaction(from_agent, to_agent)
        except Exception:
            # Consciousness tracking is non-fatal — do not break message delivery
            logger.debug(
                "Consciousness tracking unavailable, continuing message delivery",
                exc_info=True,
            )

    async def send(
        self,
        topic: str,
        content: dict[str, Any],
        message_type: str = "default",
        reply_to: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Send a message to a topic.

        Args:
            topic: Target topic
            content: Message content
            message_type: Type identifier for the message
            reply_to: Optional topic for responses
            correlation_id: Optional correlation ID
            metadata: Additional metadata

        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())

        message = ActorMessage(
            sender=self.agent_id,
            message_type=message_type,
            content=content,
            timestamp=datetime.now(UTC).isoformat(),
            correlation_id=correlation_id,
            reply_to=reply_to,
            metadata=metadata or {},
        )

        # Tier 1: Route through event mesh if available
        mesh_type = getattr(self, "mesh_type", "none")
        if await self._send_via_event_mesh(topic, message, message_id, message_type):
            logger.info(
                f"[{self.agent_id}] Tier-1 mesh route succeeded",
                extra={
                    "mesh_type": mesh_type,
                    "topic": topic,
                    "message_id": message_id,
                    "message_type": message_type,
                },
            )
            return message_id

        # Tier 1 unavailable or failed — log the reason at warning level
        if mesh_type == "none":
            logger.warning(
                f"[{self.agent_id}] Tier-1 mesh unavailable (no event mesh configured)",
                extra={"mesh_type": mesh_type, "topic": topic, "message_id": message_id},
            )

        # Tier 2: Direct delivery to actors subscribed to topic
        if await self._deliver_to_registry_actors(topic, message, message_id, message_type):
            return message_id

        # Tier 3: Queue for later delivery (last resort)
        logger.warning(
            f"[{self.agent_id}] Message {message_id} queued (no delivery mechanism available)",
            extra={"message_type": message_type, "topic": topic},
        )
        self._queue_message(message)
        return message_id

    async def _send_via_event_mesh(
        self,
        topic: str,
        message: ActorMessage,
        message_id: str,
        message_type: str,
    ) -> bool:
        """
        Attempt to send message via event mesh.

        Args:
            topic: Target topic
            message: The ActorMessage to send
            message_id: Message identifier for logging
            message_type: Message type for logging

        Returns:
            True if sent successfully, False otherwise
        """
        event_mesh = self._event_mesh or self.get_state("_event_mesh")
        if event_mesh is None:
            return False

        try:
            await event_mesh.send_to_json(
                topic,
                {
                    "type": message.message_type,
                    "from": self.agent_id,
                    "content": message.content,
                    "correlation_id": message.correlation_id,
                    "reply_to": message.reply_to,
                    "metadata": message.metadata,
                    "timestamp": message.timestamp,
                },
            )
            logger.info(
                f"[{self.agent_id}] Message {message_id} sent via event mesh to {topic}",
                extra={"message_type": message_type},
            )
            return True
        except Exception as e:
            logger.error(
                f"[{self.agent_id}] Event mesh send failed: {e}",
                extra={"message_id": message_id, "topic": topic},
            )
            return False

    async def _deliver_to_registry_actors(
        self,
        topic: str,
        message: ActorMessage,
        message_id: str,
        message_type: str,
    ) -> bool:
        """
        Attempt to deliver message directly to actors subscribed to the topic.

        Args:
            topic: Target topic
            message: The ActorMessage to deliver
            message_id: Message identifier for logging
            message_type: Message type for logging

        Returns:
            True if delivered successfully to at least one actor, False otherwise
        """
        actor_registry = self._get_actor_registry()
        if actor_registry is None:
            return False

        try:
            delivered = False
            for reg_actor in actor_registry.values():
                if topic in getattr(reg_actor, "topics", []):
                    recipient_id = getattr(reg_actor, "agent_id", None)
                    await reg_actor.put_message(message)
                    # Wire consciousness: record interaction for each recipient
                    if recipient_id:
                        self._record_agent_interaction(self.agent_id, recipient_id)
                    delivered = True
            if delivered:
                logger.info(
                    f"[{self.agent_id}] Message {message_id} delivered directly to topic subscribers",
                    extra={"message_type": message_type},
                )
                return True
            return False
        except Exception as e:
            logger.error(
                f"[{self.agent_id}] Direct delivery failed: {e}",
                extra={"message_id": message_id, "topic": topic},
            )
            return False

    def _queue_message(self, message: ActorMessage) -> None:
        """Queue a message for later delivery when event mesh becomes available."""
        pending_messages = self.get_state("_pending_messages", [])
        pending_messages.append(message)
        self.update_state("_pending_messages", pending_messages)
        logger.debug(
            f"[{self.agent_id}] Message queued for later delivery",
            extra={"message_type": message.message_type},
        )

    async def send_to_actor(
        self,
        target_actor_id: str,
        message_type: str,
        content: dict[str, Any],
        correlation_id: str | None = None,
    ) -> str:
        """
        Send a message directly to another actor.

        Args:
            target_actor_id: Target actor ID
            message_type: Message type identifier
            content: Message content
            correlation_id: Optional correlation ID

        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())

        # Use global actor registry from supervisor
        actor_registry = self._get_actor_registry()
        if actor_registry is not None and target_actor_id in actor_registry:
            try:
                target_actor = actor_registry[target_actor_id]
                message = ActorMessage(
                    sender=self.agent_id,
                    message_type=message_type,
                    content={
                        "message_type": message_type,
                        "content": content,
                        "sender": self.agent_id,
                    },
                    timestamp=datetime.now(UTC).isoformat(),
                    correlation_id=correlation_id,
                )
                await target_actor.put_message(message)
                # Wire consciousness: record this agent-to-agent interaction
                self._record_agent_interaction(self.agent_id, target_actor_id)
                logger.info(
                    f"[{self.agent_id}] Direct message sent to {target_actor_id}",
                    extra={"message_type": message_type},
                )
                return message_id
            except Exception as e:
                logger.error(
                    f"[{self.agent_id}] Direct actor send failed: {e}",
                    extra={"target": target_actor_id},
                )

        # Fallback to topic-based routing
        return await self.send(
            topic=f"actor:{target_actor_id}",
            content={
                "message_type": message_type,
                "content": content,
                "sender": self.agent_id,
            },
            message_type=message_type,
            correlation_id=correlation_id,
        )

    async def send_with_reply(
        self,
        recipient: str,
        message_type: str,
        content: dict[str, Any],
        timeout: int = 30,
    ) -> dict[str, Any] | None:
        """
        Send message and wait for reply with correlation tracking.

        Implements the request-reply pattern from Microsoft AutoGen for
        synchronous inter-agent communication.

        Args:
            recipient: Target actor ID or topic
            message_type: Message type identifier
            content: Message payload
            timeout: Seconds to wait for reply (default: 30)

        Returns:
            Reply content dict, or None if timeout/failure

        Raises:
            asyncio.TimeoutError: If no reply received within timeout
        """
        # Generate unique correlation ID for this request
        correlation_id = str(uuid.uuid4())
        reply_channel = f"reply_{self.agent_id}_{correlation_id}"

        logger.info(
            f"[{self.agent_id}] Sending request to {recipient} with correlation_id={correlation_id}",
            extra={"message_type": message_type, "timeout": timeout},
        )

        # Create a temporary queue for the reply
        reply_queue: asyncio.Queue = asyncio.Queue()

        # Register reply handler
        async def handle_reply(message: ActorMessage) -> None:
            """Handle incoming reply message."""
            await reply_queue.put(message)

        # Register the reply handler for this specific channel
        self.register_handler(reply_channel, handle_reply)

        try:
            # Send request with reply_to channel
            await self.send(
                topic=recipient,
                content=content,
                message_type=message_type,
                correlation_id=correlation_id,
                reply_to=reply_channel,
            )

            # Wait for reply with timeout
            try:
                reply_message = await asyncio.wait_for(
                    reply_queue.get(),
                    timeout=timeout,
                )

                logger.info(
                    f"[{self.agent_id}] Reply received for correlation_id={correlation_id}",
                    extra={"message_type": reply_message.message_type},
                )

                return reply_message.content

            except TimeoutError:
                logger.warning(
                    f"[{self.agent_id}] Request timeout after {timeout}s for correlation_id={correlation_id}",
                    extra={"recipient": recipient, "message_type": message_type},
                )
                raise

        finally:
            # Cleanup: unregister reply handler
            self.unregister_handler(reply_channel)

    async def put_message(self, message: ActorMessage) -> None:
        """
        Put a message in the actor's mailbox.

        Args:
            message: Actor message to process
        """
        # P1-10e fix: Add retry logic for message queuing instead of dropping
        max_retries = 3
        retry_delay = 0.1  # 100ms initial delay

        for attempt in range(max_retries):
            try:
                await asyncio.wait_for(
                    self.mailbox.put(message),
                    timeout=5.0,
                )
                logger.debug(
                    f"[{self.agent_id}] Message queued",
                    extra={"message_type": message.message_type},
                )
                return  # Success, exit retry loop
            except TimeoutError:
                if attempt < max_retries - 1:
                    # P1-10e fix: Retry with exponential backoff
                    logger.warning(
                        f"[{self.agent_id}] Mailbox full, retrying ({attempt + 1}/{max_retries})",
                        extra={"message_type": message.message_type},
                    )
                    await asyncio.sleep(retry_delay * (2**attempt))
                else:
                    # P1-10e fix: Only drop after all retries exhausted
                    logger.error(
                        f"[{self.agent_id}] Mailbox full after {max_retries} retries, message dropped",
                        extra={"message_type": message.message_type},
                    )
                    self.error_count += 1

    async def _process_mailbox(self) -> None:
        """Process messages from mailbox in a loop with continuous persistence."""
        logger.info(f"[{self.agent_id}] Starting mailbox processing")

        while self._running:
            try:
                # Get message from mailbox with timeout
                message = await asyncio.wait_for(
                    self.mailbox.get(),
                    timeout=1.0,
                )

                self.message_count += 1
                self._messages_since_persist += 1  # P0-1: Track for auto-persist
                self.last_activity = datetime.now(UTC).isoformat()

                # Process message with timing instrumentation.
                # Phase 2A.3 cutover: inline perf_counter + record_actor_processing
                # replaces the deleted observability.timing.TimedContext. The
                # legacy call to record_actor_execution (which populated the
                # collector's per-agent avg_task_duration_ms) is dropped along
                # with the collector itself in commit 9.
                actor_type = getattr(self, "actor_type", "unknown")
                start = time.perf_counter()
                try:
                    await self.process_message(message)
                finally:
                    record_actor_processing(
                        agent_id=self.agent_id,
                        actor_type=actor_type,
                        duration_seconds=time.perf_counter() - start,
                    )

                # P0-1: Auto-persist if interval configured and threshold reached
                if self._persistence_interval and self._messages_since_persist >= self._persistence_interval:
                    await self.save_state()
                    self._messages_since_persist = 0
                    logger.debug(
                        f"[{self.agent_id}] State persisted after {self._persistence_interval} messages",
                        extra={"total_messages": self.message_count},
                    )

                # Mark as done
                self.mailbox.task_done()

            except TimeoutError:
                # No messages, continue
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error_count += 1
                logger.exception(
                    f"[{self.agent_id}] Error processing message: {e}",
                )

    async def _validate_and_prepare_message(self, message: ActorMessage) -> ActorMessage | None:
        """Validate message input and return sanitized message or None if invalid."""
        if not hasattr(self, "validate_input"):
            return message

        is_valid, sanitized_content = await self.validate_input(
            input_data=message.content,
            operation=f"handle_{message.message_type}",
            source_id=message.sender,
        )
        if not is_valid:
            logger.warning(
                f"[{self.agent_id}] ZERO-02 validation rejected message",
                extra={
                    "message_type": message.message_type,
                    "sender": message.sender,
                },
            )
            self.error_count += 1
            return None
        message.content = sanitized_content
        return message

    async def _execute_handler_and_publish(self, message: ActorMessage, handler: callable) -> None:
        """Execute handler and publish result if successful."""
        try:
            result = await handler(message)
            if result and isinstance(result, dict) and result.get("status") != "error":
                reply_to = message.content.get("reply_to") if message.content else None
                await self.send(
                    topic=reply_to or f"results.{message.message_type}",
                    content=result,
                    message_type=f"{message.message_type}_response",
                    correlation_id=message.correlation_id,
                )
        except Exception as e:
            logger.exception(
                f"[{self.agent_id}] Error in handler for {message.message_type}: {e}",
            )
            self.error_count += 1

    async def process_message(self, message: ActorMessage) -> None:
        """Process an incoming message."""
        message = await self._validate_and_prepare_message(message)
        if message is None:
            return

        handler = self._message_handlers.get(message.message_type)
        if handler:
            await self._execute_handler_and_publish(message, handler)
        else:
            logger.warning(f"[{self.agent_id}] No handler for message type: {message.message_type}")

    async def broadcast(
        self,
        content: dict[str, Any],
        message_type: str = "broadcast",
    ) -> None:
        """
        Broadcast a message to all actors.

        Args:
            content: Message content
            message_type: Message type identifier
        """
        # Use event mesh broadcast if available
        event_mesh = self._event_mesh or self.get_state("_event_mesh")
        if event_mesh is not None:
            try:
                await event_mesh.broadcast_json(
                    {
                        "type": message_type,
                        "from": self.agent_id,
                        "content": content,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                logger.info(
                    f"[{self.agent_id}] Broadcast sent via event mesh",
                    extra={"message_type": message_type},
                )
                return
            except Exception as e:
                logger.error(
                    f"[{self.agent_id}] Event mesh broadcast failed: {e}",
                    extra={"message_type": message_type},
                )

        # Fallback: Broadcast to all actors via registry
        actor_registry = self._get_actor_registry()
        if actor_registry is not None:
            message = ActorMessage(
                sender=self.agent_id,
                message_type=message_type,
                content={
                    "message_type": message_type,
                    "content": content,
                    "sender": self.agent_id,
                },
                timestamp=datetime.now(UTC).isoformat(),
            )
            sent_count = 0
            for reg_actor_id, reg_actor in actor_registry.items():
                if reg_actor_id != self.agent_id:  # Don't send to self
                    try:
                        await reg_actor.put_message(message)
                        # Wire consciousness: record broadcast interaction
                        self._record_agent_interaction(self.agent_id, reg_actor_id)
                        sent_count += 1
                    except Exception as e:
                        logger.error(
                            f"[{self.agent_id}] Broadcast to {reg_actor_id} failed: {e}",
                            extra={"message_type": message_type},
                        )
            logger.info(
                f"[{self.agent_id}] Broadcast sent to {sent_count} actors via registry",
                extra={"message_type": message_type},
            )
            return

        # Last resort: topic-based broadcast
        await self.send(
            topic="broadcast",
            content={
                "message_type": message_type,
                "content": content,
                "sender": self.agent_id,
            },
            message_type=message_type,
        )

    # Default message handlers with Zero-Trust validation
    async def _handle_health_check(self, message: ActorMessage) -> None:
        """Handle health check requests with validation."""
        # P2-7 fix: Validate input before processing
        try:
            validated = self._validate_message_content("health_check", message.content)
            if validated and hasattr(validated, "reply_to") and validated.reply_to:
                reply_topic = validated.reply_to
            else:
                reply_topic = message.content.get("reply_to", "health")
        except ValueError as e:
            logger.error(f"[{self.agent_id}] Health check validation failed: {e}")
            return

        status = self.get_status()

        await self.send(
            topic=reply_topic,
            content={
                "message_type": "health_response",
                "status": {
                    "agent_id": status.agent_id,
                    "state": status.state.value,
                    "message_count": status.message_count,
                    "error_count": status.error_count,
                },
            },
            correlation_id=message.correlation_id,
        )

    async def _handle_suspend(self, message: ActorMessage) -> None:
        """Handle suspend requests with validation."""
        # P2-7 fix: Validate input before processing
        try:
            self._validate_message_content("suspend", message.content)
        except ValueError as e:
            logger.error(f"[{self.agent_id}] Suspend validation failed: {e}")
            return
        await self.suspend()

    async def _handle_resume(self, message: ActorMessage) -> None:
        """Handle resume requests with validation."""
        # P2-7 fix: Validate input before processing
        try:
            self._validate_message_content("resume", message.content)
        except ValueError as e:
            logger.error(f"[{self.agent_id}] Resume validation failed: {e}")
            return
        await self.resume()

    async def _handle_terminate(self, message: ActorMessage) -> None:
        """Handle terminate requests with validation."""
        # P2-7 fix: Validate input before processing
        try:
            validated = self._validate_message_content("terminate", message.content)
            if validated and validated.reason:
                logger.info(f"[{self.agent_id}] Termination requested: {validated.reason}")
        except ValueError as e:
            logger.error(f"[{self.agent_id}] Terminate validation failed: {e}")
            return
        await self.terminate()

    async def _handle_route_task(self, message: ActorMessage) -> None:
        """
        Handle route_task messages for on-demand task routing.

        This handler processes tasks dispatched via
        :meth:`StewardAgent.route_to_agent`.  Subclasses can override
        :meth:`_process_route_task` to implement custom task handling.

        The handler:
        1. Logs receipt via structlog with target_agent, task_type, correlation_id
        2. Calls :meth:`_process_route_task(payload)` for actual processing
        3. Optionally sends a response back via ``reply_to`` if the payload
           includes one

        Args:
            message: ActorMessage containing the route_task payload
        """
        payload = message.content.get("content", message.content)
        target_agent = payload.get("target_agent", "unknown")
        task_type = payload.get("task_type", "unknown")
        correlation_id = payload.get("correlation_id", message.correlation_id)

        logger.info(
            f"[{self.agent_id}] Received route_task",
            extra={
                "target_agent": target_agent,
                "task_type": task_type,
                "correlation_id": correlation_id,
                "sender": message.sender,
            },
        )

        # Process the routed task
        result = await self._process_route_task(payload)

        # Send response if reply_to is specified in the payload
        reply_to = payload.get("reply_to")
        if reply_to:
            await self.send(
                topic=reply_to,
                content={
                    "message_type": "route_task_response",
                    "task_type": task_type,
                    "correlation_id": correlation_id,
                    "result": result,
                },
                correlation_id=correlation_id,
            )

    async def _process_route_task(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process a routed task payload.

        Subclasses should override this method to implement custom task
        processing.  The default implementation logs a warning and returns
        ``{"status": "unhandled"}`` — providing graceful degradation so
        agents that register the handler but don't override it still log and
        don't crash.

        Args:
            payload: The route_task payload dict containing target_agent,
                     task_type, task_data, correlation_id, sender, timestamp.

        Returns:
            A dict with at minimum a ``"status"`` key.  Subclasses may
            include additional keys such as ``"result"``, ``"error"``, etc.
        """
        task_type = payload.get("task_type", "unknown")
        logger.warning(
            f"[{self.agent_id}] Route task not handled — no override for {task_type}",
            extra={
                "task_type": task_type,
                "target_agent": payload.get("target_agent"),
                "correlation_id": payload.get("correlation_id"),
            },
        )
        return {"status": "unhandled", "task_type": task_type}

    async def _handle_collective_task(self, message: ActorMessage) -> None:
        """
        Handle collective task contribution requests with validation.

        This handler processes collective task requests and returns contributions.
        Subclasses can override this method to provide custom contribution logic.

        Args:
            message: ActorMessage with collective task details
        """
        # P2-7 fix: Validate input before processing
        try:
            validated = self._validate_message_content("collective_task", message.content)
            if validated:
                task_id = validated.task_id
                task_type = validated.task_type
                description = validated.description
                input_data = validated.input_data
                protocol = validated.protocol
                reply_to = validated.reply_to
            else:
                # Fallback to unvalidated access
                task_id = message.content.get("task_id")
                task_type = message.content.get("task_type")
                description = message.content.get("description")
                input_data = message.content.get("input_data", {})
                protocol = message.content.get("protocol", {})
                reply_to = message.content.get("reply_to")
        except ValueError as e:
            logger.error(f"[{self.agent_id}] Collective task validation failed: {e}")
            return

        logger.info(
            f"[{self.agent_id}] Received collective task",
            extra={
                "task_id": task_id,
                "task_type": task_type,
                "description": description,
            },
        )

        # Generate contribution (subclasses should override for custom logic)
        contribution = await self._generate_collective_contribution(
            task_id=task_id,
            task_type=task_type,
            description=description,
            input_data=input_data,
            protocol=protocol,
        )

        # Send response if reply_to is provided
        if reply_to:
            await self.send(
                topic=reply_to,
                content={
                    "message_type": "collective_task_response",
                    "task_id": task_id,
                    "correlation_id": message.correlation_id,
                    **contribution,
                },
                correlation_id=message.correlation_id,
            )

    async def _generate_collective_contribution(
        self,
        task_id: str,
        task_type: str,
        description: str,
        input_data: dict[str, Any],
        protocol: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate contribution for a collective task.

        Subclasses should override this method to provide custom contribution logic.
        Default implementation uses LLM if available, otherwise returns fallback.

        Args:
            task_id: Task identifier
            task_type: Type of task
            description: Task description
            input_data: Task input data
            protocol: Communication protocol

        Returns:
            Dict with contribution and confidence
        """
        # Try using LLM if available
        if self.pydantic_ai_agent is not None:
            try:
                prompt = f"""You are participating in a collective task.

Task Details:
- Task ID: {task_id}
- Task Type: {task_type}
- Description: {description}
- Input Data: {input_data}

Please provide your analysis and recommendation for this collective task."""

                response = await self.run_with_llm(prompt, timeout=60)
                return {
                    "contribution": {
                        "analysis": response,
                        "recommendation": "llm_generated",
                        "method": "run_with_llm",
                    },
                    "confidence": 0.75,
                }
            except Exception as e:
                logger.error(f"[{self.agent_id}] LLM contribution error: {e}")

        # Fallback contribution
        return {
            "contribution": {
                "analysis": f"Analysis from {self.name} for task: {description}",
                "recommendation": f"{self.name}_recommendation",
                "method": "fallback",
            },
            "confidence": 0.6,
        }

    def _get_actor_registry(self) -> dict[str, "AgentActor"] | None:
        """
        Get global actor registry from supervisor.

        This enables message delivery by accessing the supervisor's actor registry.

        Returns:
            Actor registry dict or None if supervisor not available
        """
        try:
            from heretek_swarm.actors.supervisor import get_supervisor

            supervisor = get_supervisor()
            if supervisor and hasattr(supervisor, "actors"):
                return supervisor.actors
        except (ImportError, Exception):
            logger.warning("Failed to retrieve supervisor actors", exc_info=True)
        return None

    async def run_with_llm(self, prompt: str, timeout: int = 60, **kwargs) -> str:
        """
        Run a prompt through the best available LLM provider.

        When a model_router is configured and has registered providers, the call
        is routed through AgentModelRouter → ModelGarage for per-task complexity-based
        provider selection. Falls back to self.swarms_agent.run() otherwise.

        Args:
            prompt: Input prompt
            timeout: Timeout in seconds (default: 60)
            **kwargs: Additional arguments for agent run

        Returns:
            Agent response as string

        Raises:
            RuntimeError: If no LLM path is available
            asyncio.TimeoutError: If LLM call times out
            ValueError: If LLM output fails validation
        """
        import time

        from heretek_swarm.observability.prometheus_native import (
            record_llm_call,
            record_llm_tokens,
        )

        start_time = time.perf_counter()
        raw_response: str | None = None
        model_name: str = "unknown"
        provider_name: str = "unknown"
        prompt_tokens: int = 0
        completion_tokens: int = 0
        total_tokens: int = 0

        # Try routing through AgentModelRouter when providers are available
        router = getattr(self, "_model_router", None)
        if router is not None:
            try:
                # Classify the task and get a routing decision
                decision = router.route(
                    task=prompt,
                    tokens_estimate=len(prompt.split()),
                )

                # Build the LLM request through ModelGarage if available
                # Otherwise fall back to the swarms agent
                model_garage = getattr(router, "_model_garage", None)
                if model_garage is not None:
                    from heretek_swarm_core.llm.model_garage import ChatMessage, LLMRequest

                    request = LLMRequest(
                        messages=[ChatMessage(role="user", content=prompt)],
                        model=decision.model,
                        temperature=kwargs.pop("temperature", 0.7),
                        max_tokens=kwargs.pop("max_tokens", None),
                    )
                    # Phase 2A.3 cutover: inline perf_counter + record_actor_processing
                    # replaces the deleted TimedContext (observability.timing).
                    actor_type = getattr(self, "actor_type", "unknown")
                    start = time.perf_counter()
                    try:
                        response = await model_garage.complete(
                            messages=request.messages,
                            model=decision.model,
                            provider_id=decision.provider_id,
                        )
                    finally:
                        record_actor_processing(
                            agent_id=self.agent_id,
                            actor_type=actor_type,
                            duration_seconds=time.perf_counter() - start,
                        )
                    logger.info(
                        f"[{self.agent_id}] Routed via garage",
                        extra={
                            "provider": decision.provider_id,
                            "model": decision.model,
                            "complexity": decision.complexity.value,
                            "confidence": decision.confidence,
                            "tokens": response.total_tokens,
                            "latency_ms": response.latency_ms,
                        },
                    )
                    router.record_usage(decision.provider_id, response)
                    raw_response = response.content
                    model_name = decision.model
                    provider_name = decision.provider_id
                    prompt_tokens = response.prompt_tokens
                    completion_tokens = response.completion_tokens
                    total_tokens = response.total_tokens

                # Router exists but no garage — fall back to swarms_agent
                if raw_response is None:
                    logger.info(
                        f"[{self.agent_id}] Router available, falling back to swarms_agent",
                        extra={"provider": decision.provider_id, "model": decision.model},
                    )
            except RuntimeError:
                # No providers registered in router, fall through to swarms_agent
                logger.debug(f"[{self.agent_id}] No router providers, using swarms_agent fallback")
            except Exception as e:
                logger.warning(f"[{self.agent_id}] Router failed, using swarms_agent fallback: {e}")

        # Fallback: use the pydantic-ai agent directly
        if raw_response is None:
            pydantic_ai_agent = getattr(self, "pydantic_ai_agent", None)
            if pydantic_ai_agent is None:
                raise RuntimeError("No LLM path available — configure providers or provide a pydantic_ai_agent")

            try:
                # Phase 2A.3 cutover: inline perf_counter + record_actor_processing
                # replaces the deleted TimedContext (observability.timing).
                actor_type = getattr(self, "actor_type", "unknown")
                start = time.perf_counter()
                try:
                    pydantic_ai_result = await asyncio.wait_for(
                        pydantic_ai_agent.run(prompt, **kwargs),
                        timeout=timeout,
                    )
                    raw_response = getattr(pydantic_ai_result, "output", str(pydantic_ai_result))
                finally:
                    record_actor_processing(
                        agent_id=self.agent_id,
                        actor_type=actor_type,
                        duration_seconds=time.perf_counter() - start,
                    )
                model_name = "pydantic_ai_agent"
                provider_name = "pydantic_ai_agent"
                # Estimate token counts using the ~4 characters per token baseline approximation
                prompt_tokens = len(prompt) // 4
                completion_tokens = len(raw_response) // 4
                total_tokens = prompt_tokens + completion_tokens
            except TimeoutError:
                logger.error(f"[{self.agent_id}] LLM call timed out after {timeout}s")
                raise
            except Exception as e:
                logger.exception(f"[{self.agent_id}] LLM call failed: {e}")
                raise

        # --- LLM output validation (S04: single choke point for all agent responses) ---
        from heretek_swarm_core.validation.llm_output import validate_llm_text

        validation_result = validate_llm_text(raw_response)
        if not validation_result.valid:
            truncated = raw_response[:500] if len(raw_response) > 500 else raw_response
            logger.error(
                "llm_output_validation_failed",
                extra={
                    "truncated_output": truncated,
                    "model": model_name,
                    "agent_id": self.agent_id,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                },
            )
            raise ValueError(
                f"LLM output validation failed for agent '{self.agent_id}' "
                f"(model={model_name}): {'; '.join(validation_result.errors)}"
            )

        logger.debug(
            "llm_output_validation_passed",
            extra={
                "model": model_name,
                "agent_id": self.agent_id,
            },
        )

        # Record LLM call duration and token usage metrics
        duration = time.perf_counter() - start_time
        try:
            record_llm_call(
                agent_id=self.agent_id,
                provider=provider_name,
                model=model_name,
                duration_seconds=duration,
            )
            record_llm_tokens(
                agent_id=self.agent_id,
                provider=provider_name,
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        except Exception as e:
            logger.debug("failed_to_record_llm_telemetry_metrics", error=str(e))

        # Instrument standard OpenTelemetry / OpenLLMetry trace span for cognitive tracing
        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("heretek_swarm.cognitive_telemetry")
            with tracer.start_as_current_span(
                "llm.call",
                attributes={
                    "gen_ai.client.name": "heretek_swarm",
                    "gen_ai.system": provider_name,
                    "gen_ai.request.model": model_name,
                    "gen_ai.usage.prompt_tokens": prompt_tokens,
                    "gen_ai.usage.completion_tokens": completion_tokens,
                    "gen_ai.usage.total_tokens": total_tokens,
                    "agent_id": self.agent_id,
                    "duration_seconds": duration,
                },
            ):
                pass
        except Exception as e:
            logger.debug("failed_to_emit_otel_gen_ai_trace_span", error=str(e))
        return raw_response

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to maintain actor liveness via NATS."""
        while self._running:
            try:
                self.last_activity = datetime.now(UTC).isoformat()
                await self._publish_heartbeat_if_connected()
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.agent_id}] Heartbeat loop error: {e}")
                # Back off on error so a persistent failure cannot turn this
                # into a tight loop that starves the event loop.
                await asyncio.sleep(self.heartbeat_interval)

    async def _publish_heartbeat_if_connected(self) -> None:
        """Publish heartbeat to NATS event mesh if connected."""
        if self._event_mesh is None:
            return
        heartbeat_data = self._build_heartbeat_data()
        try:
            await self._event_mesh.publish(
                f"system.health.heartbeat.{self.agent_id}",
                heartbeat_data,
            )
            logger.debug(
                f"[{self.agent_id}] Heartbeat published",
                extra={"state": heartbeat_data["state"]},
            )
        except Exception as e:
            logger.warning(f"[{self.agent_id}] Failed to publish heartbeat: {e}")

    def _build_heartbeat_data(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "actor_type": getattr(self, "actor_type", "AgentActor"),
            "state": self.state.value if hasattr(self, "state") else "active",
            "timestamp": self.last_activity,
            "error_count": getattr(self, "error_count", 0),
            "mailbox_size": self.mailbox.qsize() if hasattr(self, "mailbox") else 0,
        }


# Bind message handling methods to AgentActor
AgentActor.send = AgentActorMessageHandling.send
AgentActor._send_via_event_mesh = AgentActorMessageHandling._send_via_event_mesh
AgentActor._validate_and_prepare_message = AgentActorMessageHandling._validate_and_prepare_message
AgentActor._execute_handler_and_publish = AgentActorMessageHandling._execute_handler_and_publish
AgentActor._deliver_to_registry_actors = AgentActorMessageHandling._deliver_to_registry_actors
AgentActor._queue_message = AgentActorMessageHandling._queue_message
AgentActor.send_to_actor = AgentActorMessageHandling.send_to_actor
AgentActor.send_with_reply = AgentActorMessageHandling.send_with_reply
AgentActor.put_message = AgentActorMessageHandling.put_message
AgentActor._process_mailbox = AgentActorMessageHandling._process_mailbox
AgentActor.process_message = AgentActorMessageHandling.process_message
AgentActor.broadcast = AgentActorMessageHandling.broadcast
AgentActor._handle_health_check = AgentActorMessageHandling._handle_health_check
AgentActor._handle_suspend = AgentActorMessageHandling._handle_suspend
AgentActor._handle_resume = AgentActorMessageHandling._handle_resume
AgentActor._handle_terminate = AgentActorMessageHandling._handle_terminate
AgentActor._handle_route_task = AgentActorMessageHandling._handle_route_task
AgentActor._process_route_task = AgentActorMessageHandling._process_route_task
AgentActor._handle_collective_task = AgentActorMessageHandling._handle_collective_task
AgentActor._generate_collective_contribution = AgentActorMessageHandling._generate_collective_contribution
AgentActor._get_actor_registry = AgentActorMessageHandling._get_actor_registry
AgentActor.run_with_llm = AgentActorMessageHandling.run_with_llm
AgentActor._heartbeat_loop = AgentActorMessageHandling._heartbeat_loop
AgentActor._publish_heartbeat_if_connected = AgentActorMessageHandling._publish_heartbeat_if_connected
AgentActor._build_heartbeat_data = AgentActorMessageHandling._build_heartbeat_data
