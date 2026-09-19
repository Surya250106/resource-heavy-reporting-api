"""Report interface defining the common contract for reports and proxies."""

from abc import ABC, abstractmethod


class Report(ABC):
    """Abstract Base Class for all Report subjects and proxies.
    
    Demonstrates the Proxy Pattern: Both the Real Subject (HeavyReportGenerator)
    and the Proxies (VirtualReportProxy, ProtectionReportProxy) implement this
    common interface so client code (the API) interacts transparently with it.
    """

    @abstractmethod
    def get_title(self) -> str:
        """Return the title of the report.
        
        Must be accessible without triggering heavy object instantiation.
        """
        pass

    @abstractmethod
    def generate(self, user_role: str) -> str:
        """Generate and return the report content for the given user role.
        
        Args:
            user_role: The role of the requesting user.
            
        Returns:
            The generated report content string.
        """
        pass
