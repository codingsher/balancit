import time
from feature_extractor import FeatureExtractor
from config import INTERVAL_SECONDS

print(f"ML service starting. Interval: {INTERVAL_SECONDS}s")
print(f"Day 9 mode: feature extraction only (no ML yet)")
print("-" * 60)

extractor = FeatureExtractor()

while True:
    cycle_start = time.time()

    print(f"\n[Cycle @ {time.strftime('%H:%M:%S')}]")

    features_by_pod = extractor.extract_all()

    if not features_by_pod:
        print("  No active pods.")
    else:
        for pod, features in features_by_pod.items():
            print(
                f"  {pod:<40} "
                f"rps={features['rps']:6.2f}  "
                f"err={features['error_rate']:.3f}  "
                f"ent={features['entropy']:.3f}  "
                f"p95={features['p95_latency']*1000:6.1f}ms"
            )

    elapsed = time.time() - cycle_start
    sleep_for = max(0, INTERVAL_SECONDS - elapsed)
    time.sleep(sleep_for)
