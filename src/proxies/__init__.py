"""Proxy implementations for reports."""

from src.proxies.virtual_report_proxy import VirtualReportProxy
from src.proxies.protection_report_proxy import ProtectionReportProxy, AccessDeniedException

__all__ = ["VirtualReportProxy", "ProtectionReportProxy", "AccessDeniedException"]
