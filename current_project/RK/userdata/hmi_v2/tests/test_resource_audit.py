from core.resource_audit import ResourceAudit, DATA_TOPICS, PRODUCERS


def feed(audit, now, serial, faces=2, hands=4):
    base = dict(epoch=7, src_ns=now, pub_ns=now, seq=serial, serial=serial)
    for topic in DATA_TOPICS:
        audit.observe(topic, dict(base, faces=[{'valid': True}] * faces,
                                 hands=[{}] * hands, state='IDLE'), now)
    for p in PRODUCERS:
        audit.observe('sys.metrics.' + p, dict(base, ok=True, instance=p), now)
    audit.sample(now)


def test_stable_four_hands_requires_time_coverage_and_all_services():
    a = ResourceAudit('dual_four_hands', 1_000_000_000)
    for i in range(1, 61):
        feed(a, 1_000_000_000 + i * 100_000_000, i)
    r = a.finish(7_000_000_000)
    assert r['stable'] and r['scenario_coverage']
    assert abs(r['ring_publish_rate_hz'] - 10) < 1e-9


def test_early_burst_then_silence_is_not_a_stable_run_or_scene():
    a = ResourceAudit('dual_four_hands', 1_000_000_000)
    feed(a, 2_000_000_000, 1)
    for i in range(1, 61):
        a.sample(2_000_000_000 + i * 100_000_000)
    r = a.finish(8_000_000_000)
    assert not r['stable'] and not r['scenario_coverage']
    assert r['max_message_gap_ms']['vision.hands'] == 6000


def test_four_hands_and_two_faces_must_overlap_in_time():
    a = ResourceAudit('dual_four_hands', 1_000_000_000)
    for i in range(1, 61):
        feed(a, 1_000_000_000 + i * 100_000_000, i,
             faces=2 if i < 30 else 1, hands=2 if i < 30 else 4)
    assert not a.finish(7_000_000_000)['scenario_coverage']


def test_serial_regression_invalidates_even_if_final_serial_is_larger():
    a = ResourceAudit('single', 1_000_000_000)
    for i in range(1, 61):
        feed(a, 1_000_000_000 + i * 100_000_000, 1 if i == 30 else i, 1, 2)
    r = a.finish(7_000_000_000)
    assert not r['stable'] and r['ring_regressed']
    assert r['ring_publish_rate_hz'] is None


def test_unhealthy_service_and_restart_are_not_hidden_by_recovery():
    a = ResourceAudit('single', 1_000_000_000)
    for i in range(1, 61):
        now = 1_000_000_000 + i * 100_000_000
        feed(a, now, i, 1, 2)
        if i == 30:
            a.observe('sys.metrics.hand', dict(epoch=7, src_ns=now, ok=False, instance='new'), now)
    r = a.finish(7_000_000_000)
    assert not r['stable']
    assert r['errors']['unhealthy_service'] == 1
    assert r['errors']['service_restarted'] == 1
