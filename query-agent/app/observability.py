from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def create_langfuse_handler():
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse.callback import CallbackHandler

        handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            tags=["file-qa", "openai-compat"],
        )
        logger.info("Langfuse callback handler created")
        return handler
    except Exception as exc:
        logger.warning("Langfuse handler setup failed: %s", exc)
        return None


def setup_observability(app) -> None:
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            handler = create_langfuse_handler()
            if handler:
                app.state.langfuse_handler = handler
                logger.info("Langfuse tracing enabled")
        except Exception as exc:
            logger.warning("Langfuse setup failed: %s", exc)

    if settings.otel_exporter_otlp_endpoint:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": settings.otel_service_name})
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
            )
            trace.set_tracer_provider(provider)
            FastAPIInstrumentor.instrument_app(app)
            HTTPXClientInstrumentor().instrument()
            logger.info("OpenTelemetry tracing enabled")
        except Exception as exc:
            logger.warning("OTEL setup failed: %s", exc)
