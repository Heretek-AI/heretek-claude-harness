"""NATS JetStream client.

Streams events on per-deliberation subjects:
    tier1.deliberation.{id}.events
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import nats
from nats.aio.client import Client as NatsConn
from nats.js.api import StreamConfig

from tier1.events.channels import DELIBERATION_SUBJECT_PREFIX

STREAM_NAME = "TIER1_DELIBERATIONS"
STREAM_SUBJECTS = [f"{DELIBERATION_SUBJECT_PREFIX}.*.events"]


class NatsClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.conn: NatsConn | None = None
        self.js = None

    async def connect(self) -> None:
        self.conn = await nats.connect(self.url)
        self.js = self.conn.jetstream()
        # Ensure the stream exists.
        try:
            await self.js.stream_info(STREAM_NAME)
        except Exception:
            await self.js.add_stream(StreamConfig(name=STREAM_NAME, subjects=STREAM_SUBJECTS))

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.drain()
            self.conn = None
            self.js = None

    async def publish(self, subject: str, payload: bytes) -> None:
        assert self.js is not None
        await self.js.publish(subject, payload)

    async def subscribe(self, subject: str) -> AsyncIterator[bytes]:
        assert self.js is not None
        # Consumer names cannot contain '.' or '*' or '>' — sanitize the subject.
        durable = f"watcher-{subject.replace('.', '_').replace('*', 'all').replace('>', 'gt')}"
        sub = await self.js.pull_subscribe(subject, durable=durable)
        while True:
            msgs = await sub.fetch(1, timeout=5)
            for msg in msgs:
                data = msg.data
                await msg.ack()
                yield data

    async def health(self) -> bool:
        return self.conn is not None and not self.conn.is_closed
