"""Virtual Proxy implementation for lazy initialization and caching."""

import threading
from typing import Optional

from src.core.report import Report
from src.core.heavy_report_generator import HeavyReportGenerator


class VirtualReportProxy(Report):
    """Virtual Proxy in the Proxy design pattern.
    
    Delays the instantiation of the resource-heavy Real Subject (HeavyReportGenerator)
    until it is genuinely required by an authorized generate() call, and caches the
    instantiated subject for all subsequent calls.
    """

    def __init__(self, report_id: str, title: str) -> None:
        """Initialize the virtual proxy with metadata only.
        
        CRITICAL: Does NOT create HeavyReportGenerator during initialization.
        
        Args:
            report_id: Unique identifier for the report.
            title: Title of the report.
        """
        self.report_id = report_id
        self.title = title
        self._real_subject: Optional[HeavyReportGenerator] = None
        self._lock: threading.Lock = threading.Lock()

    def get_title(self) -> str:
        """Return the cached title directly without instantiating the real subject.
        
        Calling get_title() NEVER instantiates HeavyReportGenerator.
        """
        return self.title

    def generate(self, user_role: str) -> str:
        """Lazily initialize the real subject on first call and delegate generation.
        
        Thread-safe double-checked locking ensures that concurrent requests
        instantiate exactly one HeavyReportGenerator per proxy instance.
        
        Args:
            user_role: The role of the requesting user.
            
        Returns:
            The generated report content.
        """
        if self._real_subject is None:
            with self._lock:
                if self._real_subject is None:
                    # Lazy initialization of the real subject
                    self._real_subject = HeavyReportGenerator(
                        report_id=self.report_id,
                        title=self.title
                    )
        
        # Delegate execution to the cached real subject
        return self._real_subject.generate(user_role)
