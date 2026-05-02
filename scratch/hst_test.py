# scratch/hst_test.py

from river.anomaly import HalfSpaceTrees
import random
import numpy as np

# Model
hst = HalfSpaceTrees(
    n_trees=25,
    height=15,
    window_size=250,
    seed=42,
    limits={
        "rps":           (0, 150000),
        "error_rate":    (0, 1),
        "entropy":       (0, 3),
        "traffic_ratio": (0, 1),
    }
)

# Traffic profiles

def normal_client() -> dict:
    # 50 clients × ~200-300 req/s = 10k-15k total
    return {
        "rps":           random.gauss(250, 30),
        "error_rate":    random.gauss(0.02, 0.004),
        "entropy":       random.gauss(1.8, 0.15),
        "traffic_ratio": random.gauss(0.013, 0.002),  # ~1.3% of 20k
    }

def peak_client() -> dict:
    # same clients, pushing harder — ~400 req/s each, ~20k total
    return {
        "rps":           random.gauss(400, 40),
        "error_rate":    random.gauss(0.025, 0.005),   # slightly more errors, still low
        "entropy":       random.gauss(1.75, 0.15),     # still varied endpoints
        "traffic_ratio": random.gauss(0.020, 0.002),   # ~2% of 20k
    }

def ddos_client() -> dict:
    # one client, 80k+ req/s = 4x normal total capacity
    return {
        "rps":           random.gauss(85000, 3000),
        "error_rate":    random.gauss(0.88, 0.04),     # hammering blindly
        "entropy":       random.gauss(0.04, 0.01),     # one endpoint
        "traffic_ratio": random.gauss(0.92, 0.03),     # dominates all traffic
    }

# Core
def observe(x: dict) -> float:
    s = hst.score_one(x)
    hst.learn_one(x)
    return s

def section(title: str):
    print(f"\n{'─'*68}\n  {title}\n{'─'*68}")

# Phase 1: Warmup
section("PHASE 1 — Warmup  (20k samples | 70% normal, 30% peak)")

for i in range(20000):
    x = normal_client() if random.random() < 0.70 else peak_client()
    observe(x)
    if (i + 1) % 5000 == 0:
        print(f"  {i+1:>6} / 20000 samples...")

print("  Done.")

# Phase 2: Calibrate thresholds
section("PHASE 2 — Calibrating thresholds from legitimate traffic")

cal_scores = []
for _ in range(1000):
    x = normal_client() if random.random() < 0.70 else peak_client()
    cal_scores.append(observe(x))

p50 = np.percentile(cal_scores, 50)
p90 = np.percentile(cal_scores, 90)
p99 = np.percentile(cal_scores, 99)

print(f"  Legitimate traffic score distribution:")
print(f"    min = {min(cal_scores):.6f}")
print(f"    p50 = {p50:.6f}")
print(f"    p90 = {p90:.6f}  ← suspicious threshold")
print(f"    p99 = {p99:.6f}  ← anomaly threshold")
print(f"    max = {max(cal_scores):.6f}")

def classify(s: float) -> str:
    if s < p90:   return "GENUINE    ✓"
    elif s < p99: return "SUSPICIOUS ?"
    else:         return "ANOMALY    ✗"

def print_row(i: int, label: str, x: dict, s: float):
    print(
        f"  {i:<4} {label:<28} "
        f"rps={x['rps']:<9.0f} "
        f"err={x['error_rate']:.3f}  "
        f"ent={x['entropy']:.2f}  "
        f"score={s:.6f}  {classify(s)}"
    )

# Phase 3: Normal traffic (10k–15k total)
section("PHASE 3 — Normal traffic  (10k–15k total | ~250 req/s per client)")
print("  Expected: GENUINE\n")

normal_scores = []
for i in range(15):
    x = normal_client()
    s = observe(x)
    normal_scores.append(s)
    print_row(i, "Normal", x, s)

