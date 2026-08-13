"""
NATS Event Mesh Infrastructure.

Provides event-driven communication for the Heretek Swarm using NATS.

Topics:
- agents.*.messages - Agent-to-agent messaging
- agents.*.events - Agent lifecycle events
- consensus.* - Consensus deliberations
- consciousness.* - Consciousness metrics
- swarm.* - Swarm-wide events
"""

from heretek_swarm.infrastructure.nats.ca import (
    CertificateAuthority,
    check_and_renew_certs,
    decrypt_certs,
    encrypt_certs,
    generate_cert_files,
    load_certificates,
    write_temp_cert_files,
)
from heretek_swarm.infrastructure.nats.client import NATSClient, get_nats_client
from heretek_swarm.infrastructure.nats.discovery import (
    AgentInfo,
    AgentRegistry,
    AgentStatus,
    HeartbeatMessage,
    PresenceAnnouncement,
    get_discovery_registry,
    shutdown_discovery_registry,
)
from heretek_swarm.infrastructure.nats.publisher import NATSPublisher
from heretek_swarm.infrastructure.nats.subscriber import NATSSubscriber

__all__ = [
    "AgentInfo",
    "AgentRegistry",
    "AgentStatus",
    "CertificateAuthority",
    "HeartbeatMessage",
    "NATSClient",
    "NATSPublisher",
    "NATSSubscriber",
    "PresenceAnnouncement",
    "check_and_renew_certs",
    "decrypt_certs",
    "encrypt_certs",
    "generate_cert_files",
    "get_discovery_registry",
    "get_nats_client",
    "load_certificates",
    "shutdown_discovery_registry",
    "write_temp_cert_files",
]
