"""FastAPI dependency providers — wired by create_app()."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from tier1.events.nats_client import NatsClient
from tier1.llm.garage import ModelGarage
from tier1.persistence.postgres import PostgresPool
from tier1.persistence.qdrant import QdrantStore
from tier1.persistence.redis import RedisCache


def _pg(request: Request) -> PostgresPool:
    return request.app.state.pg


def _redis(request: Request) -> RedisCache:
    return request.app.state.redis


def _nats(request: Request) -> NatsClient:
    return request.app.state.nats


def _qdrant(request: Request) -> QdrantStore:
    return request.app.state.qdrant


def _garage(request: Request) -> ModelGarage:
    return request.app.state.garage


PgDep = Annotated[PostgresPool, Depends(_pg)]
RedisDep = Annotated[RedisCache, Depends(_redis)]
NatsDep = Annotated[NatsClient, Depends(_nats)]
QdrantDep = Annotated[QdrantStore, Depends(_qdrant)]
GarageDep = Annotated[ModelGarage, Depends(_garage)]
