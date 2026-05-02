import os

# Prometheus
PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://prometheus-kube-prometheus-prometheus.monitoring:9090"
)

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "redis.balancit")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Loop timing
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "5"))
WINDOW           = os.getenv("WINDOW", "30s")

# Defaults (used in later days)
DEFAULT_RATE_LIMIT = float(os.getenv("DEFAULT_RATE_LIMIT", "100"))