# Phase 4: Peak hour (~20k total)
section("PHASE 4 — Peak hour  (~20k total | ~400 req/s per client)")
print("  High RPS but behaving normally. Expected: GENUINE\n")

peak_scores = []
for i in range(15):
    x = peak_client()
    s = observe(x)
    peak_scores.append(s)
    print_row(i, "Peak hour", x, s)

# Phase 5: DDoS (80k+ from one client)
section("PHASE 5 — Single client DDoS  (80k+ req/s | one client)")
print("  One client = 4x total system capacity. Expected: ANOMALY\n")

ddos_scores = []
for i in range(15):
    x = ddos_client()
    s = observe(x)
    ddos_scores.append(s)
    print_row(i, "DDoS", x, s)

# Phase 6: Slow ramp
section("PHASE 6 — Slow ramp attacker  (normal → DDoS over 25 steps)")
print("  Watch score rise as attacker escalates.\n")

ramp_scores = []
rps   = 250.0
err   = 0.02
ent   = 1.80
ratio = 0.013

first_suspicious = None
first_anomaly    = None

for i in range(25):
    rps   = min(rps   * 1.40, 85000)
    err   = min(err   * 1.18, 0.88)
    ent   = max(ent   - 0.08, 0.04)
    ratio = min(ratio * 1.35, 0.92)

    x = {
        "rps":           rps,
        "error_rate":    err,
        "entropy":       ent,
        "traffic_ratio": ratio,
    }
    s = observe(x)
    ramp_scores.append(s)
    print_row(i, "Slow ramp", x, s)

    if first_suspicious is None and s >= p90:
        first_suspicious = i
    if first_anomaly is None and s >= p99:
        first_anomaly = i

# Summary
section("RESULTS SUMMARY")

avg_normal = np.mean(normal_scores)
avg_peak   = np.mean(peak_scores)
avg_ddos   = np.mean(ddos_scores)
separation = avg_ddos - max(avg_normal, avg_peak)

genuine_correct_normal = sum(1 for s in normal_scores if s < p90)
genuine_correct_peak   = sum(1 for s in peak_scores   if s < p90)
ddos_correct           = sum(1 for s in ddos_scores   if s >= p99)

print(f"""
  Traffic context:
    Normal  : 10k–15k total  (~250 req/s per client)
    Peak    : ~20k    total  (~400 req/s per client)
    DDoS    : 80k+    total  (one client, 4× capacity)

  Average anomaly scores:
    Normal traffic : {avg_normal:.6f}
    Peak hour      : {avg_peak:.6f}
    DDoS attacker  : {avg_ddos:.6f}

  Classification accuracy (15 samples each):
    Normal correctly GENUINE  : {genuine_correct_normal}/15
    Peak correctly GENUINE    : {genuine_correct_peak}/15
    DDoS correctly ANOMALY    : {ddos_correct}/15

  Score separation (DDoS vs best legitimate):
    {separation:.6f}

  Slow ramp detection:
    First SUSPICIOUS at step : {first_suspicious if first_suspicious is not None else 'not detected'}
    First ANOMALY    at step : {first_anomaly    if first_anomaly    is not None else 'not detected'}
""")

# Verdict
all_pass = (
    genuine_correct_normal >= 12 and
    genuine_correct_peak   >= 12 and
    ddos_correct           >= 12 and
    separation             >  0.05
)

if all_pass:
    print("  ✓ PASS — HST working correctly at 100k scale")
    print("  ✓ Normal traffic (10-15k) → not flagged")
    print("  ✓ Peak hour (20k)         → not flagged")
    print("  ✓ DDoS (80k+)             → correctly flagged")
    print("  ✓ Ready to move to Day 2")
elif separation > 0.01:
    print("  ~ MARGINAL — partial separation, investigate further")
    print(f"  → Normal correct : {genuine_correct_normal}/15")
    print(f"  → Peak correct   : {genuine_correct_peak}/15")
    print(f"  → DDoS correct   : {ddos_correct}/15")
else:
    print("  ✗ FAIL — run: pip show river  and share output")
