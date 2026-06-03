# Grafana Alloy Configuration for OpenTelemetry with PHI Detection

This configuration file sets up Grafana Alloy to receive OpenTelemetry data (traces and logs) via gRPC, process them, detect potential PHI/HIPAA data, and forward to Loki.

## Architecture Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Python App     │────▶│  Grafana Alloy  │────▶│     Loki        │
│  (OTLP gRPC)    │     │  (PHI Detection)│     │  (Log Storage)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        │                       ├── 1. Receive OTLP (gRPC :4317)
        │                       ├── 2. Convert traces to logs
        │                       ├── 3. Add service labels
        │                       ├── 4. Batch processing
        │                       ├── 5. Extract log body
        │                       ├── 6. PHI/HIPAA Detection
        │                       └── 7. Send to Loki
        │
        └── Traces + Logs
```

## Pipeline Components

| Step | Component | Description |
|------|-----------|-------------|
| 1 | `otelcol.receiver.otlp` | Receives OTLP data on gRPC port 4317 |
| 2 | `otelcol.connector.spanlogs` | Converts traces/spans into log format |
| 3 | `otelcol.processor.attributes` | Adds service name and Loki labels |
| 4 | `otelcol.processor.batch` | Batches logs for efficient processing |
| 5 | `otelcol.exporter.loki` | Converts OTLP logs to Loki format |
| 6 | `loki.process.extract_body` | Extracts log body and metadata |
| 7 | `loki.process.phi_detector` | **Scans for PHI/HIPAA patterns** |
| 8 | `loki.write` | Sends logs to Loki endpoint |

## PHI/HIPAA Detection

The `phi_detector` stage scans each log line for potential Protected Health Information (PHI) using regex patterns.

### Detected PHI Types

| Type | Pattern | Example |
|------|---------|---------|
| `ssn` | Social Security Number | `123-45-6789` |
| `phone` | US Phone Numbers | `(617) 555-1234`, `617-555-1234`, `617.555.1234` |
| `email` | Email Addresses | `john.doe@hospital.org` |
| `mrn` | Medical Record Number | `MRN: ABC12345`, `Patient ID: 987654` |
| `ip_address` | IPv4 Addresses | `192.168.1.100` |
| `credit_card` | Credit Card Numbers | `4111-1111-1111-1111` |
| `address` | Street Addresses | `123 Main Street`, `456 Oak Avenue` |
| `dob` | Date of Birth | `DOB: 01/15/1985`, `Birthdate: 1985-01-15` |
| `insurance_id` | Insurance/Policy IDs | `Policy# BCBS-987654321` |

### Labels Added

When PHI is detected, the following labels are added to the log entry:

| Label | Value | Description |
|-------|-------|-------------|
| `suspected_phi` | `"true"` or `"false"` | Whether any PHI was detected |
| `phi_types` | `"ssn,email,phone"` | Comma-separated list of ALL detected PHI types |
| `phi_count` | `"3"` | Number of distinct PHI types found in the log |

## Sample Test Log Lines

Use these log messages to test PHI detection. Each line demonstrates a specific pattern:

### Single PHI Type Tests

```python
# SSN - Expected: suspected_phi="true", phi_types="ssn", phi_count="1"
logger.info("Processing patient with SSN 123-45-6789 in system")

# Phone - Expected: phi_types="phone"
logger.info("Contact number updated: (617) 555-1234 for user account")

# Email - Expected: phi_types="email"
logger.info("Notification sent to john.doe@hospital.org successfully")

# MRN - Expected: phi_types="mrn"
logger.info("Looking up MRN: ABC12345678 in medical records")

# IP Address - Expected: phi_types="ip_address"
logger.info("Request received from 192.168.1.100 for patient data")

# Credit Card - Expected: phi_types="credit_card"
logger.info("Payment processed with card 4111-1111-1111-1111")

# Address - Expected: phi_types="address"
logger.info("Patient lives at 123 Main Street in Boston")

# DOB - Expected: phi_types="dob"
logger.info("Patient DOB: 01/15/1985 verified in system")

# Insurance - Expected: phi_types="insurance_id"
logger.info("Insurance Policy# BCBS-987654321 verified")
```

### Multiple PHI Types Tests

