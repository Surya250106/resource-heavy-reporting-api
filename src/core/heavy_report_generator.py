"""HeavyReportGenerator representing the Real Subject in the Proxy Pattern."""

from src.core.report import Report
from src.core.metrics_tracker import MetricsTracker


class HeavyReportGenerator(Report):
    """Real Subject in the Proxy design pattern.
    
    Represents a resource-intensive report generator. Its instantiation is
    expensive and must only occur on demand (lazy loading via Virtual Proxy).
    """

    def __init__(self, report_id: str, title: str) -> None:
        """Initialize the heavy report generator and increment the metrics tracker.
        
        Args:
            report_id: Unique identifier for the report.
            title: Human-readable title of the report.
        """
        self.report_id = report_id
        self.title = title
        
        # Increment metric on actual construction to prove lazy initialization
        MetricsTracker.increment()

    def get_title(self) -> str:
        """Return the report title."""
        return self.title

    def generate(self, user_role: str) -> str:
        """Generate the report content.
        
        Args:
            user_role: Role of the requesting user.
            
        Returns:
            Formatted report content string.
        """
        return f"Report content for {self.title}"
