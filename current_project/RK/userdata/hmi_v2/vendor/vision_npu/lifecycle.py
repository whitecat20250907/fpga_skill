"""Own app launches, normal stop/reap, and finite exclusive benchmark jobs.

Environment is retained in memory only. No driver/FPGA changes, signals,
foreign-child adoption, or unbounded CSV loading.
"""
import fcntl,importlib.util,json,os,pwd,subprocess,time,traceback,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent
STATE=Path('/userdata/cpu_model_reuse_lifecycle_20261022');STATE.mkdir(exist_ok=False)
spec=importlib.util.spec_from_file_location('known_lifecycle','/userdata/gaze_eye_fix_20261021/lifecycle_owner.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
prior=json.loads(Path('/userdata/npu_dualcore_lifecycle_20261022/selected.json').read_text())['runtime']
m.need(m.owners()==prior['owners'],'Current runtime changed');m.need(m.identity(prior['supervisor']['pid'])==prior['supervisor'],'Current parent changed')
proc=next(x for x in prior['owners'] if 'run_gaze.py' in x['cmdline'])
env={}
for item in Path(f'/proc/{proc["pid"]}/environ').read_bytes().split(b'\0'):
    if b'=' in item:
        k,v=item.split(b'=',1);env[k.decode()]=v.decode()
m.env=env;m.ROOT=STATE;m.E=STATE/'lifecycle';m.E.mkdir();m.NEW=Path(prior['app']);m.OLD=m.NEW;m.RESTART_USER=False
lock=open('/home/linaro/pcie_fix_20261003/twb_hardware_trial.lock','a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
child=row=None;phase='READY';seq=0
def save(n,v):
    p=STATE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
save('ready.json',dict(supervisor=m.identity(os.getpid()),prior=prior,phase=phase))
while True:
    request=STATE/f'request_{seq+1:04d}.json'
    if not request.exists():time.sleep(.1);continue
    seq+=1;cmd=json.loads(request.read_text());response=dict(sequence=seq,ok=False)
    try:
        m.need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==m.BOOT,'Boot changed')
        action=cmd['action']
        if action=='stop_original':
            m.need(phase=='READY','Already stopped');m.need(m.owners()==prior['owners'],'Runtime changed')
            Path(prior['stop_request']).touch(exist_ok=False)
            proof=Path('/userdata/npu_dualcore_lifecycle_20261022/lifecycle/selected_uncapped_closed.json');deadline=time.monotonic()+45
            while not proof.exists() and time.monotonic()<deadline:time.sleep(.1)
            closed=json.loads(proof.read_text())
            m.need(closed['status']=='PASS_OWNED_CHILD_REAPED_NATIVE_CLOSED' and closed['parent_pid']==prior['supervisor']['pid'] and closed['launcher']==prior['launcher'],'Close proof mismatch')
            m.need(not m.owners(),'Owners remain');m.no_camera_fds();save('original_closed.json',closed);phase='STOPPED'
        elif action in ('benchmark','job'):
            m.need(phase=='STOPPED' and not m.owners(),'Benchmark requires stopped runtime')
            account=pwd.getpwuid(1000);log=STATE/(cmd.get('label','benchmark')+'.log')
            done=threading.Event();loadfile=STATE/'npu_load.txt'
            def sample_load():
                while not done.is_set():
                    try:
                        tmp=loadfile.with_suffix('.tmp');tmp.write_text(Path('/sys/kernel/debug/rknpu/load').read_text());tmp.replace(loadfile)
                    except OSError:pass
                    done.wait(.25)
            sampler=threading.Thread(target=sample_load);sampler.start()
            try:
                with log.open('w') as f:
                    p=subprocess.run([str(m.BASE/'app_venv/bin/python'),'-u','-B',str(Path(cmd.get('package',str(ROOT)))/cmd.get('script','benchmark_dual.py')),*cmd.get('args',[])],cwd=ROOT,env=dict(env,NPU_LOAD_FILE=str(loadfile),GAZE_APP_DIR=cmd.get('app','/userdata/gaze_model_migration_v1_20261014/app_v34_cpu_reuse_20261022')),stdout=f,stderr=subprocess.STDOUT,
                        user=1000,group=1000,extra_groups=os.getgrouplist(account.pw_name,1000),timeout=600)
            finally:done.set();sampler.join()
            response['returncode']=p.returncode;m.need(p.returncode==0,'Benchmark failed; log '+str(log))
        elif action=='start':
            m.need(phase=='STOPPED' and child is None,'Must stop first');m.need(not m.owners(),'Existing runtime')
            app=Path(cmd.get('app',prior['app']));m.NEW=app
            m.env=dict(env,GAZE_APP_DIR=str(app),NPU_MAX_FACES='2')
            child,row=m.start(app,cmd.get('label','selected'),cmd.get('seconds'));phase='STARTING';row=m.verify_running(child,row);phase='RUNNING';response['runtime']=row
        elif action=='close_trial':
            m.need(child is not None and phase=='RUNNING','Missing owned trial')
            response['closed']=m.closed(child,row,60);child=row=None;phase='STOPPED'
        elif action=='stop_owned':
            m.need(child is not None and phase=='RUNNING','Missing owned app');m.need(m.identity(row['launcher']['pid'])==row['launcher'],'Launcher changed')
            Path(row['stop_request']).touch(exist_ok=False);response['closed']=m.closed(child,row,45);child=row=None;phase='STOPPED'
        elif action=='finish':
            m.need(child is not None and phase=='RUNNING','Missing owned app');row=m.verify_running(child,row);save('selected.json',dict(status='PASS_NPU_APPLICATION_RUNNING',runtime=row))
            response.update(ok=True,phase='FINAL_KEEP',runtime=row);save(f'response_{seq:04d}.json',response)
            fcntl.flock(lock,fcntl.LOCK_UN);lock.close();child.wait();m.closed(child,row,1);break
        else:raise ValueError(action)
        response['ok']=True
    except BaseException as e:response.update(error=repr(e),traceback=traceback.format_exc())
    response['phase']=phase;save(f'response_{seq:04d}.json',response)
