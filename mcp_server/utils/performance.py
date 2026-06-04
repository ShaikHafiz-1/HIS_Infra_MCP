"""
Performance monitoring for MCP tool execution.

Tracks per-tool call counts, error rates, response times (including p95),
and exposes Prometheus-compatible metrics text.
"""

import threading
from bisect import insort
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)

# Response-time SLAs per tool (milliseconds)
_SLOW_THRESHOLDS: Dict[str, float] = {
    "get_care_unit_summary": 500.0,
    "default": 2000.0,
}
_MAX_RESPONSE_HISTORY = 1000  # per tool
_MAX_SLOW_QUERY_HISTORY = 50


@dataclass
class ToolMetrics:
    tool_name: str
    total_calls: int = 0
    total_errors: int = 0
    total_response_time_ms: float = 0.0
    min_response_time_ms: Optional[float] = None
    max_response_time_ms: Optional[float] = None
    _response_times: List[float] = field(default_factory=list, repr=False)

    @property
    def avg_response_time_ms(self) -> Optional[float]:
        if self.total_calls == 0:
            return None
        return self.total_response_time_ms / self.total_calls

    @property
    def error_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_errors / self.total_calls

    @property
    def p95_response_time_ms(self) -> Optional[float]:
        if not self._response_times:
            return None
        idx = int(len(self._response_times) * 0.95)
        idx = min(idx, len(self._response_times) - 1)
        return self._response_times[idx]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "total_calls": self.total_calls,
            "total_errors": self.total_errors,
            "error_rate": round(self.error_rate, 4),
            "avg_response_time_ms": round(self.avg_response_time_ms, 2) if self.avg_response_time_ms else None,
            "min_response_time_ms": round(self.min_response_time_ms, 2) if self.min_response_time_ms else None,
            "max_response_time_ms": round(self.max_response_time_ms, 2) if self.max_response_time_ms else None,
            "p95_response_time_ms": round(self.p95_response_time_ms, 2) if self.p95_response_time_ms else None,
        }


class PerformanceMonitor:
    """Thread-safe performance monitor for MCP tool invocations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._metrics: Dict[str, ToolMetrics] = {}
        self._slow_queries: deque = deque(maxlen=_MAX_SLOW_QUERY_HISTORY)

    def record_tool_call(
        self,
        tool_name: str,
        response_time_ms: float,
        success: bool,
    ) -> None:
        """Record a completed tool call."""
        with self._lock:
            if tool_name not in self._metrics:
                self._metrics[tool_name] = ToolMetrics(tool_name=tool_name)

            m = self._metrics[tool_name]
            m.total_calls += 1
            if not success:
                m.total_errors += 1
            m.total_response_time_ms += response_time_ms

            if m.min_response_time_ms is None or response_time_ms < m.min_response_time_ms:
                m.min_response_time_ms = response_time_ms
            if m.max_response_time_ms is None or response_time_ms > m.max_response_time_ms:
                m.max_response_time_ms = response_time_ms

            # Keep sorted response time list for percentile calculation
            if len(m._response_times) >= _MAX_RESPONSE_HISTORY:
                m._response_times.pop(0)
            insort(m._response_times, response_time_ms)

            # Detect slow queries
            threshold = _SLOW_THRESHOLDS.get(tool_name, _SLOW_THRESHOLDS["default"])
            if response_time_ms > threshold:
                self._slow_queries.append({
                    "tool_name": tool_name,
                    "response_time_ms": round(response_time_ms, 2),
                    "threshold_ms": threshold,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                logger.warning(
                    f"Slow query: {tool_name} took {response_time_ms:.0f}ms "
                    f"(threshold: {threshold:.0f}ms)"
                )

    def get_tool_metrics(self, tool_name: str) -> ToolMetrics:
        with self._lock:
            return self._metrics.get(tool_name, ToolMetrics(tool_name=tool_name))

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {name: m.to_dict() for name, m in self._metrics.items()}

    def get_prometheus_metrics(self) -> str:
        """Return metrics in Prometheus text exposition format."""
        lines = []
        with self._lock:
            for name, m in self._metrics.items():
                safe = name.replace("-", "_")
                lines.append(f"# HELP mcp_{safe}_calls_total Total calls to {name}")
                lines.append(f"# TYPE mcp_{safe}_calls_total counter")
                lines.append(f'mcp_{safe}_calls_total{{tool="{name}"}} {m.total_calls}')

                lines.append(f"# HELP mcp_{safe}_errors_total Total errors in {name}")
                lines.append(f"# TYPE mcp_{safe}_errors_total counter")
                lines.append(f'mcp_{safe}_errors_total{{tool="{name}"}} {m.total_errors}')

                if m.avg_response_time_ms is not None:
                    lines.append(f"# HELP mcp_{safe}_response_ms Average response time ms")
                    lines.append(f"# TYPE mcp_{safe}_response_ms gauge")
                    lines.append(
                        f'mcp_{safe}_response_ms{{tool="{name}",quantile="avg"}} '
                        f"{m.avg_response_time_ms:.2f}"
                    )
                if m.p95_response_time_ms is not None:
                    lines.append(
                        f'mcp_{safe}_response_ms{{tool="{name}",quantile="0.95"}} '
                        f"{m.p95_response_time_ms:.2f}"
                    )
                lines.append("")

        return "\n".join(lines)

    def is_slow_query(self, tool_name: str, response_time_ms: float) -> bool:
        threshold = _SLOW_THRESHOLDS.get(tool_name, _SLOW_THRESHOLDS["default"])
        return response_time_ms > threshold

    def get_slow_query_report(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._slow_queries)


# Global singleton
performance_monitor = PerformanceMonitor()
