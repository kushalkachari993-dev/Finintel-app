import html
import time
from collections import Counter
from collections import deque
from dataclasses import asdict
from dataclasses import dataclass
from threading import RLock


@dataclass
class RequestTrace:
    request_id: str
    method: str
    path: str
    status_code: int
    duration_ms: float
    timestamp: int
    route: str | None = None
    principal: str | None = None


class ObservabilityRegistry:

    def __init__(
        self,
        max_traces: int = 200
    ):
        self._lock = RLock()
        self.request_count = 0
        self.error_count = 0
        self.timeout_count = 0
        self.total_latency_ms = 0.0
        self.status_counts = Counter()
        self.path_counts = Counter()
        self.route_counts = Counter()
        self.traces = deque(maxlen=max_traces)

    def record_request(
        self,
        trace: RequestTrace
    ):
        with self._lock:
            self.request_count += 1
            self.total_latency_ms += trace.duration_ms
            self.status_counts[str(trace.status_code)] += 1
            self.path_counts[trace.path] += 1

            if trace.status_code >= 500:
                self.error_count += 1

            if trace.status_code == 504:
                self.timeout_count += 1

            if trace.route:
                self.route_counts[trace.route] += 1

            self.traces.appendleft(trace)

    def snapshot(self):
        with self._lock:
            average_latency_ms = (
                self.total_latency_ms / self.request_count
                if self.request_count
                else 0.0
            )
            error_rate = (
                self.error_count / self.request_count
                if self.request_count
                else 0.0
            )

            alerts = []
            if error_rate >= 0.05 and self.request_count >= 10:
                alerts.append(
                    "High backend error rate."
                )
            if average_latency_ms >= 8000 and self.request_count >= 5:
                alerts.append(
                    "High average request latency."
                )
            if self.timeout_count:
                alerts.append(
                    "Provider timeout responses detected."
                )

            return {
                "request_count": self.request_count,
                "error_count": self.error_count,
                "timeout_count": self.timeout_count,
                "average_latency_ms": round(average_latency_ms, 2),
                "error_rate": round(error_rate, 4),
                "status_counts": dict(self.status_counts),
                "path_counts": dict(self.path_counts),
                "route_counts": dict(self.route_counts),
                "alerts": alerts,
                "recent_traces": [
                    asdict(trace)
                    for trace in list(self.traces)[:25]
                ]
            }

    def prometheus_text(self) -> str:
        snapshot = self.snapshot()
        lines = [
            "# HELP finintel_requests_total Total HTTP requests.",
            "# TYPE finintel_requests_total counter",
            f"finintel_requests_total {snapshot['request_count']}",
            "# HELP finintel_errors_total Total 5xx HTTP requests.",
            "# TYPE finintel_errors_total counter",
            f"finintel_errors_total {snapshot['error_count']}",
            "# HELP finintel_timeouts_total Total timeout responses.",
            "# TYPE finintel_timeouts_total counter",
            f"finintel_timeouts_total {snapshot['timeout_count']}",
            "# HELP finintel_average_latency_ms Average request latency.",
            "# TYPE finintel_average_latency_ms gauge",
            f"finintel_average_latency_ms {snapshot['average_latency_ms']}",
        ]

        for status, count in snapshot["status_counts"].items():
            lines.append(
                f'finintel_requests_by_status_total{{status="{status}"}} {count}'
            )

        for route, count in snapshot["route_counts"].items():
            lines.append(
                f'finintel_chat_routes_total{{route="{route}"}} {count}'
            )

        return "\n".join(lines) + "\n"

    def dashboard_html(self) -> str:
        snapshot = self.snapshot()
        alert_markup = "".join(
            f"<li>{html.escape(alert)}</li>"
            for alert in snapshot["alerts"]
        ) or "<li>No active alerts.</li>"
        trace_rows = "".join(
            "<tr>"
            f"<td>{html.escape(trace['timestamp'].__str__())}</td>"
            f"<td>{html.escape(trace['method'])}</td>"
            f"<td>{html.escape(trace['path'])}</td>"
            f"<td>{trace['status_code']}</td>"
            f"<td>{trace['duration_ms']}</td>"
            f"<td>{html.escape(str(trace.get('route') or ''))}</td>"
            f"<td>{html.escape(str(trace.get('principal') or ''))}</td>"
            "</tr>"
            for trace in snapshot["recent_traces"]
        )

        return f"""
        <!doctype html>
        <html>
        <head>
          <title>FinIntel Observability</title>
          <style>
            body {{ font-family: system-ui, sans-serif; margin: 32px; color: #12211c; }}
            .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
            .card {{ border: 1px solid #dfe8e5; border-radius: 8px; padding: 16px; }}
            strong {{ display: block; font-size: 30px; margin-top: 8px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
            th, td {{ border-bottom: 1px solid #dfe8e5; text-align: left; padding: 8px; }}
          </style>
        </head>
        <body>
          <h1>FinIntel Observability</h1>
          <div class="grid">
            <div class="card">Requests<strong>{snapshot['request_count']}</strong></div>
            <div class="card">Errors<strong>{snapshot['error_count']}</strong></div>
            <div class="card">Timeouts<strong>{snapshot['timeout_count']}</strong></div>
            <div class="card">Avg latency<strong>{snapshot['average_latency_ms']} ms</strong></div>
          </div>
          <h2>Alerts</h2>
          <ul>{alert_markup}</ul>
          <h2>Recent Traces</h2>
          <table>
            <thead>
              <tr><th>Time</th><th>Method</th><th>Path</th><th>Status</th><th>ms</th><th>Route</th><th>Principal</th></tr>
            </thead>
            <tbody>{trace_rows}</tbody>
          </table>
        </body>
        </html>
        """


observability = ObservabilityRegistry()
