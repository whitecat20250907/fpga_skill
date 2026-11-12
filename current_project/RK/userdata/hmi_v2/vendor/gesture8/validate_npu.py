import json
import time
from pathlib import Path
import numpy as np
from classifier import Classifier
root = Path(__file__).resolve().parent
data = np.load(root/'model/vectors.npz')
classifier = Classifier(root)
rows = []
try:
    for image, expected in zip(data['images'], data['torch_logits']):
        start = time.monotonic()
        prediction = classifier.predict(image)
        expected = np.exp(expected-expected.max()); expected /= expected.sum()
        error = float(np.max(np.abs(np.asarray(prediction['probabilities'])-expected)))
        # Predeclared FP16 gate on probabilities, plus identical decision/argmax.
        assert error <= .005, error
        assert int(np.argmax(expected)) == classifier.classes.index(prediction['label'])
        assert bool(expected.max() >= .6) == prediction['accepted']
        rows.append(dict(probability_max_abs=error, inference_ms=(time.monotonic()-start)*1000, **prediction))
finally:
    classifier.close()
report = dict(status='PASS_ACTUAL_RK3576_NPU_SYNTHETIC_PARITY', rows=rows,
              boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
              max_probability_error=max(r['probability_max_abs'] for r in rows),
              median_ms=float(np.median([r['inference_ms'] for r in rows[1:]])),
              p95_ms=float(np.percentile([r['inference_ms'] for r in rows[1:]],95)),
              human_accuracy_tested=False, camera_opened=False)
(root/'model/npu_validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
