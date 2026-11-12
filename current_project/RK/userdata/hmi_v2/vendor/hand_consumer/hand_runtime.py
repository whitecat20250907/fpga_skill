"""Shared strict NPU recognizer; CPU is an explicit reference-test backend."""

def create_recognizer(model_path, *, video=True, num_hands=4, cpu_threads=2, backend='npu'):
    if type(num_hands) is not int or not 1<=num_hands<=4:
        raise ValueError('num_hands must be in 1..4')
    if type(cpu_threads) is not int or cpu_threads not in (0,1,2,4):
        raise ValueError('cpu_threads must be 0, 1, 2 or 4; 0 preserves default delegate')
    if backend not in ('npu','cpu'):raise ValueError('backend must be npu or cpu')
    if backend=='npu':
        import os,sys
        from pathlib import Path
        package=Path(os.environ.get('NPU_VISION_PACKAGE','/userdata/cpu_model_reuse_20261022'))
        if not (package/'vision_pipeline.py').is_file():raise RuntimeError('NPU package is absent: '+str(package))
        sys.path.insert(0,str(package))
        from vision_pipeline import HandRecognizer
        return HandRecognizer(num_hands=num_hands)
    import mediapipe as mp
    class CPUOptions(mp.tasks.BaseOptions):
        def to_pb2(self):
            value=super().to_pb2()
            if cpu_threads:
                value.acceleration.Clear()
                value.acceleration.xnnpack.num_threads=cpu_threads
            return value
    options=mp.tasks.vision.GestureRecognizerOptions(
        base_options=CPUOptions(model_asset_path=str(model_path),delegate=mp.tasks.BaseOptions.Delegate.CPU),
        running_mode=mp.tasks.vision.RunningMode.VIDEO if video else mp.tasks.vision.RunningMode.IMAGE,
        num_hands=num_hands,min_hand_detection_confidence=.6,min_hand_presence_confidence=.6,min_tracking_confidence=.6)
    return mp.tasks.vision.GestureRecognizer.create_from_options(options)


def create_frame_reader(app_dir,model_pid=None):
    """Use app34's model pixels; preserve explicit older-app compatibility."""
    import os,sys
    from pathlib import Path
    if (Path(app_dir)/'shared_model_frame.py').is_file():
        package=Path(os.environ.get('NPU_VISION_PACKAGE','/userdata/cpu_model_reuse_20261022'))
        sys.path.insert(0,str(package))
        from model_frame_reader import ExistingModelFrame
        return ExistingModelFrame(app_dir,model_pid)
    from pcie_preview_reader import ExistingPreview
    return ExistingPreview(app_dir,model_pid)


class SampleClock:
    """No backlog. A busy shared frame is retried soon, not one full period later."""
    def __init__(self,fps):
        import math
        if not math.isfinite(fps) or fps<0:raise ValueError('fps must be finite and nonnegative; 0 is uncapped')
        self.period=1/fps if fps else 0.;self.deadline=0.
    def delay(self,now):return max(0.,self.deadline-now)
    def busy(self,now):self.deadline=now+.005
    def accepted(self,now):self.deadline=now+self.period
