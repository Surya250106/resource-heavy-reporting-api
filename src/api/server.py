"""Flask REST API server for Resource-Heavy Reporting service."""

import os
from typing import Dict, Optional
from flask import Flask, jsonify, request, Response

from src.core.metrics_tracker import MetricsTracker
from src.proxies.protection_report_proxy import ProtectionReportProxy, AccessDeniedException
from src.proxies.virtual_report_proxy import VirtualReportProxy


def init_default_reports() -> Dict[str, ProtectionReportProxy]:
    """Initialize the default proxy-wrapped report database.
    
    CRITICAL: Initializes Protection Proxies wrapping Virtual Proxies.
    Never instantiates HeavyReportGenerator during startup.
    
    Returns:
        Dictionary mapping report_id to its ProtectionReportProxy instance.
    """
    return {
        "report-1": ProtectionReportProxy(
            underlying_report=VirtualReportProxy(
                report_id="report-1",
                title="Financial Q1"
            ),
            required_role="admin"
        ),
        "report-2": ProtectionReportProxy(
            underlying_report=VirtualReportProxy(
                report_id="report-2",
                title="User Analytics"
            ),
            required_role="manager"
        ),
        "report-3": ProtectionReportProxy(
            underlying_report=VirtualReportProxy(
                report_id="report-3",
                title="System Status"
            ),
            required_role="guest"
        ),
    }


def create_app(reports: Optional[Dict[str, ProtectionReportProxy]] = None) -> Flask:
    """Application factory for Flask reporting API.
    
    Args:
        reports: Optional reports mapping (defaults to init_default_reports()).
        
    Returns:
        Configured Flask application.
    """
    app = Flask(__name__)
    
    # In-memory persistence of report proxies across HTTP requests
    reports_db: Dict[str, ProtectionReportProxy] = (
        reports if reports is not None else init_default_reports()
    )

    @app.route("/health", methods=["GET"])
    def health() -> Response:
        """Health check endpoint for container monitoring."""
        return jsonify({"status": "ok"}), 200

    @app.route("/api/metrics", methods=["GET"])
    def get_metrics() -> Response:
        """Return the total number of HeavyReportGenerator instantiations."""
        return jsonify({
            "total_instantiations": MetricsTracker.get_count()
        }), 200

    @app.route("/api/metrics/reset", methods=["POST"])
    def reset_metrics() -> Response:
        """Reset the metrics instantiation counter."""
        MetricsTracker.reset()
        return jsonify({
            "message": "Metrics reset successfully"
        }), 200

    @app.route("/api/reports", methods=["GET"])
    def list_reports() -> Response:
        """List all available reports with their metadata.
        
        CRITICAL: Accesses proxy metadata methods (get_title, required_role)
        without triggering instantiation of HeavyReportGenerator.
        """
        report_list = [
            {
                "id": report_id,
                "title": proxy.get_title(),
                "required_role": proxy.required_role
            }
            for report_id, proxy in reports_db.items()
        ]
        return jsonify(report_list), 200

    @app.route("/api/reports/<report_id>/generate", methods=["GET"])
    def generate_report(report_id: str) -> Response:
        """Generate a specific report for an authorized role.
        
        Flow: Controller -> ProtectionReportProxy -> VirtualReportProxy -> HeavyReportGenerator
        """
        role = request.args.get("role")
        if role is None or role.strip() == "":
            return jsonify({"error": "Role is required"}), 400

        proxy = reports_db.get(report_id)
        if proxy is None:
            return jsonify({"error": "Report not found"}), 404

        try:
            # Delegate generation through proxy chain
            content = proxy.generate(user_role=role)
            return jsonify({
                "id": report_id,
                "content": content
            }), 200
        except AccessDeniedException:
            return jsonify({"error": "Access Denied"}), 403
        except Exception:
            # Mask internal error details from API responses
            return jsonify({"error": "Internal Server Error"}), 500

    return app


# Default application instance
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
