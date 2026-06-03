"""
Flask application with OpenTelemetry integration for logs, metrics, and traces.
Supports sending telemetry data to OTEL collector via gRPC or HTTP.
"""

import os
import logging
from flask import Flask, render_template, jsonify, request
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as GrpcMetricExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter as GrpcLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as HttpMetricExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter as HttpLogExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor


# Configuration from environment variables
# Default endpoint points to Grafana Alloy server
OTEL_ENDPOINT = os.getenv("OTEL_ENDPOINT", "http://10.112.82.249:4317")
OTEL_PROTOCOL = os.getenv("OTEL_PROTOCOL", "grpc")  # grpc or http
SERVICE_NAME_VALUE = os.getenv("SERVICE_NAME", "otel-logger-app")

# Current configuration (can be updated at runtime)
current_config = {
    "endpoint": OTEL_ENDPOINT,
    "protocol": OTEL_PROTOCOL
}

# Create resource
resource = Resource.create({SERVICE_NAME: SERVICE_NAME_VALUE})

# Initialize providers (will be set up in setup_telemetry)
tracer_provider = None
meter_provider = None
logger_provider = None
tracer = None
meter = None
otel_logger = None
log_counter = None


def get_exporters(endpoint, protocol):
    """Get exporters based on protocol type."""
    if protocol.lower() == "http":
        # HTTP endpoints typically use different ports/paths
        traces_endpoint = f"{endpoint}/v1/traces"
        metrics_endpoint = f"{endpoint}/v1/metrics"
        logs_endpoint = f"{endpoint}/v1/logs"
        
        return {
            "trace": HttpSpanExporter(endpoint=traces_endpoint),
            "metric": HttpMetricExporter(endpoint=metrics_endpoint),
            "log": HttpLogExporter(endpoint=logs_endpoint)
        }
    else:  # grpc
        return {
            "trace": GrpcSpanExporter(endpoint=endpoint, insecure=True),
            "metric": GrpcMetricExporter(endpoint=endpoint, insecure=True),
            "log": GrpcLogExporter(endpoint=endpoint, insecure=True)
        }


def setup_telemetry(endpoint=None, protocol=None):
    """Setup OpenTelemetry with the specified endpoint and protocol."""
    global tracer_provider, meter_provider, logger_provider
    global tracer, meter, otel_logger, log_counter, current_config
    
    if endpoint:
        current_config["endpoint"] = endpoint
    if protocol:
        current_config["protocol"] = protocol
    
    # Get exporters
    exporters = get_exporters(current_config["endpoint"], current_config["protocol"])
    
    # Setup Tracer Provider
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(exporters["trace"]))
    trace.set_tracer_provider(tracer_provider)
    tracer = trace.get_tracer(__name__)
    
    # Setup Meter Provider
    metric_reader = PeriodicExportingMetricReader(exporters["metric"], export_interval_millis=5000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter(__name__)
    
    # Create metrics
    log_counter = meter.create_counter(
        name="log_events",
        description="Count of log events by level",
        unit="1"
    )
    
    # Setup Logger Provider
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporters["log"]))
    
    # Setup Python logging to use OTEL
    handler = LoggingHandler(level=logging.DEBUG, logger_provider=logger_provider)
    otel_logger = logging.getLogger("otel-app")
    otel_logger.setLevel(logging.DEBUG)
    otel_logger.addHandler(handler)
    
    return True


# Initial setup
setup_telemetry()

# Create Flask app
app = Flask(__name__)

# Instrument Flask with OpenTelemetry
FlaskInstrumentor().instrument_app(app)


@app.route("/")
def index():
    """Render the main UI."""
    return render_template("index.html", config=current_config)


