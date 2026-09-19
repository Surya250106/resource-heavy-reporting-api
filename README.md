# Resource-Heavy Reporting REST API (Proxy Pattern)

A clean, production-grade Python Flask REST API demonstrating the **Proxy Design Pattern** through layered **Virtual Proxy** (lazy loading & caching) and **Protection Proxy** (role-based access control) implementations.

---

## 1. Project Overview

This service provides an API for generating resource-intensive reports. In a real-world system, reports may require heavy computational power, large database queries, or extensive memory allocation. 

Using the Proxy Design Pattern:
- **Startup is instantaneous**: Heavy report generation objects are **never** instantiated during application startup or when simply listing report metadata.
- **Access is strictly guarded**: Unauthorized users are blocked before any expensive resource is instantiated or executed.
- **Instantiation is lazy and cached**: An expensive report generator is constructed only upon its first authorized generation request, and the instance is cached for all subsequent calls.

---

## 2. Technology Stack

- **Python 3.12**
- **Flask** (REST API framework)
- **pytest** (Automated unit & integration testing)
- **Docker & Docker Compose** (Containerization & health monitoring)
- **Port**: `8080` (bound to `0.0.0.0`)

---

## 3. Project Structure

```
resource-heavy-reporting-api/
├── src/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── server.py                  # Flask API controllers & application factory
│   ├── core/
│   │   ├── __init__.py
│   │   ├── report.py                  # Report interface / Abstract Base Class
│   │   ├── metrics_tracker.py         # Thread-safe instantiation metric tracker
│   │   └── heavy_report_generator.py  # Real Subject (expensive resource)
│   └── proxies/
│       ├── __init__.py
│       ├── virtual_report_proxy.py    # Virtual Proxy (lazy loading & caching)
│       └── protection_report_proxy.py # Protection Proxy (role access control)
│
├── tests/
│   ├── __init__.py
│   └── test_api.py                    # Comprehensive pytest test suite
│
├── Dockerfile                         # Container build definition
├── docker-compose.yml                 # Multi-container orchestration & healthcheck
├── requirements.txt                   # Production & test dependencies
├── .env.example                       # Example environment configuration
├── .gitignore                         # Git ignore rules
└── README.md                          # Documentation
```

---

## 4. Proxy Architecture

Both proxies and the real subject implement the common `Report` interface (`get_title()` and `generate(user_role)`). Client code (the API controller) interacts strictly with the `Report` abstraction.

```
API / Controller
       |
       v
ProtectionReportProxy   (Checks user role & enforces access control)
       |
       v
VirtualReportProxy      (Delays creation until needed & caches instance)
       |
       v
HeavyReportGenerator    (Real Subject: Expensive computation & instantiation)
```

### Seeded Report Database

At application startup, exactly three reports are initialized using proxies:

| Report ID | Title | Required Role |
| :--- | :--- | :--- |
| `report-1` | Financial Q1 | `admin` |
| `report-2` | User Analytics | `manager` |
| `report-3` | System Status | `guest` |

> [!IMPORTANT]
> `HeavyReportGenerator` is **never** instantiated during application startup. Only the lightweight `ProtectionReportProxy` wrapping `VirtualReportProxy` objects are registered in the in-memory database.

---

## 5. Virtual Proxy vs. Protection Proxy

| Proxy Type | Responsibility | Implementation in this Project |
| :--- | :--- | :--- |
| **Virtual Proxy** | **Resource Optimization**: Postpones creation of expensive objects until strictly necessary and caches the reference. | `VirtualReportProxy` maintains `_real_subject = None`. It initializes `HeavyReportGenerator` only upon the first `generate()` call and reuses it on subsequent calls. |
| **Protection Proxy** | **Security & Access Control**: Verifies caller permissions before allowing access to the underlying target. | `ProtectionReportProxy` verifies that `user_role` matches `required_role`. It raises `AccessDeniedException` if unauthorized, preventing downstream execution. |

---

## 6. Why Protection Proxy Wraps Virtual Proxy

In our layered architecture:
```
ProtectionReportProxy -> VirtualReportProxy -> HeavyReportGenerator
```

Wrapping `VirtualReportProxy` with `ProtectionReportProxy` guarantees that **permission verification occurs before lazy loading**:
- If an unauthorized request arrives (e.g., `role=guest` for `report-1`), `ProtectionReportProxy` denies the request immediately (HTTP 403).
- Because the call is rejected before reaching `VirtualReportProxy.generate()`, **no `HeavyReportGenerator` is instantiated**.
- This prevents denial-of-service / resource exhaustion attacks where unauthorized clients attempt to trigger expensive background computations.

