"""Phase 1A observability tests.

Covers liveness/readiness separation, request-id correlation,
metadata-only access logging, unhandled-exception envelopes, and log
redaction of credentials.
"""

import logging
import time
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from app.api.routes import health as health_routes
from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.redaction import RedactingFormatter, redact_text
from app.main import create_app


class BrokenEngine:
    """Engine double whose connection attempt always fails."""

    def connect(self):
        raise RuntimeError("db down at postgresql://user:pass@host/db")


class BlockingEngine:
    """Engine double that blocks long enough to exercise the timeout."""

    def connect(self):
        time.sleep(0.5)
        raise RuntimeError("late readiness failure")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("observability") / "test.db"
    settings = Settings(
        database_url=f"sqlite:///{db_path}",
        environment="test",
        debug=False,
        ai_api_key="test-key",
    )
    return create_app(settings)


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


def test_health_is_liveness_only(client, app, monkeypatch):
    monkeypatch.setattr(app.state, "engine", BrokenEngine())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "service", "version", "environment"}
    assert response.headers["Cache-Control"] == "no-store"


def test_health_supports_head_for_uptime_monitors(client, app, monkeypatch):
    monkeypatch.setattr(app.state, "engine", BrokenEngine())

    response = client.head("/health")

    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["Cache-Control"] == "no-store"
    assert "X-Request-ID" in response.headers


def test_versioned_health_supports_head(client):
    response = client.head("/api/v1/health")

    assert response.status_code == 200
    assert response.content == b""


def test_versioned_health_still_works(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_http_exception_response_keeps_envelope_and_request_id(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert "X-Request-ID" in response.headers
    assert response.json() == {"success": False, "message": "Not Found"}


def test_readiness_reports_ok_when_database_responds(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["Cache-Control"] == "no-store"


def test_readiness_returns_503_when_database_is_unavailable(
    client, app, monkeypatch, caplog
):
    monkeypatch.setattr(app.state, "engine", BrokenEngine())

    with caplog.at_level(logging.WARNING, logger="app.api.routes.health"):
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert "user:pass" not in response.text
    assert "db down" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_readiness_timeout_returns_503_without_details(
    client, app, monkeypatch
):
    monkeypatch.setattr(app.state, "engine", BlockingEngine())
    monkeypatch.setattr(health_routes, "READINESS_TIMEOUT_SECONDS", 0.01)

    started = time.monotonic()
    response = client.get("/ready")
    elapsed = time.monotonic() - started

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert elapsed < 0.2
    assert "late readiness failure" not in response.text
    assert "RuntimeError" not in response.text


def test_request_logging_is_metadata_only(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        response = client.get(
            "/health?token=SUPER_SECRET_QUERY",
            headers={"Authorization": "Bearer AUTH_SECRET_VALUE"},
        )

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    text = caplog.text

    assert "method=GET" in text
    assert "route=/health" in text
    assert "status=200" in text
    assert "duration_ms=" in text
    assert f"request_id={request_id}" in text
    assert "SUPER_SECRET_QUERY" not in text
    assert "AUTH_SECRET_VALUE" not in text
    assert "token=" not in text


def test_request_logging_uses_route_template_for_path_parameters(client, caplog):
    resource_id = "550e8400-e29b-41d4-a716-446655440000"

    with caplog.at_level(logging.INFO, logger="app.request"):
        response = client.get(f"/api/v1/resumes/{resource_id}")

    assert response.status_code == 401
    text = caplog.text
    assert "route=/resumes/{resume_id}" in text
    assert resource_id not in text


def test_request_logging_hides_unmatched_paths(client, caplog):
    resource_id = "550e8400-e29b-41d4-a716-446655440000"

    with caplog.at_level(logging.INFO, logger="app.request"):
        response = client.get(f"/missing/{resource_id}")

    assert response.status_code == 404
    text = caplog.text
    assert "route=<unmatched>" in text
    assert resource_id not in text


@pytest.mark.parametrize("logger_name", ["uvicorn", "uvicorn.access"])
def test_uvicorn_handlers_use_redacting_formatter(logger_name):
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger(logger_name)
    original_handlers = logger.handlers
    original_propagate = logger.propagate
    original_level = logger.level

    try:
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.WARNING)

        configure_logging(Settings(environment="test", debug=False, _env_file=None))
        logger.warning("api_key=uvicorn-secret-value")

        output = stream.getvalue()
        assert len(logger.handlers) == 1
    finally:
        logger.handlers = original_handlers
        logger.propagate = original_propagate
        logger.setLevel(original_level)

    assert "uvicorn-secret-value" not in output
    assert "[REDACTED]" in output
    assert output.count("api_key=") == 1


def test_uvicorn_custom_formatter_fields_are_preserved_and_redacted():
    class LevelPrefixFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            record.levelprefix = "UVICORN"
            return super().format(record)

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        LevelPrefixFormatter("%(levelprefix)s %(message)s")
    )

    logger = logging.getLogger("uvicorn")
    original_handlers = logger.handlers
    original_propagate = logger.propagate
    original_level = logger.level

    try:
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.WARNING)

        configure_logging(Settings(environment="test", debug=False, _env_file=None))
        logger.warning("api_key=uvicorn-levelprefix-secret")

        output = stream.getvalue()
        assert len(logger.handlers) == 1
    finally:
        logger.handlers = original_handlers
        logger.propagate = original_propagate
        logger.setLevel(original_level)

    assert "UVICORN" in output
    assert "uvicorn-levelprefix-secret" not in output
    assert "[REDACTED]" in output


def test_unhandled_exception_is_enveloped_correlated_and_redacted(app, caplog):
    @app.get("/_test/unhandled-secret")
    def unhandled_secret():
        raise RuntimeError(
            "api_key=sk-test-secret-1234567890 "
            "Authorization: Bearer abc.def.ghi"
        )

    local_client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="app.api.errors"):
        response = local_client.get(
            "/_test/unhandled-secret?access_token=QUERY_SECRET"
        )

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "message": "An unexpected error occurred.",
    }
    request_id = response.headers["X-Request-ID"]
    text = caplog.text

    assert f"request_id={request_id}" in text
    assert "status=500" in text
    assert "exc_type=RuntimeError" in text
    assert "sk-test-secret" not in text
    assert "Bearer abc" not in text
    assert "QUERY_SECRET" not in text
    assert "api_key=sk" not in text