```python
# SSN + Email + Phone
# Expected: suspected_phi="true", phi_types="ssn,phone,email", phi_count="3"
logger.warning("Patient SSN 123-45-6789 with email john@hospital.org called from (617) 555-1234")

# MRN + DOB + Address
# Expected: phi_types="mrn,address,dob", phi_count="3"
logger.info("MRN: ABC12345 patient born DOB: 03/22/1970 lives at 456 Oak Avenue")

# All PHI types combined (stress test)
# Expected: phi_count="9"
logger.error("Patient SSN 111-22-3333 MRN: XYZ789 DOB: 01/01/1980 at 789 Pine Street phone (555) 123-4567 email test@test.com IP 10.0.0.1 card 4111-1111-1111-1111 policy BCBS-123456")
```

### Clean Logs (No PHI)

```python
# Expected: suspected_phi="false", phi_types="none", phi_count="0"
logger.info("Application started successfully on port 8080")
logger.debug("Database connection established")
logger.info("User authentication successful")
logger.warning("Cache miss for key: user_preferences")
```

## Grafana Loki Queries

### Basic Queries

```logql
# All logs with suspected PHI
{suspected_phi="true"}

# All clean logs (no PHI)
{suspected_phi="false"}

# Logs with specific PHI type
{phi_types=~".*ssn.*"}
{phi_types=~".*email.*"}
{phi_types=~".*credit_card.*"}
```

### Advanced Queries

```logql
# High-risk logs with multiple PHI types
{suspected_phi="true"} | phi_count > 2

# Logs containing both SSN and email
{phi_types=~".*ssn.*"} | phi_types=~".*email.*"

# Count PHI occurrences by type over time
sum by (phi_types) (count_over_time({suspected_phi="true"}[1h]))

# Filter by service and PHI
{service_name="python-logger-app", suspected_phi="true"}

# Error logs with PHI (critical security concern)
{suspected_phi="true", level="error"}
```

### Dashboard Metrics

```logql
# Total PHI events per hour
sum(count_over_time({suspected_phi="true"}[1h]))

# PHI events by type
sum by (phi_types) (count_over_time({suspected_phi="true"}[24h]))

# Top services leaking PHI
topk(10, sum by (service_name) (count_over_time({suspected_phi="true"}[24h])))
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| Loki URL | `http://loki.dfci.harvard.edu/loki/api/v1/push` | Loki push endpoint |
| gRPC Port | `4317` | OTLP gRPC receiver port |
| HTTP Port | `4318` | OTLP HTTP receiver port |

### OTLP Endpoints

| Protocol | Port | Endpoint |
|----------|------|----------|
| gRPC | 4317 | `grpc://alloy-host:4317` |
| HTTP Traces | 4318 | `http://alloy-host:4318/v1/traces` |
| HTTP Metrics | 4318 | `http://alloy-host:4318/v1/metrics` |
| HTTP Logs | 4318 | `http://alloy-host:4318/v1/logs` |

### Modifying the Configuration

To add new PHI patterns:

1. Add a new `stage.regex` block with a named capture group:
   ```alloy
   stage.regex {
     expression = "(?P<phi_newtype>YOUR_REGEX_PATTERN)"
   }
   ```

2. Update the `phi_types` template to include the new type
3. Update the `phi_count` template to count the new type
4. Update the `suspected_phi` template to check for the new type

## Troubleshooting

### Common Issues

1. **Logs not appearing in Loki**
   - Check Alloy logs: `docker logs alloy`
   - Verify Loki endpoint is reachable
   - Ensure gRPC port 4317 is exposed

2. **PHI not being detected**
   - Verify log format matches regex patterns
   - Check if `stage.output` is extracting the correct field
   - Test regex patterns independently

3. **Configuration errors on startup**
   - Validate Alloy syntax: `alloy fmt config.alloy`
   - Check for typos in component names
   - Ensure all `forward_to` references exist

### Validation Command

```bash
# Check Alloy configuration syntax
alloy fmt --write config.alloy

# Run Alloy with debug logging
alloy run config.alloy --log.level=debug
```

## Security Considerations

- **This is a detection system, not a prevention system** - PHI is still logged
- Consider adding `stage.replace` to redact/mask PHI before sending to Loki
- Implement alerting on `{suspected_phi="true"}` for immediate notification
- Review and tune regex patterns based on your specific data formats
- Regularly audit logs flagged with `suspected_phi="true"`

## Future Enhancements

- [ ] Add PHI redaction/masking stage
- [ ] Implement alerting via Alertmanager
- [ ] Add more PHI patterns (passport, driver's license, etc.)
- [ ] Support for international phone/address formats
- [ ] Machine learning-based name detection
