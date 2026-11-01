# Monitoring and observability

This repository includes a lightweight monitoring baseline for a Raspberry Pi deployment. The goal is to make backend health, service status, request trends, and host resource usage visible without requiring a large cloud-native footprint.

## Included stack

- Loki: log aggregation for FastAPI, Nginx, and systemd journal logs
- Promtail: log shipping from host files and journald
- Prometheus: self and host metrics; application metrics only if explicitly
  enabled and configured
- Node Exporter: CPU, memory, and disk metrics
- Grafana: dashboards and alerting surface

The stack is intentionally lightweight and designed for Pi-class hardware. It
is an optional monitoring foundation, not a complete production alerting or
application-metrics solution.

## Run the stack

From the repository root:

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

Verify the services are up:

```bash
docker compose -f docker-compose.monitoring.yml ps
```

Then open:

- Grafana: http://127.0.0.1:3000
- Prometheus: http://127.0.0.1:9090
- Loki readiness: http://127.0.0.1:3100/ready

The Compose file publishes these ports on all host interfaces. Restrict access
with a host firewall or change the port mappings to bind to `127.0.0.1` before
starting the stack on a networked host. Do not expose Grafana, Prometheus, or
Loki publicly. The default Grafana password is `change-me`; set a strong
`GRAFANA_ADMIN_PASSWORD` before starting the stack.

For remote administration, use SSH local forwarding and keep the monitoring
ports firewalled:

```bash
ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 <user>@<pi-host>
```

## Log sources

Promtail is configured to ingest:

- `/var/log/*.log`
- `/var/log/nginx/*.log`
- Linux systemd journal entries

This makes the app logs, Nginx access/error logs, and host-level events searchable in Grafana through Loki.

## Health signal and backend metrics

The FastAPI backend exposes a `/health` endpoint that reports service,
database, and schema state. The health check should remain the first gate
before marking the service healthy in deployment automation.

Prometheus currently scrapes itself and Node Exporter. The backend scrape
configuration is commented out, and the application request-metrics panels in
the dashboard will remain empty until a compatible backend metrics endpoint
and scrape target are implemented and verified. Do not treat those panels as
application monitoring evidence yet.

The `host.docker.internal` host-gateway mapping is available in Compose for an
optional backend scrape target, but it is not enabled by default.

## Grafana dashboard

The provided dashboard is provisioned automatically at startup:

- `monitoring/grafana/dashboards/overview.json`

It currently includes panels for:

- request rate
- error rate
- latency
- CPU utilization
- memory usage
- disk usage

Only the Pi utilization panels are backed by the default Node Exporter scrape.
Request rate, error rate, and latency require backend metrics that are not
currently scraped.

## Alerting

This stack does not include Alertmanager or configured alert rules. A future
hardening step is to add alerting for:

- service down
- high 5xx rate
- disk pressure above 80%
- sustained latency regressions

## Security notes

- change the default Grafana admin password before exposing the port externally
- do not publish Grafana publicly without TLS or a network firewall policy
- keep Pi monitoring on a private network or behind a reverse proxy
- rotate credentials for any external monitoring integrations

## Operational guidance

- Keep the monitoring stack on a dedicated Docker compose file so it is independent from the application service stack.
- For production deployments, prefer a dedicated monitoring network and firewall rules to avoid exposing metrics directly to the internet.
- Confirm the app logs arrive in Loki before treating the stack as ready for production use.
