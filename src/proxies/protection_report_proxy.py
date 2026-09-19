"""Protection Proxy implementation for role-based access control."""

from src.core.report import Report


class AccessDeniedException(Exception):
    """Raised when a user role does not have permission to access the report."""
    pass


class ProtectionReportProxy(Report):
    """Protection Proxy in the Proxy design pattern.
    
    Controls access to the underlying Report subject based on user roles.
    Unauthorized requests are rejected before the underlying report's generate()
    method is called, preventing unnecessary resource allocation or initialization.
    """

    def __init__(self, underlying_report: Report, required_role: str) -> None:
        """Initialize the protection proxy.
        
        Args:
            underlying_report: The wrapped Report (typically a VirtualReportProxy).
            required_role: The exact role required to generate this report.
        """
        self.underlying_report = underlying_report
        self.required_role = required_role

    @property
    def report_id(self) -> str:
        """Get the report identifier from the underlying report if available."""
        return getattr(self.underlying_report, "report_id", "")

    def get_title(self) -> str:
        """Delegate getting the report title to the underlying report."""
        return self.underlying_report.get_title()

    def generate(self, user_role: str) -> str:
        """Enforce access control before delegating to the underlying report.
        
        Uses exact string comparison without role hierarchy.
        
        Args:
            user_role: The role supplied by the client.
            
        Returns:
            The generated report content string.
            
        Raises:
            AccessDeniedException: If user_role does not exactly match required_role.
        """
        if user_role != self.required_role:
            raise AccessDeniedException("Access Denied")
        
        # Access granted: delegate to the underlying proxy / subject
        return self.underlying_report.generate(user_role)
