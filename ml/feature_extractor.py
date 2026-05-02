import requests
import math
from typing import Optional
from config import PROMETHEUS_URL, WINDOW


class FeatureExtractor:

    def __init__(self):
        self.prom = PROMETHEUS_URL

    def query(self, promql: str) -> list:
        try:
            resp = requests.get(
                f"{self.prom}/api/v1/query",
                params={"query": promql},
                timeout=5,
            )
            resp.raise_for_status()
            return resp.json()["data"]["result"]
        except Exception as e:
            print(f"  ! Prometheus query failed: {e}")
            return []

    def get_active_pods(self) -> list[dict]:
        """Returns list of pods currently receiving traffic."""
        result = self.query(
            f'sum by (pod, namespace) '
            f'(rate(http_requests_total{{namespace="balancit"}}[{WINDOW}])) > 0'
        )
        return [
            {
                "pod":       r["metric"].get("pod", "unknown"),
                "namespace": r["metric"].get("namespace", "unknown"),
            }
            for r in result
        ]

    def extract(self, pod: str) -> Optional[dict]:
        """Extract feature vector for one pod."""

        # Total RPS for this pod
        r = self.query(
            f'sum(rate(http_requests_total{{pod="{pod}"}}[{WINDOW}]))'
        )
        rps = float(r[0]["value"][1]) if r else 0.0

        if rps < 0.01:
            return None

        # Error rate (4xx + 5xx)
        r = self.query(
            f'sum(rate(http_requests_total{{pod="{pod}",'
            f'status=~"4..|5.."}}[{WINDOW}]))'
        )
        error_rps = float(r[0]["value"][1]) if r else 0.0
        error_rate = error_rps / max(rps, 0.01)

        # Endpoint distribution → entropy
        r = self.query(
            f'sum by (handler) '
            f'(rate(http_requests_total{{pod="{pod}"}}[{WINDOW}]))'
        )
        if r:
            counts = [float(x["value"][1]) for x in r]
            total = sum(counts)
            if total > 0:
                probs = [c / total for c in counts if c > 0]
                entropy = -sum(p * math.log(p) for p in probs)
            else:
                entropy = 0.0
        else:
            entropy = 0.0

        # p95 latency
        r = self.query(
            f'histogram_quantile(0.95, '
            f'sum by (le) (rate(http_request_duration_seconds_bucket'
            f'{{pod="{pod}"}}[{WINDOW}])))'
        )
        try:
            p95 = float(r[0]["value"][1]) if r else 0.0
            if math.isnan(p95):
                p95 = 0.0
        except (IndexError, ValueError):
            p95 = 0.0

        return {
            "rps":          rps,
            "error_rate":   error_rate,
            "entropy":      entropy,
            "p95_latency":  p95,
        }

    def extract_all(self) -> dict[str, dict]:
        """Extract features for all currently-active pods."""
        pods = self.get_active_pods()
        result = {}
        for pod_info in pods:
            pod = pod_info["pod"]
            features = self.extract(pod)
            if features is not None:
                result[pod] = features
        return result
