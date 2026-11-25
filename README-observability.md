# PerfAgent monitoring

PerfAgent's **Run** page shows live test metrics. The project **Dashboard** and **Report** pages show saved results and release comparisons. The **Monitoring** page opens external dashboards. Use the bundled Grafana dashboard to chart PerfAgent traffic, or link an existing service dashboard for CPU, memory, database, and application metrics.

## Start local monitoring

1. Open Docker Desktop. From the repository root, start the stack.

   ```bash
   GRAFANA_ADMIN_PASSWORD='your-local-password' docker compose -f docker-compose.observability.yml up -d
   ```

   Use a password of your choice. Grafana initializes its admin password when its data volume is first created.

2. Keep the local PerfAgent backend running on port 8080. On Docker Desktop for macOS, Prometheus can reach it through `host.docker.internal`.

   ```bash
   uv run uvicorn perfagent.api.app:app --host 127.0.0.1 --port 8080
   ```

3. In PerfAgent, open **Monitoring → Open Grafana live dashboard** and sign in as `admin`. You can also open the dashboard directly. [Grafana Live Run](http://127.0.0.1:3000/d/perfagent-live)
4. Check that the `perfagent` scrape target is **UP**. It should show `host.docker.internal:8080/api/metrics`. The endpoint status inside PerfAgent confirms that the backend responds. The targets page confirms that Prometheus can scrape it. [Prometheus targets](http://127.0.0.1:9090/targets)
5. Run an approved k6 test for about a minute and watch the live charts. Select your environment or leave it on **All**. Local k6 publishes combined traffic across journeys. Prometheus scrapes every five seconds, so a very short run may have few samples.

If the target is **DOWN**, check the backend port and fetch the metrics endpoint from the host. If Grafana opens but charts are empty, check the scrape target, the time range, and whether PerfAgent has run k6 traffic since startup. [Local metrics endpoint](http://localhost:8080/api/metrics)

The bundled **History & Coverage** Grafana dashboard requires a PostgreSQL data source with access to the `run_records` table. The PerfAgent Dashboard and Report already show saved run history with the configured application database.

## Link dashboards and collect service metrics

Use **Open in new tab** for Grafana or Prometheus pages that block framing or require their own sign-in. **Try embedded preview** is available for URLs served with compatible framing and authentication settings.

For report correlation, configure `PERFAGENT_PROMETHEUS_URL` with the approved Prometheus base URL and `PERFAGENT_OBSERVABILITY_TARGET` with the exact test target base URL. Set `PERFAGENT_PROMETHEUS_QUERIES` to a JSON object mapping display labels with units to PromQL expressions. Each expression must return one time series. If needed, set `PERFAGENT_PROMETHEUS_TOKEN` on the backend. Reports compare the two minutes before the run with measurements during the run. Service metrics such as CPU and memory require an instrumented service or host exporter.
