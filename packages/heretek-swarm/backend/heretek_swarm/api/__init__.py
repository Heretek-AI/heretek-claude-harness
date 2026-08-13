"""
Heretek Swarm API Module

Provides FastAPI-based HTTP and WebSocket endpoints:
- Health checks for all services
- Agent management and monitoring
- Memory statistics
- A2A protocol WebSocket
- Consensus voting endpoints
- Plugin management

Example:
    ```python
    import uvicorn
    from heretek_swarm.api.main import app

    # Start the API server
    uvicorn.run(app, host="0.0.0.0", port=8000)
    ```
"""

from heretek_swarm.api import (
    collective_evolution,
    consciousness,
    consensus,
    emergent_intelligence,
    observability,
    plugins,
    skills,
    websockets,
)
from heretek_swarm.api.main import app

__all__ = [
    "app",
    "collective_evolution",
    "consciousness",
    "consensus",
    "emergent_intelligence",
    "observability",
    "plugins",
    "skills",
    "websockets",
]