---

## 7. How Lazy Initialization Works

1. When `VirtualReportProxy` is created, `self._real_subject` is set to `None`.
2. Calling metadata methods such as `get_title()` returns cached metadata directly without creating `_real_subject`.
3. When `generate(user_role)` is called:
   - It checks whether `self._real_subject is None`.
   - If `None`, it enters a thread-safe critical section (`with self._lock:` double-checked locking) and instantiates `HeavyReportGenerator(self.report_id, self.title)`.
   - `self._real_subject` is stored in the proxy.
   - On all future calls, the existing `_real_subject` is reused without constructing new instances.

---

## 8. Proving Lazy Initialization with MetricsTracker

The `MetricsTracker` class maintains a global, thread-safe counter of `HeavyReportGenerator` instantiations.

- **Crucial Rule**: The counter increment (`MetricsTracker.increment()`) is placed **exclusively inside the `HeavyReportGenerator.__init__` constructor**.
- Proxies **do not** touch or increment this counter directly.
- Therefore:
  - Startup: metric is `0`.
  - Listing reports (`GET /api/reports`): metric remains `0`.
  - Unauthorized calls (`GET /api/reports/report-1/generate?role=guest`): metric remains `0`.
  - First authorized call (`GET /api/reports/report-3/generate?role=guest`): metric becomes `1`.
  - Repeated calls to `report-3`: metric remains `1`.
  - First authorized call to `report-1`: metric becomes `2`.

---

## 9. Running with Docker Compose

To build and start the service in detached mode:

```bash
docker-compose up -d --build
```

To view logs:
```bash
docker-compose logs -f
```

To stop the service:
```bash
docker-compose down
```

---

## 10. API Endpoints

| Method | Endpoint | Query Params | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | None | Health check endpoint for Docker & load balancers. |
| `GET` | `/api/metrics` | None | Returns total `HeavyReportGenerator` instantiations. |
| `POST` | `/api/metrics/reset` | None | Resets instantiation metric to 0. |
| `GET` | `/api/reports` | None | Lists available reports with metadata. |
| `GET` | `/api/reports/<id>/generate` | `role` (required) | Generates report content if authorized. |

---

## 11. Example cURL Commands

### Health Check
```bash
curl -i http://localhost:8080/health
```

### Get Current Metrics
```bash
curl -i http://localhost:8080/api/metrics
```

### List Reports (Metadata only - zero instantiations)
```bash
curl -i http://localhost:8080/api/reports
```

### Generate Report 3 (Authorized as guest -> instantiates report-3)
```bash
curl -i "http://localhost:8080/api/reports/report-3/generate?role=guest"
```

### Generate Report 1 (Unauthorized as guest -> returns 403, 0 new instantiations)
```bash
curl -i "http://localhost:8080/api/reports/report-1/generate?role=guest"
```

### Generate Report 1 (Authorized as admin -> returns 200, instantiates report-1)
```bash
curl -i "http://localhost:8080/api/reports/report-1/generate?role=admin"
```

### Reset Metrics Counter
```bash
curl -i -X POST http://localhost:8080/api/metrics/reset
```

### Missing Role Parameter (HTTP 400)
```bash
curl -i "http://localhost:8080/api/reports/report-1/generate"
```

### Non-Existent Report (HTTP 404)
```bash
curl -i "http://localhost:8080/api/reports/unknown-report/generate?role=admin"
```

---

## 12. Running Automated Tests

Run the full pytest suite with verbose output:

```bash
pytest -v
```

Or run quietly:
```bash
pytest -q
```

---

## 13. Expected Metrics Lifecycle

```
[Start Application]                       -> /api/metrics => {"total_instantiations": 0}
[GET /api/reports]                        -> /api/metrics => {"total_instantiations": 0}
[GET /api/reports/report-3 (role=guest)]  -> /api/metrics => {"total_instantiations": 1}
[GET /api/reports/report-3 (role=guest)]  -> /api/metrics => {"total_instantiations": 1}
[GET /api/reports/report-1 (role=guest)]  -> 403 Forbidden
                                          -> /api/metrics => {"total_instantiations": 1}
[GET /api/reports/report-1 (role=admin)]  -> /api/metrics => {"total_instantiations": 2}
[POST /api/metrics/reset]                 -> /api/metrics => {"total_instantiations": 0}
```

---

## 14. Health Check

The service includes a built-in `/health` endpoint that returns:
```json
{
  "status": "ok"
}
```
This endpoint is actively monitored by `docker-compose.yml` with a 10-second interval.
