"""
Metrics Store for SentinelCache Gateway (Phase 5).

Stores request telemetry in-memory with query helpers for summary statistics,
timeseries aggregation, and recent request logs.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import math

class MetricsStore:
    def __init__(self, max_records: int = 5000):
        self.max_records = max_records
        self.records: List[Dict[str, Any]] = []

    def record_request(
        self,
        prompt: str,
        cache_outcome: str,  # 'hit', 'miss', 'blocked_by_guard'
        similarity_score: Optional[float],
        threshold_used: float,
        risk_score: float,
        provider: str,
        model: str,
        tier: str,
        latency_ms: float,
        estimated_cost_usd: float,
        guard_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        record = {
            "id": len(self.records) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt,
            "cache_outcome": cache_outcome,
            "similarity_score": similarity_score,
            "threshold_used": threshold_used,
            "risk_score": risk_score,
            "provider": provider,
            "model": model,
            "tier": tier,
            "latency_ms": latency_ms,
            "estimated_cost_usd": estimated_cost_usd,
            "guard_reason": guard_reason
        }
        self.records.append(record)
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]
        return record

    def get_summary(self) -> Dict[str, Any]:
        total_requests = len(self.records)
        if total_requests == 0:
            return {
                "total_requests": 0,
                "overall_hit_rate": 0.0,
                "hits": 0,
                "misses": 0,
                "blocked_by_guard": 0,
                "avg_latency_ms": 0.0,
                "median_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "total_cost_usd": 0.0,
                "estimated_cost_saved_usd": 0.0,
                "requests_by_provider": {},
                "requests_by_tier": {}
            }

        hits = sum(1 for r in self.records if r["cache_outcome"] == "hit")
        misses = sum(1 for r in self.records if r["cache_outcome"] == "miss")
        blocked = sum(1 for r in self.records if r["cache_outcome"] == "blocked_by_guard")
        hit_rate = round(hits / total_requests, 4)

        latencies = sorted(r["latency_ms"] for r in self.records)
        avg_latency = round(sum(latencies) / total_requests, 2)
        median_latency = round(latencies[len(latencies) // 2], 2)
        p95_idx = min(int(math.ceil(total_requests * 0.95)) - 1, total_requests - 1)
        p95_latency = round(latencies[p95_idx], 2)

        total_cost = round(sum(r["estimated_cost_usd"] for r in self.records), 6)
        
        # Estimate cost saved: average cost of a miss * number of hits
        miss_costs = [r["estimated_cost_usd"] for r in self.records if r["cache_outcome"] != "hit" and r["estimated_cost_usd"] > 0]
        avg_miss_cost = (sum(miss_costs) / len(miss_costs)) if miss_costs else 0.0001
        cost_saved = round(hits * avg_miss_cost, 6)

        by_provider: Dict[str, int] = {}
        by_tier: Dict[str, int] = {}
        for r in self.records:
            p = r["provider"]
            t = r["tier"]
            by_provider[p] = by_provider.get(p, 0) + 1
            by_tier[t] = by_tier.get(t, 0) + 1

        return {
            "total_requests": total_requests,
            "overall_hit_rate": hit_rate,
            "hits": hits,
            "misses": misses,
            "blocked_by_guard": blocked,
            "avg_latency_ms": avg_latency,
            "median_latency_ms": median_latency,
            "p95_latency_ms": p95_latency,
            "total_cost_usd": total_cost,
            "estimated_cost_saved_usd": cost_saved,
            "requests_by_provider": by_provider,
            "requests_by_tier": by_tier
        }

    def get_timeseries(self, window: str = "1h") -> List[Dict[str, Any]]:
        # Define time window filter
        now = datetime.now(timezone.utc)
        if window == "24h":
            delta = timedelta(hours=24)
            buckets_count = 24
        elif window == "7d":
            delta = timedelta(days=7)
            buckets_count = 14
        else:  # 1h default
            delta = timedelta(hours=1)
            buckets_count = 12

        start_time = now - delta
        filtered = [r for r in self.records if datetime.fromisoformat(r["timestamp"]) >= start_time]
        
        if not filtered:
            return []

        # Bucket requests into intervals
        step_seconds = delta.total_seconds() / buckets_count
        buckets: List[Dict[str, Any]] = []

        for i in range(buckets_count):
            b_start = start_time + timedelta(seconds=i * step_seconds)
            b_end = b_start + timedelta(seconds=step_seconds)
            
            b_records = [
                r for r in filtered 
                if b_start <= datetime.fromisoformat(r["timestamp"]) < b_end
            ]
            
            b_total = len(b_records)
            b_hits = sum(1 for r in b_records if r["cache_outcome"] == "hit")
            b_hit_rate = round(b_hits / b_total, 4) if b_total > 0 else 0.0
            b_avg_lat = round(sum(r["latency_ms"] for r in b_records) / b_total, 2) if b_total > 0 else 0.0
            b_cost = round(sum(r["estimated_cost_usd"] for r in b_records), 6)

            buckets.append({
                "timestamp": b_start.strftime("%H:%M" if window == "1h" else "%m-%d %H:%M"),
                "requests": b_total,
                "hit_rate": b_hit_rate,
                "avg_latency_ms": b_avg_lat,
                "cost_usd": b_cost
            })

        return buckets

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self.records[-limit:]))


# Global metrics store instance
metrics_store = MetricsStore()
