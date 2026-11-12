from core.metrics import Metrics

def test_metrics_use_bounded_recent_observations_and_reject_invalid_values():
    metrics=Metrics()
    for i in range(300):metrics.observe(i*10_000_000,stage=float(i),invalid=float('nan'))
    result=metrics.snapshot(3_000_000_000)
    assert len(metrics.samples)==256 and result['observed_hz']==100.
    assert result['stages']['stage']['samples']==256
    assert result['stages']['stage']['p95_ms']==286.
    assert 'invalid' not in result['stages'] and result['npu_utilization'] is None
    result=metrics.snapshot(10_000_000_000)
    assert result['observed_hz']==0 and result['stages']=={}
