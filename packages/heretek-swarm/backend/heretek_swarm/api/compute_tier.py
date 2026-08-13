"""
Compute Tier Detection API

Provides a FastAPI APIRouter with a single endpoint that classifies the host
machine's compute capacity into one of three tiers based on CPU count, RAM,
and GPU availability.  Intended for internal service-to-service use by the
Sentinel's AnomalyMonitor.

Tier classification rules
--------------------------
- Tier 1 (low)   : < 4 CPUs  *or*  < 8 GB RAM
- Tier 2 (medium): 4-7 CPUs *and* 8-31 GB RAM *and* no GPU
- Tier 3 (high)  : >= 8 CPUs *or* >= 32 GB RAM *or* GPU available

GPU detection attempts ``torch.cuda.is_available()`` and falls back gracefully
to ``False`` when PyTorch is not installed.
"""

from __future__ import annotations

import psutil
import structlog
from fastapi import APIRouter, Depends

from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger("api.compute_tier")

router = APIRouter(
    prefix="/api/compute",
    tags=["compute"],
    dependencies=[Depends(verify_auth)],
)


def _detect_gpu() -> bool:
    """Return True when a CUDA-capable GPU is detected via PyTorch.

    Falls back to ``False`` on ``ImportError`` so the endpoint remains
    functional even when PyTorch is not installed.
    """
    try:
        import torch
    except ImportError:
        logger.debug("torch_not_installed_gpu_fallback_false")
        return False

    try:
        available = torch.cuda.is_available()
    except Exception:
        logger.exception("cuda_check_failed")
        return False

    return bool(available)


def classify_tier(
    cpu_count: int,
    total_ram_gb: float,
    gpu_available: bool,
) -> int:
    """Classify the host into a compute tier (1, 2, or 3).

    Args:
        cpu_count: Number of logical CPUs reported by ``psutil``.
        total_ram_gb: Total physical RAM in GiB.
        gpu_available: Whether a CUDA-capable GPU was detected.

    Returns:
        Tier number: 1 (low), 2 (medium), or 3 (high).
    """
    # Tier 1 (safety net) checked first: low CPU or RAM → hard-freeze tier
    # regardless of other resources (e.g. 1 CPU + 32 GB RAM is still Tier 1).
    if cpu_count < 4 or total_ram_gb < 8:
        return 1

    # Tier 3 is the high-capacity gate.
    if cpu_count >= 8 or total_ram_gb >= 32 or gpu_available:
        return 3

    # Everything left: 4-7 CPUs, 8-31 GB RAM, no GPU → Tier 2.
    return 2


@router.get("/tier")
async def get_compute_tier() -> dict:
    """Report the detected compute tier and underlying host details.

    Returns
    -------
    dict
        ``{"tier": <int>, "details": {"cpu_count": <int>,
        "total_ram_gb": <float>, "gpu_available": <bool>}}``

    Notes
    -----
    This endpoint is designed for internal service-to-service use.
    Ensure your firewall / ingress rules reflect that constraint.
    """
    try:
        cpu_count = psutil.cpu_count() or 1
        total_ram_bytes = psutil.virtual_memory().total
        total_ram_gb = round(total_ram_bytes / (1024 ** 3), 2)
        gpu_available = _detect_gpu()
    except Exception:
        logger.exception("compute_tier_detection_failed")
        # Degrade gracefully: return Tier 1 on any unexpected error.
        return {
            "tier": 1,
            "details": {
                "cpu_count": 1,
                "total_ram_gb": 0.0,
                "gpu_available": False,
            },
        }

    tier = classify_tier(cpu_count, total_ram_gb, gpu_available)

    logger.info(
        "compute_tier_classified",
        tier=tier,
        cpu_count=cpu_count,
        total_ram_gb=total_ram_gb,
        gpu_available=gpu_available,
    )

    return {
        "tier": tier,
        "details": {
            "cpu_count": cpu_count,
            "total_ram_gb": total_ram_gb,
            "gpu_available": gpu_available,
        },
    }
