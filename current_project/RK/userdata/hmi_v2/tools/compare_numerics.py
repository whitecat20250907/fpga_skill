"""Independent-process CPU numerical A/B; does not claim RKNN equivalence."""
import argparse, hashlib, importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def worker(gaze, trajectory, output):
    sys.path[:0] = [str(gaze), str(gaze/'GazeFollower')]
    import numpy as np
    from ridge_isotonic_calibration import RidgeIsotonicCalibration
    from region8 import RegionDecider
    from gazefollower.filter.OneEuroFilter import OneEuroFilter
    spec = importlib.util.spec_from_file_location('original_trajectory', trajectory)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    rng = np.random.default_rng(20261024)
    features = rng.normal(size=(390, 258))
    labels = np.clip(.5 + features[:, :2]*.15, 0, 1)
    model = RidgeIsotonicCalibration()
    ok, error, fitted = model.calibrate(features, labels)
    if not ok: raise RuntimeError('Calibration failed')
    unseen = rng.normal(size=(96, 258))
    predicted = np.array([model.predict(row, (0., 0.))[1] for row in unseen])
    filt = OneEuroFilter(); decider = RegionDecider(); filtered=[]; regions=[]
    for i in range(600):
        if i == 300: filt.reset(); decider.reset()
        xy = np.clip([.5+.3*np.sin(i/37), .5+.3*np.cos(i/47)] + rng.normal(0,.003,2),0,1)
        smooth = filt.filter_values(xy, timestamp=100+i/30)
        filtered.append(smooth)
        cell = decider.update(*smooth)
        regions.append([*(cell or (-1,-1)), decider.confidence, float(decider.decided)])
    trajectories = [[], [(3,3)], [(3,3)]*20]
    trajectories += [np.cumsum(rng.normal(size=(n,2)),axis=0).tolist() for n in (2,8,48,300)]
    rasters = np.stack([module.trajectory_to_image(p) for p in trajectories])
    np.savez(output, fitted=fitted, error=np.array(error), predicted=predicted,
             filtered=np.asarray(filtered), regions=np.asarray(regions), rasters=rasters)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--worker',nargs=3)
    args=parser.parse_args()
    if args.worker:
        worker(*map(Path,args.worker)); return 0
    if not args.baseline: parser.error('--baseline is required')
    provenance=json.loads((ROOT/'vendor/PROVENANCE.json').read_text(encoding='utf-8'))['files']
    sources={item['path']:args.baseline/item['source'] for item in provenance}
    old_gaze=sources['vendor/gaze_app/ridge_isotonic_calibration.py'].parent
    old_trajectory=sources['vendor/ui_support/demo_trajectory.py']
    env={**os.environ, 'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    with tempfile.TemporaryDirectory(prefix='hmi_numeric_') as tmp:
        paths=[]
        for label,gaze,traj in [('baseline',old_gaze,old_trajectory),('integrated',ROOT/'vendor/gaze_app',ROOT/'vendor/ui_support/demo_trajectory.py')]:
            output=Path(tmp)/(label+'.npz'); paths.append(output)
            subprocess.run([sys.executable,__file__,'--worker',str(gaze),str(traj),str(output)],env=env,check=True)
        import numpy as np
        comparisons={}
        with np.load(paths[0]) as old, np.load(paths[1]) as new:
            for key in old.files:
                a,b=old[key],new[key]
                comparisons[key]={'shape':list(a.shape),'bitwise_equal':a.dtype==b.dtype and a.tobytes()==b.tobytes(),
                    'max_abs_error':float(np.max(np.abs(a.astype(float)-b.astype(float)))),
                    'sha256':hashlib.sha256(b.tobytes()).hexdigest()}
    report={'status':'PASS' if all(x['bitwise_equal'] for x in comparisons.values()) else 'FAIL',
            'scope':'CPU stages on deterministic synthetic inputs; excludes RKNN inference and wrapper/hardware timing',
            'seed':20261024,'numpy':np.__version__,'comparisons':comparisons}
    (ROOT/'docs/evidence/numerical_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2)); return 0 if report['status']=='PASS' else 1

if __name__=='__main__': raise SystemExit(main())
