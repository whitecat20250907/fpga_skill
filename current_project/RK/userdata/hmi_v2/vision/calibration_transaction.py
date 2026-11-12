"""Keep the last fitted object until replacement succeeds; no numerical changes."""
class CalibrationTransaction:
    def __init__(self):self.previous=None
    def begin(self,current):
        if current is not None and current.has_calibrated:self.previous=current
    def finish(self,current):
        result=current if current is not None and current.has_calibrated else self.previous
        self.previous=None
        return result
    def clear(self):self.previous=None
