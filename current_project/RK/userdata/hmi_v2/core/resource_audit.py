"""Time-window checks for a measurement; never controls the running system."""
from collections import Counter

DATA_TOPICS = ('frame.meta', 'vision.face', 'vision.gaze', 'vision.hands', 'hmi.state')
PRODUCERS = ('fpga-io', 'gaze', 'hand', 'engine', 'ui', 'hud', 'adapters', 'console')


class ResourceAudit:
    def __init__(self, scenario, start_ns):
        if scenario not in ('empty', 'single', 'dual_four_hands'):
            raise ValueError('Unknown scenario')
        self.scenario = scenario
        self.start_ns = start_ns
        self.latest = {}
        self.arrivals = {}
        self.max_gaps = Counter()
        self.epochs = set()
        self.instances = {}
        self.errors = Counter()
        self.windows = self.healthy_windows = self.scene_windows = 0
        self.ring_first = self.ring_last = None
        self.ring_regressed = False

    def observe(self, topic, msg, now_ns):
        if topic not in DATA_TOPICS and not topic.startswith('sys.metrics.'):
            return
        previous = self.arrivals.get(topic, self.start_ns)
        self.max_gaps[topic] = max(self.max_gaps[topic], now_ns - previous)
        self.arrivals[topic] = now_ns
        self.latest[topic] = msg
        self.epochs.add(msg.get('epoch'))
        if not msg.get('epoch'):
            self.errors['missing_epoch'] += 1
        if not 0 < msg.get('src_ns', 0) <= now_ns:
            self.errors['invalid_source_time'] += 1
        if topic.startswith('sys.metrics.'):
            if not msg.get('ok'):
                self.errors['unhealthy_service'] += 1
            instance = msg.get('instance')
            if instance:
                old = self.instances.setdefault(topic, instance)
                if old != instance:
                    self.errors['service_restarted'] += 1
        if topic == 'frame.meta':
            row = (msg.get('pub_ns', 0), msg.get('serial', 0), msg.get('epoch'))
            if self.ring_last and (row[0] < self.ring_last[0] or row[1] < self.ring_last[1] or row[2] != self.ring_last[2]):
                self.ring_regressed = True
            if self.ring_first is None:
                self.ring_first = row
            self.ring_last = row

    def sample(self, now_ns):
        # Exclude only the first second for PUB/SUB connection establishment.
        if now_ns - self.start_ns < 1_000_000_000:
            return
        self.windows += 1

        def fresh(topic, limit):
            msg = self.latest.get(topic, {})
            return bool(msg.get('epoch')) and 0 <= now_ns - msg.get('src_ns', 0) <= limit

        data_ok = all(fresh(t, 350_000_000) for t in DATA_TOPICS)
        metrics_ok = all(fresh('sys.metrics.' + p, 2_000_000_000)
                         and self.latest['sys.metrics.' + p].get('ok') for p in PRODUCERS)
        state_ok = self.latest.get('hmi.state', {}).get('state') not in ('DEGRADED', 'ESTOP')
        self.healthy_windows += int(data_ok and metrics_ok and state_ok and len(self.epochs) == 1)
        if fresh('vision.face', 350_000_000) and fresh('vision.hands', 350_000_000):
            face, hand = self.latest['vision.face'], self.latest['vision.hands']
            nf = sum(bool(f.get('valid')) for f in face.get('faces', []))
            nh = len(hand.get('hands', []))
            matched = ((nf == 0 and nh == 0) if self.scenario == 'empty' else
                       (nf == 1 and 1 <= nh <= 2) if self.scenario == 'single' else (nf == 2 and nh == 4))
            self.scene_windows += int(matched and face.get('epoch') == hand.get('epoch'))

    def finish(self, now_ns):
        required = DATA_TOPICS + tuple('sys.metrics.' + p for p in PRODUCERS)
        gaps = {t: max(self.max_gaps[t], now_ns - self.arrivals.get(t, self.start_ns)) / 1e6 for t in required}
        healthy = self.healthy_windows / max(1, self.windows)
        coverage = self.scene_windows / max(1, self.windows)
        rate = None
        if self.ring_first and self.ring_last and not self.ring_regressed:
            a, b = self.ring_first, self.ring_last
            if b[0] > a[0] and b[1] > a[1]:
                rate = (b[1] - a[1]) * 1e9 / (b[0] - a[0])
        return dict(stable=bool(self.windows >= 10 and healthy >= .95 and max(gaps.values()) <= 2000
                                and not self.errors and len(self.epochs) == 1 and rate is not None),
                    scenario_coverage=bool(self.windows >= 10 and coverage >= .8),
                    time_windows=self.windows, healthy_window_fraction=healthy,
                    scenario_window_fraction=coverage, max_message_gap_ms=gaps,
                    errors=dict(self.errors), ring_regressed=self.ring_regressed,
                    ring_publish_rate_hz=rate,
                    thresholds=dict(warmup_ms=1000, sample_interval_ms=100, data_age_ms=350,
                                    heartbeat_age_ms=2000, max_gap_ms=2000,
                                    healthy_fraction=.95, scenario_fraction=.8))
