# Monitoring and observability

This repository includes a lightweight monitoring baseline for a Raspberry Pi deployment. The goal is to make backend health, service status, request trends, and host resource usage visible without requiring a large cloud-native footprint.

## Included stack

- Loki: log aggregation for FastAPI, Nginx, and systemd journal logs
- Promtail: log shipping from host files and journald
- Prometheus: metrics collection for app and host-level signals
- Node Exporter: CPU, memory, and disk metrics
- Grafana: dashboards and alerting surface

The stack is intentionally lightweight and designed for Pi-class hardware. It is meant as a production baseline, not as a full Kubernetes-style observability platform.

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

- Grafana: http://<pi-host>:3000
- Prometheus: http://<pi-host>:9090
- Loki: http://<pi-host>:3100/ready

Default Grafana credentials are `admin / change-me` unless overridden with `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD` in the shell environment.

## Log sources

Promtail is configured to ingest:

- `/var/log/*.log`
- `/var/log/nginx/*.log`
- Linux systemd journal entries

This makes the app logs, Nginx access/error logs, and host-level events searchable in Grafana through Loki.

## Health signal and backend metrics

The FastAPI backend exposes a `/health` endpoint that reports service, database, and schema state. The health check should remain the first gate before marking the service healthy in deployment automation.

If your backend exposes Prometheus metrics, update the scrape target in `monitoring/prometheus.yml` to match the service host and port.

The default target is `host.docker.internal:8000`, which works with the included `host-gateway` mapping and is the easiest way to monitor a locally running backend on the same machine.

## Grafana dashboard

The provided dashboard is provisioned automatically at startup:

- `monitoring/grafana/dashboards/overview.json`

It includes panels for:

- request rate
- error rate
- latency
- CPU utilization
- memory usage
- disk usage

## Alerting

This baseline does not include a full alertmanager deployment yet. The next hardening step is to add Prometheus Alertmanager rules for:

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
