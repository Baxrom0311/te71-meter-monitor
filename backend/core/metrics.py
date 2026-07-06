from collections import defaultdict

REQUEST_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

_request_total: dict[tuple[str, str, str], int] = defaultdict(int)
_request_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
_request_duration_count: dict[tuple[str, str], int] = defaultdict(int)
_request_duration_buckets: dict[tuple[str, str, float], int] = defaultdict(int)


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def observe_http_request(method: str, route: str, status_code: int, elapsed_seconds: float) -> None:
    if route == "/metrics":
        return
    method = method.upper()
    status = str(status_code)
    _request_total[(method, route, status)] += 1
    _request_duration_sum[(method, route)] += elapsed_seconds
    _request_duration_count[(method, route)] += 1
    for bucket in REQUEST_DURATION_BUCKETS:
        if elapsed_seconds <= bucket:
            _request_duration_buckets[(method, route, bucket)] += 1


def render_http_metrics() -> list[str]:
    lines = [
        "# HELP meter_monitor_http_requests_total Total HTTP requests.",
        "# TYPE meter_monitor_http_requests_total counter",
    ]
    for method, route, status in sorted(_request_total):
        value = _request_total[(method, route, status)]
        lines.append(
            f'meter_monitor_http_requests_total{{method="{_label(method)}",route="{_label(route)}",status="{_label(status)}"}} {value}'
        )

    lines.extend(
        [
            "# HELP meter_monitor_http_request_duration_seconds HTTP request latency.",
            "# TYPE meter_monitor_http_request_duration_seconds histogram",
        ]
    )
    for method, route in sorted(_request_duration_count):
        for bucket in REQUEST_DURATION_BUCKETS:
            value = _request_duration_buckets[(method, route, bucket)]
            lines.append(
                f'meter_monitor_http_request_duration_seconds_bucket{{method="{_label(method)}",route="{_label(route)}",le="{bucket:g}"}} {value}'
            )
        count = _request_duration_count[(method, route)]
        total = _request_duration_sum[(method, route)]
        lines.append(
            f'meter_monitor_http_request_duration_seconds_bucket{{method="{_label(method)}",route="{_label(route)}",le="+Inf"}} {count}'
        )
        lines.append(
            f'meter_monitor_http_request_duration_seconds_count{{method="{_label(method)}",route="{_label(route)}"}} {count}'
        )
        lines.append(
            f'meter_monitor_http_request_duration_seconds_sum{{method="{_label(method)}",route="{_label(route)}"}} {total:.6f}'
        )
    return lines


def reset_http_metrics() -> None:
    _request_total.clear()
    _request_duration_sum.clear()
    _request_duration_count.clear()
    _request_duration_buckets.clear()
