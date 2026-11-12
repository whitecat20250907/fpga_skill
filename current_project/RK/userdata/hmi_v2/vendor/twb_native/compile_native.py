"""Compile pinned native source and call only its constant library ABI.

Never calls native open/probe/snapshot/flush/commit or accesses a device.
Run only in the newly allocated directory named by this manifest.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import tarfile
import time

ROOT=Path(__file__).resolve().parent
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def run(command,label):
    started=time.monotonic()
    process=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        env=dict(os.environ,LC_ALL='C'))
    stdout,stderr=process.communicate();code=process.wait()
    (ROOT/(label+'.stdout.txt')).write_bytes(stdout);(ROOT/(label+'.stderr.txt')).write_bytes(stderr)
    row=dict(command=command,pid=process.pid,returncode=code,elapsed_seconds=time.monotonic()-started,
        original_Popen_wait_completed=True,stdout_path=label+'.stdout.txt',stderr_path=label+'.stderr.txt')
    commands.append(row)
    if code:raise RuntimeError(label+' failed: '+str(code))
    return stdout.decode('utf8','replace')


commands=[];result=dict(status='NOT_STARTED',commands=commands,device_opened=False,probe_called=False,
    owner_RPC_or_driver_or_model_touched=False,only_ctypes_call='twb_native_library_abi')
try:
    manifest=json.loads((ROOT/'MANIFEST.json').read_bytes())
    if ROOT.is_symlink() or str(ROOT)!=manifest['remote_root']:raise ValueError('Exact new compile directory required')
    if platform.machine().lower() not in ('aarch64','arm64'):raise ValueError('Actual ARM64 native compiler required')
    for row in manifest['native_sources']:
        path=ROOT/row['filename']
        if path.is_symlink() or not path.is_file() or sha(path)!=row['sha256']:raise ValueError('Source pin changed: '+row['filename'])
    if (ROOT/'libtwb.so').exists():raise ValueError('Fresh output only; refusing replacement')
    compiler=shutil.which('gcc');readelf=shutil.which('readelf')
    if not compiler or not readelf:raise ValueError('Existing gcc/readelf required; no package installation')
    result['compiler']=dict(path=compiler,resolved=str(Path(compiler).resolve()),sha256=sha(Path(compiler).resolve()))
    result['compiler_version']=run([compiler,'--version'],'compiler_version')
    result['compiler_target']=run([compiler,'-dumpmachine'],'compiler_target').strip()
    run([compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared',
         'twb_core.c','twb_mmio.c','-o','libtwb.so'],'compile')
    header=run([readelf,'-h','libtwb.so'],'readelf')
    if not re.search(r'^\s*Machine:\s+AArch64\s*$',header,re.M):raise ValueError('readelf Machine must be AArch64')
    binary=ROOT/'libtwb.so';raw=binary.read_bytes()
    if raw[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',raw,18)[0]!=183:raise ValueError('ELF64 little-endian AArch64 required')
    library=ctypes.CDLL(str(binary));function=library.twb_native_library_abi
    function.argtypes=[];function.restype=ctypes.c_uint32;abi=function()
    if abi!=0x32535754:raise ValueError('TWS2 constant library ABI required')
    for row in manifest['native_sources']:
        if sha(ROOT/row['filename'])!=row['sha256']:raise ValueError('Source changed during compile')
    result.update(status='PASS_ARM64_COMPILE_AND_CONSTANT_ABI_ONLY',machine='AArch64',ELF_class=64,
        library=dict(path=str(binary),sha256=sha(binary),bytes=len(raw)),ABI_value=f'0x{abi:08x}',
        ABI_text=abi.to_bytes(4,'little').decode('ascii'),sources_unchanged=True,
        host_manifest_sha256=manifest['host_manifest_sha256'],native_sources=manifest['native_sources'])
except Exception as error:
    result.update(status='FAIL_ARM64_COMPILE_AND_CONSTANT_ABI_ONLY',error=type(error).__name__+': '+str(error))
finally:
    (ROOT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    with tarfile.open(ROOT/'evidence.tar.gz','w:gz') as archive:
        for path in sorted([ROOT/'result.json',*ROOT.glob('*.stdout.txt'),*ROOT.glob('*.stderr.txt')]):
            archive.add(path,arcname=path.name,recursive=False)
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['status'].startswith('PASS') else 1)