@app.route("/config", methods=["GET", "POST"])
def config():
    """Get or update OTEL configuration."""
    if request.method == "POST":
        data = request.get_json()
        endpoint = data.get("endpoint", current_config["endpoint"])
        protocol = data.get("protocol", current_config["protocol"])
        
        try:
            setup_telemetry(endpoint, protocol)
            return jsonify({
                "success": True,
                "message": "Configuration updated successfully",
                "config": current_config
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 500
    else:
        return jsonify(current_config)


@app.route("/log/<level>", methods=["POST"])
def log_message(level):
    """Generate a log message at the specified level."""
    data = request.get_json() or {}
    message = data.get("message", f"Sample {level.upper()} log message")
    
    # Create a span for the log event
    with tracer.start_as_current_span(f"log-{level}") as span:
        span.set_attribute("log.level", level)
        span.set_attribute("log.message", message)
        span.set_attribute("telemetry_type", "trace")  # Label for trace
        
        # Log at the appropriate level with telemetry_type label
        log_extra = {"telemetry_type": "log", "level": level}
        if level == "debug":
            otel_logger.debug(message, extra=log_extra)
        elif level == "info":
            otel_logger.info(message, extra=log_extra)
        elif level == "warning":
            otel_logger.warning(message, extra=log_extra)
        elif level == "error":
            otel_logger.error(message, extra=log_extra)
        elif level == "critical":
            otel_logger.critical(message, extra=log_extra)
        else:
            return jsonify({"error": "Invalid log level"}), 400
        
        # Increment metric counter with telemetry_type label
        log_counter.add(1, {"level": level, "telemetry_type": "metrics"})
        
        span.add_event(f"Log recorded: {level}")
    
    return jsonify({
        "success": True,
        "level": level,
        "message": message,
        "endpoint": current_config["endpoint"],
        "protocol": current_config["protocol"]
    })


@app.route("/trace", methods=["POST"])
def generate_trace():
    """Generate a sample trace with multiple spans."""
    data = request.get_json() or {}
    operation = data.get("operation", "sample-operation")
    
    with tracer.start_as_current_span("parent-operation") as parent_span:
        parent_span.set_attribute("operation.name", operation)
        parent_span.set_attribute("operation.type", "manual")
        parent_span.set_attribute("telemetry_type", "trace")  # Label for trace
        
        # Create child spans
        with tracer.start_as_current_span("child-operation-1") as child1:
            child1.set_attribute("step", 1)
            child1.set_attribute("telemetry_type", "trace")
            child1.add_event("Processing step 1")
            otel_logger.info(f"Trace operation: {operation} - Step 1", extra={"telemetry_type": "log"})
        
        with tracer.start_as_current_span("child-operation-2") as child2:
            child2.set_attribute("step", 2)
            child2.set_attribute("telemetry_type", "trace")
            child2.add_event("Processing step 2")
            otel_logger.info(f"Trace operation: {operation} - Step 2", extra={"telemetry_type": "log"})
        
        parent_span.add_event("All operations completed")
    
    return jsonify({
        "success": True,
        "operation": operation,
        "message": "Trace generated successfully"
    })


@app.route("/metrics", methods=["POST"])
def generate_metrics():
    """Generate sample metrics."""
    data = request.get_json() or {}
    metric_name = data.get("name", "sample_metric")
    value = data.get("value", 1)
    
    with tracer.start_as_current_span("generate-metric") as span:
        span.set_attribute("metric.name", metric_name)
        span.set_attribute("metric.value", value)
        span.set_attribute("telemetry_type", "trace")  # Span is still a trace
        
        # Record metric with telemetry_type label
        log_counter.add(value, {"metric_name": metric_name, "type": "custom", "telemetry_type": "metrics"})
        otel_logger.info(f"Metric recorded: {metric_name} = {value}", extra={"telemetry_type": "log"})
    
    return jsonify({
        "success": True,
        "metric": metric_name,
        "value": value
    })


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": SERVICE_NAME_VALUE,
        "otel_config": current_config
    })


if __name__ == "__main__":
    print(f"Starting OTEL Logger App...")
    print(f"OTEL Endpoint: {current_config['endpoint']}")
    print(f"OTEL Protocol: {current_config['protocol']}")
    app.run(host="0.0.0.0", port=5000, debug=True)
