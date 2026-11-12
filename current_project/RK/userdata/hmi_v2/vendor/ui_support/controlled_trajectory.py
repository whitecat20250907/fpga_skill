"""ModeGate consumer inside the existing hand inference loop; no extra worker.

The original relay remains the only game gesture policy/action owner. This
module never sends actions. All accepted interaction modes invoke the shared recorder;
the original RKNN classifier is constructed lazily on the first completed stroke.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from interaction_ui import ExistingTrajectorySession, TrajectorySnapshot, hand_keys


def load_mode_gate(config_path, config_sha256):
    """Read the same resolved, pinned GAME_EXISTING_APP34_MODE_V2 owner config."""
    config_path = Path(config_path)
    raw = config_path.read_bytes()
    if not config_path.is_absolute() or len(raw) > 1048576 or hashlib.sha256(raw).hexdigest() != config_sha256:
        raise ValueError('pinned absolute existing mode config required')
    config = json.loads(raw)
    if config.get('schema') != 'GAME_EXISTING_APP34_MODE_V2':
        raise ValueError('existing owner mode-v2 config required')
    helper = config['interaction_modes']
    path = Path(helper['path'])
    raw_helper = path.read_bytes()
    if not path.is_absolute() or hashlib.sha256(raw_helper).hexdigest() != helper['sha256']:
        raise ValueError('pinned existing interaction_modes helper required')
    name = '_trajectory_owner_interaction_modes_' + helper['sha256'][:16]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    module = sys.modules[name]
    if module.SCHEMA != 'INTERACTION_MODE_V1':
        raise ValueError('existing ModeGate schema required')
    return module.ModeGate(config['interaction_state'], boot_id=config['boot_id'], controller=config['interaction_controller'])


class ControlledTrajectory:
    def __init__(self, mode_gate, trajectory_factory, classifier_factory, source_instance, clock_ns=time.monotonic_ns):
        self.gate, self.trajectory_factory, self.classifier_factory = mode_gate, trajectory_factory, classifier_factory
        self.source_instance, self.clock_ns = source_instance, clock_ns
        self.session = self.classifier = None
        self.generation = None
        self.classifier_calls = self.classifier_loads = 0
        self.static = TrajectorySnapshot(source_instance)
        self.previous_tracks = set()

    def close(self):
        self.session = None
        if self.classifier is not None:
            classifier, self.classifier = self.classifier, None
            classifier.close()

    def predict(self, raster):
        # ExistingTrajectorySession calls this only for each newly finished
        # raster; only completed strokes reach this method in any mode.
        if self.classifier is None:
            self.classifier = self.classifier_factory()
            self.classifier_loads += 1
        self.classifier_calls += 1
        return self.classifier.predict(raster)

    def _adopt(self, mode):
        if mode.generation != self.generation:
            self.close()
            self.static = TrajectorySnapshot(self.source_instance)
            self.generation = mode.generation

    def update(self, prediction, meta, now_ns, width, height):
        keys = hand_keys(prediction)
        retired = sorted(self.previous_tracks - set(keys))
        self.previous_tracks = set(keys)
        mode = self.gate.read(now_ns)
        self._adopt(mode)
        allowed = mode.accepted and meta['timestamp_ns'] > mode.cutoff_ns
        begin = self.clock_ns()
        if allowed:
            if self.session is None:
                self.session = ExistingTrajectorySession(self.trajectory_factory(), self, self.source_instance)
            snapshot = self.session.update(prediction, meta, now_ns, width, height)
        else:
            # Static labels still come directly from this exact prediction.
            idle = SimpleNamespace(recorders={key: SimpleNamespace(state='IDLE', points=[], released=True,
                reason='mode_' + mode.mode) for key in keys})
            snapshot = self.static.observe(prediction, idle, [], meta, now_ns, width, height)
        completed = self.clock_ns()
        # Commands issued during a slow first RKNN load cannot publish stale
        # trajectory state under the new mode. In-flight inference is not retried.
        final_mode = self.gate.read(completed)
        if final_mode.generation != mode.generation or not allowed:
            self._adopt(final_mode)
            snapshot.update(valid=False, hands=[], reason='mode_transition_or_precommand_source')
        snapshot['interaction_mode_ack'] = dict(mode=final_mode.mode, code=final_mode.code,
            epoch=final_mode.epoch, generation=final_mode.generation, accepted=final_mode.accepted,
            cutoff_ns=final_mode.cutoff_ns, changed_monotonic_ns=final_mode.changed_monotonic_ns,
            reason=final_mode.reason, timestamp_ns=meta['timestamp_ns'],
            capture_sequence=meta['sequence'], source_instance=self.source_instance)
        snapshot['retired_track_ids'] = retired
        snapshot['trajectory_ms'] = (completed - begin) / 1e6
        snapshot['classifier_calls'] = self.classifier_calls
        snapshot['classifier_loads'] = self.classifier_loads
        return snapshot


def mode_ack_matches(ack, mode_view, now_ns):
    """Relay shows an effective mode only after the same producer acknowledges."""
    from interaction_ui import MAX_AGE_NS
    return bool(isinstance(ack, dict) and ack.get('accepted') and mode_view.accepted
        and ack.get('mode') == mode_view.mode and ack.get('code') == mode_view.code
        and ack.get('epoch') == mode_view.epoch
        and type(ack.get('timestamp_ns')) is int
        and mode_view.cutoff_ns < ack['timestamp_ns'] <= now_ns
        and now_ns - ack['timestamp_ns'] <= MAX_AGE_NS)