def test_unhandled_exception_logs_route_template_not_resource_id(app, caplog):
    @app.get("/_test/unhandled/{resource_id}")
    def unhandled_with_id(resource_id: str):
        raise RuntimeError("unhandled boom")

    resource_id = "550e8400-e29b-41d4-a716-446655440000"
    local_client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="app.api.errors"):
        response = local_client.get(
            f"/_test/unhandled/{resource_id}?access_token=QUERY_SECRET"
        )

    assert response.status_code == 500
    text = caplog.text
    assert "route=/_test/unhandled/{resource_id}" in text
    assert resource_id not in text
    assert "QUERY_SECRET" not in text


def test_unhandled_exception_does_not_log_exception_message(app, caplog):
    @app.get("/_test/unhandled-message")
    def unhandled_message():
        raise RuntimeError("user supplied resume text and private notes")

    local_client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="app.api.errors"):
        response = local_client.get("/_test/unhandled-message")

    assert response.status_code == 500
    text = caplog.text
    assert "exc_type=RuntimeError" in text
    assert "route=/_test/unhandled-message" in text
    assert "user supplied resume text" not in text
    assert "message=" not in text


def test_redact_text_masks_common_secret_shapes():
    raw = (
        "Authorization: Bearer abc.def.ghi "
        "api_key=sk-test-secret-1234567890 "
        "OPENAI_API_KEY=sk-live-abcdefgh "
        "access_token=opaque-token "
        "postgresql://user:pass@db.example.com/app "
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature"
    )

    redacted = redact_text(raw)

    for secret in (
        "abc.def.ghi",
        "sk-test-secret",
        "sk-live-abcdefgh",
        "opaque-token",
        "user:pass",
        "eyJhbGciOiJIUzI1NiJ9",
    ):
        assert secret not in redacted
    assert "[REDACTED]" in redacted


@pytest.mark.parametrize(
    ("raw", "secret"),
    [
        ("openai_api_key=lower-secret-value", "lower-secret-value"),
        ("OpenAI_Api_Key=mixed-case-secret", "mixed-case-secret"),
        ("OPENAI_API_KEY=upper-case-secret", "upper-case-secret"),
        ("sentry_dsn=lower-dsn-secret", "lower-dsn-secret"),
        ("Sentry_Dsn: dsn-colon-secret", "dsn-colon-secret"),
        ("SENTRY_DSN=upper-dsn-secret", "upper-dsn-secret"),
        (
            "SUPABASE_SERVICE_ROLE_KEY=service-role-secret",
            "service-role-secret",
        ),
        (
            "supabase_service_role_key=lower-service-role-secret",
            "lower-service-role-secret",
        ),
        ("AWS_ACCESS_KEY_ID=aws-access-key-secret", "aws-access-key-secret"),
        ("client_secret=client-secret-value", "client-secret-value"),
        ("JWT_SECRET=jwt-secret-value", "jwt-secret-value"),
        ("db_password=db-password-value", "db-password-value"),
        (
            'openai_api_key="quoted secret value"',
            "quoted secret value",
        ),
        ("SENTRY_DSN_URL=https://public@example", "public@example"),
        ("X-API-Key: header-secret", "header-secret"),
        ("api-key=hyphen-secret", "hyphen-secret"),
    ],
)
def test_redact_text_masks_prefixed_and_case_varied_secret_names(raw, secret):
    redacted = redact_text(raw)

    assert secret not in redacted
    assert "[REDACTED]" in redacted


def test_redact_text_leaves_benign_operational_fields_unchanged():
    text = "request_id=abc token_count=42 path=/health status=200"

    assert redact_text(text) == text


def test_redacting_formatter_masks_rendered_arguments():
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="api_key=%s",
        args=("formatter-secret",),
        exc_info=None,
    )

    assert "formatter-secret" not in RedactingFormatter("%(message)s").format(record)
