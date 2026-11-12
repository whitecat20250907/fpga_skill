"""Publish real v4a running recovery while retaining its known control defect."""
import copy
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from publish_app39_recovery_v3 import encoded,future_ref,load,ref,save_new,R,Y

O=Y/'evidence/application_recovery_actual_v6'

def main():
    cfg=load(O/'config.json');binding=load(O/'binding.json');bpin=load(O/'binding_reference.json')
    assert ref(O/'binding.json')['sha256']==bpin['sha256']=='d2f6a001f6d01fc5a6eb0db8cb917a6bd1a1c960bf1f2f04cfb0a56263fab32a'
    assert ref(O/'config.json')['sha256']==binding['owner_config']['sha256']=='47e0759e07caa7a5507ce2f159c616ed865c3e45e0994df3c31462f361f0dc98'
    assert binding['owner']['pid']==250418 and binding['owner']['start_ticks']==67336261
    assert binding['control_config_runtime_mutation_detected'] and not binding['owner_keep_accepted'] and not binding['interaction_control_accepted']
    for number,action in ((1,'snapshot_failed_bar'),(3,'quiesce'),(4,'retain_same_bit'),(5,'reprobe'),(6,'start_panel'),(7,'capture_fpga'),(8,'roundtrip')):
        rpc=load(O/f'rpc_{number:04d}_sent.json');response=rpc['response']
        assert rpc['sequence']==number and not rpc['pending'] and response['ok'] and response['action']=='native_action'
        assert response['supervisor']==binding['owner']
        assert load(O/f'payload_{"retain_same_bit" if number==4 else "snapshot_failed_bar" if number==1 else action}.json')['native_action']==action
    capture=load(O/'rpc_0007_sent.json')['response']['value']['value']
    assert capture['status']=='PASS_ACTUAL_DUAL_STREAM_NATIVE_AND_CLEAN_CLOSE'
    assert capture['end']['errno']==capture['end']['cleanup_errno']==0
    assert len(capture['same_frame_tensor_checks'])==3 and all(c['face128_byte_exact'] and c['palm192_byte_exact'] for c in capture['same_frame_tensor_checks'])
    rgb=load(O/'rpc_0008_sent.json')['response']['value']['value']
    assert rgb['status']=='PASS_FULL_RGB1080_H2C_FPGA_C2H_BYTE_COMPARE' and len(rgb['images'])==2
    assert all(v['iterations']==3 and v['bytes_per_image']==6220800 and v['returncode']==0 for v in rgb['images'])
    started=load(O/'rpc_0009_sent.json');assert started['response']['ok'] and started['response']['phase']=='FEATURE_RUNNING'
    exit_proof=load(O/'supervisor_exit_original.json')
    assert exit_proof['owner_exited'] and exit_proof['original_cleanup_errno']==110 and not exit_proof['normal_runtime_PASS']
    names=('GOAL_PROGRESS.json','CURRENT_CAMERA.json');before={n:(R/n).read_bytes() for n in names}
    progress,current=[json.loads(before[n]) for n in names]
    assert current['status']=='POINTER_ACTUAL_APP39_FAILED_NO_HEALTHY_MODEL' and ref(current['selection']['path'])==current['selection']
    spec=importlib.util.spec_from_file_location('_v4a_publication_remote',Y/'tools/execute_application_recovery_actual_v6.py')
    a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
    body='''import hashlib,importlib.util,json,time
from pathlib import Path
pin=__PIN__;source='/home/linaro/pcie_fix_20261003/hft2_recovery_v3_20261024/snapshot_application_readonly.py'
assert hashlib.sha256(Path(source).read_bytes()).hexdigest()=='bfa9d9efa5ea847b0e063e59109da86fadafb79f0c62f739913ad0024b11d510'
s=importlib.util.spec_from_file_location('_v4a_publisher_readonly_collector',source);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
snapshot=m.sample(pin)
root=Path(__ROOT__);state=json.loads((root/'lifecycle/video_owner_state.json').read_text())
assert state['phase']=='FEATURE_RUNNING' and state['main_handle_retained'] and state['feature_session_retained']
assert not state['feature_errors'] and state['tick_error'] is None and state['main_returncode'] is None
assert state['keep_feature'] is False and state['historical_failures_relabelled'] is False
assert not Path(state['runtime']['stop_request']).exists()
q=json.loads(Path(state['recovery_quiesced']['path']).read_text())
assert q['system']['kernel_other_matching_tasks']==[] and q['system']['kernel_dma_tasks']==[] and q['system']['device_fds']==[]
assert q['system']['loaded_DMA_modules']==[] and q['system']['PCI_devices']==[] and q['system']['PCIe_root_bound'] is False
print(json.dumps(dict(status='ACTUAL_V4A_FRESH_PASSIVE_RUNNING_SNAPSHOT_CONTROL_LIMITATION',snapshot=snapshot,state=state,quiescence=q)))
'''.replace('__PIN__',repr(bpin)).replace('__ROOT__',repr(binding['root']))
    actual=a.remote('verify_v4a_running_publication_fresh_readonly',body,timeout=30)
    save_new(O/'running_publication_fresh.json',actual)
    s=importlib.util.spec_from_file_location('_v4a_publication_observer_rules',Y/'tools/watch_application_longrun_v3.py')
    watch=importlib.util.module_from_spec(s);s.loader.exec_module(watch)
    row=watch.LongrunState().observe(actual['snapshot'])
    prior=progress['full_task_ledger'];assert ref(prior['path'])==prior
    ledger=copy.deepcopy(load(prior['path']));revision=ledger['revision']+1
    out=Path(prior['path']).parent.parent/f'goal_task_ledger_v{revision}';assert not out.exists()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    selected=dict(status='ACTUAL_APP39_V4A_RUNNING_CONTROL_REPAIR_PENDING',observed_utc=now,
        previous_failed_selection=current['selection'],actual_binding=ref(O/'binding.json'),remote_binding=bpin,
        actual_owner=binding['owner'],runtime=actual['state']['runtime'],feature_directory=binding['feature_directory'],
        candidate_programming_receipt=binding['candidate_programming_receipt'],
        active_driver=binding['active_driver'],active_driver_build_id=binding['active_driver_build_id'],
        recovery_config=ref(O/'config.json'),original_failed_cleanup_errno=110,historical_failures_relabelled=False,
        original_empty_supervisor_exit=ref(O/'supervisor_exit_original.json'),
        actual_running_snapshot=ref(O/'running_publication_fresh.json'),actual_passive_observation=row,
        capture_byte_checks=ref(O/'rpc_0007_sent.json'),RGB_roundtrip=ref(O/'rpc_0008_sent.json'),
        true_programmer=exit_proof.get('programming_owner',{'pid':202401,'start_ticks':63896509}),
        same_SRAM_recovery=True,new_JTAG_or_Flash=False,keep_accepted=False,interaction_control_accepted=False,
        known_control_defect=binding['control_limitation'],longrun_accepted=False,
        human_or_optical_acceptance=False,full_goal_complete=False,
        limitation='App39/hand/relay restored with clean byte checks and fresh source/UI progress. Original start_profile mutates the shared in-memory config; guarded keep/interaction are not accepted. Keep this visual generation running pending a reviewed normal close/exact empty-owner exit and new app40/bit/v12 transaction. Old cleanup110 failures remain failures; no root-cause or longrun/human acceptance.')
    out.mkdir();save_new(out/'selection.json',selected);selection=ref(out/'selection.json')
    pointer=dict(status='POINTER_ACTUAL_APP39_V4A_RUNNING_CONTROL_REPAIR_PENDING',selection=selection,scope=selected['limitation'])
    event=dict(status=selected['status'],observed_utc=now,selection=selection,current_selected_runtime_is_live=True,
        control_ready=False,longrun_accepted=False,human_or_optical_accepted=False,full_goal_complete=False)
    key=f'v{revision}_actual_v4a_recovery_running_control_repair_pending';ledger['evidence'][key]=event
    for task in ledger['tasks']:
        if task['id'] in ('T02','U01','U02','U03','U04','U05'):
            task.setdefault('evidence_keys',[]).append(key)
            task['current_state']='新250418代恢复app39/hand/relay，三同帧tensor+六RGB检查通过；cfg共享可变导致keep/交互校验待修，现保持visual运行并观察，不计最终通过。'+task['current_state']
    ledger.update(revision=revision,previous_ledger=prior,updated_utc=now,publisher=ref(__file__),full_goal_complete=False,
        current_camera_selection=selection,next_safe_action='保持v4a visual运行并观察。准备精确原stop_owned完整wait→空250418退出→新EX app40/TD修复位流/v12及真实回退；不热改/不伪造keep。')
    save_new(out/'ledger.json',ledger)
    progress.update(observed_utc=now,full_task_ledger=ref(out/'ledger.json'),protected_CURRENT=future_ref(R/'CURRENT_CAMERA.json',encoded(pointer)))
    progress['active_work'].update(status=selected['status'],current_selected_runtime_is_live=True,actual_new_UI_application=event,next_action=ledger['next_safe_action'])
    progress['first_video_milestone']['actual_new_UI_application']=event;progress['current_runtime_stop_rule']=selected['limitation']
    for name,value in zip(names,(progress,pointer)):
        assert (R/name).read_bytes()==before[name]
        temporary=R/(name+'.v4a_publish.tmp')
        with temporary.open('xb') as f:f.write(encoded(value))
        assert (R/name).read_bytes()==before[name];os.replace(temporary,R/name)
    proc=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tools/refresh_pending_tasks.py')],cwd=R,capture_output=True)
    (out/'refresh.stdout').write_bytes(proc.stdout);(out/'refresh.stderr').write_bytes(proc.stderr);assert proc.returncode==0
    for name in (*names,'PENDING_TASKS.md','PENDING_TASKS.json','PENDING_FIELD_TESTS.md','PENDING_FIELD_TESTS.json'):
        (out/('snapshot_'+name)).write_bytes((R/name).read_bytes())
    save_new(out/'publication.json',event);print('ACTUAL_V4A_RUNNING_WITH_CONTROL_LIMITATION_PUBLISHED',revision)

if __name__=='__main__':main()
