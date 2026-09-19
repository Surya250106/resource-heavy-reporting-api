"""Automated test suite for Resource-Heavy Reporting REST API and Proxy Pattern."""

import concurrent.futures
import pytest
from src.core.metrics_tracker import MetricsTracker
from src.core.heavy_report_generator import HeavyReportGenerator
from src.proxies.virtual_report_proxy import VirtualReportProxy
from src.proxies.protection_report_proxy import ProtectionReportProxy, AccessDeniedException
from src.api.server import create_app, init_default_reports


@pytest.fixture(autouse=True)
def reset_metrics_fixture():
    """Reset MetricsTracker before and after each test for test isolation."""
    MetricsTracker.reset()
    yield
    MetricsTracker.reset()


@pytest.fixture
def client():
    """Create a fresh Flask test client with fresh proxy instances."""
    app = create_app(reports=init_default_reports())
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ==============================================================================
# Requirement Tests
# ==============================================================================

def test_health_endpoint(client):
    """Test 1: Health endpoint returns HTTP 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_initial_metrics_zero(client):
    """Test 2: Initial metrics count is 0 as an integer."""
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.get_json()
    assert data == {"total_instantiations": 0}
    assert isinstance(data["total_instantiations"], int)


def test_listing_reports(client):
    """Test 3: Listing reports returns exactly three reports with expected metadata."""
    response = client.get("/api/reports")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 3

    expected = [
        {"id": "report-1", "title": "Financial Q1", "required_role": "admin"},
        {"id": "report-2", "title": "User Analytics", "required_role": "manager"},
        {"id": "report-3", "title": "System Status", "required_role": "guest"},
    ]
    assert data == expected


def test_listing_reports_does_not_instantiate_heavy_objects(client):
    """Test 4: Listing reports does not instantiate HeavyReportGenerator (metrics remain 0)."""
    assert MetricsTracker.get_count() == 0
    response = client.get("/api/reports")
    assert response.status_code == 200
    assert MetricsTracker.get_count() == 0

    metrics_res = client.get("/api/metrics")
    assert metrics_res.get_json() == {"total_instantiations": 0}


def test_first_authorized_generation_instantiates_heavy_object(client):
    """Test 5: First authorized generation instantiates exactly one heavy object."""
    assert MetricsTracker.get_count() == 0
    response = client.get("/api/reports/report-3/generate?role=guest")
    assert response.status_code == 200
    assert response.get_json() == {
        "id": "report-3",
        "content": "Report content for System Status",
    }
    assert MetricsTracker.get_count() == 1


def test_repeated_generation_reuses_instance(client):
    """Test 6: Repeated generation of the same report does not increase instantiation count."""
    for _ in range(5):
        response = client.get("/api/reports/report-3/generate?role=guest")
        assert response.status_code == 200
        assert response.get_json() == {
            "id": "report-3",
            "content": "Report content for System Status",
        }
    
    # Still only 1 instantiation across all 5 requests
    assert MetricsTracker.get_count() == 1


def test_unauthorized_generation_returns_403(client):
    """Test 7: Unauthorized generation returns HTTP 403 with Access Denied."""
    response = client.get("/api/reports/report-1/generate?role=guest")
    assert response.status_code == 403
    assert response.get_json() == {"error": "Access Denied"}


def test_unauthorized_generation_does_not_increase_instantiation_count(client):
    """Test 8: Unauthorized generation does not instantiate heavy object."""
    assert MetricsTracker.get_count() == 0
    
    # Try unauthorized access on report-1 (requires admin)
    res1 = client.get("/api/reports/report-1/generate?role=guest")
    assert res1.status_code == 403
    assert MetricsTracker.get_count() == 0

    # Try unauthorized access on report-2 (requires manager)
    res2 = client.get("/api/reports/report-2/generate?role=guest")
    assert res2.status_code == 403
    assert MetricsTracker.get_count() == 0


def test_authorized_generation_succeeds(client):
    """Test 9: Authorized generation for each report succeeds with correct content."""
    # report-1 (admin)
    res1 = client.get("/api/reports/report-1/generate?role=admin")
    assert res1.status_code == 200
    assert res1.get_json() == {
        "id": "report-1",
        "content": "Report content for Financial Q1",
    }

    # report-2 (manager)
    res2 = client.get("/api/reports/report-2/generate?role=manager")
    assert res2.status_code == 200
    assert res2.get_json() == {
        "id": "report-2",
        "content": "Report content for User Analytics",
    }

    # Total instantiations should now be 2
    assert MetricsTracker.get_count() == 2


def test_metrics_reset_works(client):
    """Test 10: Resetting metrics resets the count to 0."""
    # Trigger one instantiation
    client.get("/api/reports/report-3/generate?role=guest")
    assert MetricsTracker.get_count() == 1

    # Reset metrics
    reset_res = client.post("/api/metrics/reset")
    assert reset_res.status_code == 200
    assert reset_res.get_json() == {"message": "Metrics reset successfully"}

    # Verify count is 0
    metrics_res = client.get("/api/metrics")
    assert metrics_res.get_json() == {"total_instantiations": 0}
    assert MetricsTracker.get_count() == 0


def test_invalid_report_returns_404(client):
    """Test 11: Non-existent report returns HTTP 404 with exact error message."""
    response = client.get("/api/reports/non-existent-report/generate?role=admin")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Report not found"}
    assert MetricsTracker.get_count() == 0


def test_missing_role_returns_400(client):
    """Test 12: Missing or blank role parameter returns HTTP 400."""
    res1 = client.get("/api/reports/report-1/generate")
    assert res1.status_code == 400
    assert res1.get_json() == {"error": "Role is required"}

    res2 = client.get("/api/reports/report-1/generate?role=")
    assert res2.status_code == 400
    assert res2.get_json() == {"error": "Role is required"}
    assert MetricsTracker.get_count() == 0


# ==============================================================================
# Critical Evaluation Sequence Test
# ==============================================================================

def test_critical_evaluation_sequence(client):
    """Test full evaluation sequence as specified in requirements."""
    # 1. Start application -> GET /api/metrics => 0
    m0 = client.get("/api/metrics")
    assert m0.status_code == 200
    assert m0.get_json() == {"total_instantiations": 0}

    # 2. GET /api/reports => exactly 3 reports, metrics still 0
    r = client.get("/api/reports")
    assert r.status_code == 200
    assert len(r.get_json()) == 3
    m1 = client.get("/api/metrics")
    assert m1.get_json() == {"total_instantiations": 0}

    # 3. GET /api/reports/report-3/generate?role=guest => 200, metrics 1
    g1 = client.get("/api/reports/report-3/generate?role=guest")
    assert g1.status_code == 200
    assert g1.get_json() == {"id": "report-3", "content": "Report content for System Status"}
    m2 = client.get("/api/metrics")
    assert m2.get_json() == {"total_instantiations": 1}

    # 4. Call report-3 generate three additional times => 200, metrics still 1
    for _ in range(3):
        g_repeat = client.get("/api/reports/report-3/generate?role=guest")
        assert g_repeat.status_code == 200
    m3 = client.get("/api/metrics")
    assert m3.get_json() == {"total_instantiations": 1}

    # 5. GET /api/reports/report-1/generate?role=guest => 403, metrics still 1
    g_unauth = client.get("/api/reports/report-1/generate?role=guest")
    assert g_unauth.status_code == 403
    assert g_unauth.get_json() == {"error": "Access Denied"}
    m4 = client.get("/api/metrics")
    assert m4.get_json() == {"total_instantiations": 1}

    # 6. GET /api/reports/report-1/generate?role=admin => 200, metrics 2
    g_auth = client.get("/api/reports/report-1/generate?role=admin")
    assert g_auth.status_code == 200
    assert g_auth.get_json() == {"id": "report-1", "content": "Report content for Financial Q1"}
    m5 = client.get("/api/metrics")
    assert m5.get_json() == {"total_instantiations": 2}

    # 7. POST /api/metrics/reset => 200, metrics 0
    rst = client.post("/api/metrics/reset")
    assert rst.status_code == 200
    assert rst.get_json() == {"message": "Metrics reset successfully"}
    m6 = client.get("/api/metrics")
    assert m6.get_json() == {"total_instantiations": 0}

    # 8. GET /api/reports/non-existent-report/generate?role=admin => 404
    nf = client.get("/api/reports/non-existent-report/generate?role=admin")
    assert nf.status_code == 404
    assert nf.get_json() == {"error": "Report not found"}


# ==============================================================================
# Unit Tests for Proxy Pattern Components
# ==============================================================================

def test_heavy_report_generator_direct():
    """Unit test for HeavyReportGenerator subject."""
    assert MetricsTracker.get_count() == 0
    heavy = HeavyReportGenerator("test-id", "Test Title")
    assert MetricsTracker.get_count() == 1
    assert heavy.get_title() == "Test Title"
    assert heavy.generate("admin") == "Report content for Test Title"


def test_virtual_proxy_lazy_and_caching():
    """Unit test for VirtualReportProxy."""
    assert MetricsTracker.get_count() == 0
    vproxy = VirtualReportProxy("test-id", "Test Title")
    
    # Constructor must not increment
    assert MetricsTracker.get_count() == 0
    assert vproxy._real_subject is None
    
    # get_title() must not increment
    assert vproxy.get_title() == "Test Title"
    assert MetricsTracker.get_count() == 0
    
    # First generate() creates real subject
    content1 = vproxy.generate("admin")
    assert content1 == "Report content for Test Title"
    assert MetricsTracker.get_count() == 1
    assert vproxy._real_subject is not None
    
    # Second generate() reuses cached real subject
    content2 = vproxy.generate("admin")
    assert content2 == "Report content for Test Title"
    assert MetricsTracker.get_count() == 1


def test_protection_proxy_access_control():
    """Unit test for ProtectionReportProxy."""
    assert MetricsTracker.get_count() == 0
    vproxy = VirtualReportProxy("test-id", "Admin Only")
    pproxy = ProtectionReportProxy(underlying_report=vproxy, required_role="admin")
    
    assert pproxy.get_title() == "Admin Only"
    assert MetricsTracker.get_count() == 0

    # Unauthorized attempt raises AccessDeniedException without instantiating heavy subject
    with pytest.raises(AccessDeniedException):
        pproxy.generate("guest")
    assert MetricsTracker.get_count() == 0

    # Authorized attempt succeeds and instantiates heavy subject
    content = pproxy.generate("admin")
    assert content == "Report content for Admin Only"
    assert MetricsTracker.get_count() == 1


def test_concurrent_virtual_proxy_initialization():
    """Verify thread-safety of VirtualReportProxy under concurrent calls."""
    assert MetricsTracker.get_count() == 0
    vproxy = VirtualReportProxy("concurrent-id", "Concurrent Report")

    def run_generate():
        return vproxy.generate("guest")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(run_generate) for _ in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 20
    assert all(r == "Report content for Concurrent Report" for r in results)
    # Exactly one instantiation despite concurrent calls
    assert MetricsTracker.get_count() == 1
