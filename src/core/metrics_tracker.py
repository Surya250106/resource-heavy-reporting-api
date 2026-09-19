"""Metrics tracker for tracking HeavyReportGenerator instantiations."""

import threading


class MetricsTracker:
    """Thread-safe global tracker for HeavyReportGenerator instantiations.
    
    This metric proves lazy initialization: increments occur exclusively
    within the HeavyReportGenerator constructor.
    """

    _count: int = 0
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def increment(cls) -> None:
        """Increment the instantiation counter in a thread-safe manner."""
        with cls._lock:
            cls._count += 1

    @classmethod
    def get_count(cls) -> int:
        """Get the total number of HeavyReportGenerator instantiations."""
        with cls._lock:
            return cls._count

    @classmethod
    def reset(cls) -> None:
        """Reset the instantiation counter to zero."""
        with cls._lock:
            cls._count = 0
