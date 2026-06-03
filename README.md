# OpenTelemetry Logger App

A Flask web application that generates logs, metrics, and traces and sends them to an OpenTelemetry Collector. The app provides a UI with buttons to generate different log levels and supports configurable OTEL collector endpoints via gRPC or HTTP protocols.

## Features

- 🔭 **OpenTelemetry Integration**: Full support for logs, metrics, and traces
- 📝 **Log Levels**: Debug, Info, Warning, Error, and Critical log buttons
- 📊 **Traces**: Generate sample distributed traces with parent-child spans
- 📈 **Metrics**: Counter metrics for tracking log events
- ⚙️ **Configurable Endpoint**: Change OTEL collector URL at runtime
- 🔄 **Protocol Support**: gRPC (port 4317) or HTTP (port 4318)
- 🎨 **Modern UI**: Clean, responsive web interface

## Quick Start

### 1. Install Dependencies

```bash
cd d:\python\otel-logger-app
pip install -r requirements.txt
```

### 2. Start an OTEL Collector (Optional)

If you don't have an OTEL collector running, you can use Docker:

```bash
docker-compose up -d
```

Or run the collector manually:

```bash
docker run -d --name otel-collector \
  -p 4317:4317 \
  -p 4318:4318 \
  otel/opentelemetry-collector:latest
```

### 3. Run the Application

```bash
python app.py
```

Or with custom configuration:

```bash
# Using gRPC
set OTEL_ENDPOINT=http://localhost:4317
set OTEL_PROTOCOL=grpc
python app.py

# Using HTTP
set OTEL_ENDPOINT=http://localhost:4318
set OTEL_PROTOCOL=http
python app.py
```

### 4. Open the UI

Navigate to [http://localhost:5000](http://localhost:5000) in your browser.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_ENDPOINT` | `http://localhost:4317` | OTEL Collector endpoint URL |
| `OTEL_PROTOCOL` | `grpc` | Protocol: `grpc` or `http` |
| `SERVICE_NAME` | `otel-logger-app` | Service name for telemetry |

### Runtime Configuration

You can also change the endpoint and protocol through the web UI without restarting the app.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main UI |
| `/config` | GET | Get current configuration |
| `/config` | POST | Update OTEL endpoint configuration |
| `/log/<level>` | POST | Generate log at specified level |
| `/trace` | POST | Generate a sample trace |
| `/metrics` | POST | Generate sample metrics |
| `/health` | GET | Health check endpoint |

### Example API Usage

```bash
# Send an info log
curl -X POST http://localhost:5000/log/info \
  -H "Content-Type: application/json" \
  -d '{"message": "Custom info message"}'

# Generate a trace
curl -X POST http://localhost:5000/trace \
  -H "Content-Type: application/json" \
  -d '{"operation": "my-operation"}'

# Update configuration
curl -X POST http://localhost:5000/config \
  -H "Content-Type: application/json" \
  -d '{"endpoint": "http://my-collector:4317", "protocol": "grpc"}'
```

## OTEL Collector Ports

- **gRPC**: Port `4317` (default)
- **HTTP**: Port `4318`

When using HTTP protocol, the app automatically appends the correct paths:
- Traces: `/v1/traces`
- Metrics: `/v1/metrics`
- Logs: `/v1/logs`

## Project Structure

```
otel-logger-app/
├── app.py                 # Main Flask application
├── templates/
│   └── index.html         # Web UI template
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # OTEL Collector setup
├── otel-collector-config.yaml  # Collector configuration
└── README.md              # This file
```

## Viewing Telemetry Data

### Using Jaeger for Traces

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest
```

Open [http://localhost:16686](http://localhost:16686) to view traces.

### Using Grafana + Loki for Logs

See the docker-compose.yml for a complete observability stack.

## Troubleshooting

### Connection Refused
- Ensure the OTEL collector is running
- Check the endpoint URL and port
- Verify firewall settings

### gRPC vs HTTP
- gRPC is typically faster but requires port 4317
- HTTP is more firewall-friendly and uses port 4318
- Some collectors only support one protocol

### Logs Not Appearing
- Check collector logs: `docker logs otel-collector`
- Verify the collector is configured to receive OTLP data
- Ensure the correct protocol is selected

## License

MIT
