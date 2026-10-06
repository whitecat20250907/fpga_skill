"""Compile actual probe/init/teardown C functions with deterministic mocks.

This is a host-side fault-injection check, not a kernel-module build or proof of
real PCIe STOP/writeback behavior. No board or driver is loaded by this tool.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'fpga/deploy/sgdma_drv/anlogic_pci_lib.c'


def function(source, name):
    match = re.search(r'\b' + re.escape(name) + r'\s*\([^;]*?\)\s*\{', source)
    if not match:
        raise AssertionError('Function missing: ' + name)
    start = source.rfind('\n', 0, match.start()) + 1
    # Return-type continuation lines precede the name for these static helpers.
    if source[start:match.start()].strip() == '':
        start = source.rfind('\n', 0, start - 1) + 1
    brace = source.index('{', match.start())
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


PRELUDE = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
enum dma_data_direction { DMA_TO_DEVICE = 1, DMA_FROM_DEVICE = 2 };
#define MAGIC_ENGINE 0xabc
#define SGDMA_ENG_IRQ_NUM 1
#define BYPASS_MODE_SPACING 0x100
#define SGDMA_OFFSET_FROM_CHANNEL 0x400
#define SGDMA_ENGINE_CREDIT_XFER_MAX_DESC 64
#define SGDMA_ENGINE_XFER_MAX_DESC 1024
#define DESC_BYPASS 0
#define CHANNEL_SPACING 0x100
#define H2C_CHANNEL_OFFSET 0x1000
#define TARGET_SPACING 0x100
#define SGDMA_ID_H2C 0x1fc0
#define SGDMA_ID_C2H 0x1fc1
#define dbg_init(...) ((void)0)
#define dbg_sg(...) ((void)0)
#define pr_info(...) ((void)0)
#define pr_err(...) ((void)0)
#define spin_lock_irqsave(lock, flags) do { (void)(lock); (flags)=0; } while(0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(lock); (void)(flags); } while(0)
#define INIT_WORK(work, func) do { *(work)=1; (void)(func); } while(0)
struct anlogic_dev;
struct engine_regs { u32 identifier, interrupt_enable_mask; };
struct sgdma_common_regs { u32 credit_mode_enable_w1c; };
struct anlogic_dma_engine {
    int channel, streaming, work, desc_max, lock;
    unsigned long magic;
    u32 irq_bitmask, bypass_offset;
    enum dma_data_direction dir;
    char name[40];
    struct anlogic_dev *sgdev;
    struct engine_regs *regs;
    void *sgdma_regs;
    bool poll_removing, dma_quiescing;
    bool programmed, stopped, worker_attached, worker_joined;
    unsigned int resources;
    int init_index;
};
struct anlogic_dev {
    int idx, engines_num, config_bar_idx;
    int h2c_channel_max, c2h_channel_max;
    u32 mask_irq_h2c, mask_irq_c2h;
    void *bar[1];
    struct anlogic_dma_engine engine_h2c[4], engine_c2h[4];
};
static int poll_mode, failure_index, failure_stage;
static int attempts, allocations, frees, drained[8], drain_count;
static void engine_service_work(int *work) { (void)work; }
static bool st_c2h_credit_enabled(struct anlogic_dma_engine *engine)
{ (void)engine; return false; }
static u32 read_register(u32 *reg) { return *reg; }
static void write_register(u32 value, u32 *reg, unsigned long offset)
{ (void)offset; *reg=value; }
static int get_engine_id(struct engine_regs *regs) { return (int)(regs->identifier>>16); }
static int get_engine_channel_id(struct engine_regs *regs) { return (int)((regs->identifier>>8)&15); }
static void engine_free_resource(struct anlogic_dma_engine *engine)
{
    assert(!engine->programmed || (engine->stopped && engine->worker_joined));
    for (unsigned int bit=1; bit<=4; bit<<=1)
        if(engine->resources & bit) frees++;
    engine->resources=0;
}
static int engine_alloc_resource(struct anlogic_dma_engine *engine)
{
    engine->init_index=attempts++;
    for(int stage=1; stage<=3; stage++) {
        if((stage==2 && !poll_mode) || (stage==3 && engine->dir==DMA_TO_DEVICE)) continue;
        if(engine->init_index==failure_index && failure_stage==stage) {
            /* Mirrors allocation cleanup before any hardware target publication. */
            engine_free_resource(engine);
            return -ENOMEM;
        }
        engine->resources |= 1u<<(stage-1);
        allocations++;
    }
    return 0;
}
static int engine_init_regs(struct anlogic_dma_engine *engine)
{
    engine->programmed=true;
    if(engine->init_index==failure_index && failure_stage==4) return -EIO;
    if(engine->init_index==failure_index && failure_stage==5) return -EINVAL;
    return 0;
}
static void sgdma_thread_add_work(struct anlogic_dma_engine *engine)
{ assert(engine->magic==MAGIC_ENGINE); engine->worker_attached=true; }
static int engine_service_shutdown(struct anlogic_dma_engine *engine)
{ engine->stopped=true; return 0; }
static void sgdma_thread_remove_work(struct anlogic_dma_engine *engine)
{ engine->worker_attached=false; engine->worker_joined=true; }
static void cancel_work_sync(int *work) { assert(*work==1); }
static void engine_wait_stopped(struct anlogic_dma_engine *engine)
{
    assert(engine->stopped);
    assert(!engine->worker_attached);
    engine->worker_joined=true;
    drained[drain_count++]=engine->init_index;
    engine->dma_quiescing=false;
}
static int engine_destroy(struct anlogic_dev *, struct anlogic_dma_engine *);
'''

TESTS = r'''
static void prepare(struct anlogic_dev *dev, u32 *bar, int h, int c, int fi, int fs)
{
    memset(dev,0,sizeof(*dev)); memset(bar,0,0x4000);
    dev->h2c_channel_max=4; dev->c2h_channel_max=4; dev->bar[0]=bar;
    for(int i=0;i<h;i++) bar[(i*CHANNEL_SPACING)/4]=(SGDMA_ID_H2C<<16)|(i<<8)|0x8000;
    for(int i=0;i<c;i++) bar[(H2C_CHANNEL_OFFSET+i*CHANNEL_SPACING)/4]=(SGDMA_ID_C2H<<16)|(i<<8)|0x8000;
    failure_index=fi; failure_stage=fs;
    attempts=allocations=frees=drain_count=0;
}
static void assert_clean(struct anlogic_dev *dev)
{
    assert(dev->engines_num==0 && dev->mask_irq_h2c==0 && dev->mask_irq_c2h==0);
    assert(allocations==frees);
    for(int i=0;i<4;i++) {
        assert(!dev->engine_h2c[i].magic && !dev->engine_c2h[i].magic);
        assert(!dev->engine_h2c[i].resources && !dev->engine_c2h[i].resources);
        assert(!dev->engine_h2c[i].worker_attached && !dev->engine_c2h[i].worker_attached);
    }
}
int main(void)
{
    struct anlogic_dev dev; u32 bar[0x4000/4]; int cases=0, failures=0;
    for(poll_mode=0;poll_mode<=1;poll_mode++) for(int h=0;h<=3;h++) for(int c=0;c<=3;c++) {
        prepare(&dev,bar,h,c,-1,0);
        int rv=probe_engines(&dev);
        assert(rv==((h+c)?0:-ENODEV));
        if(h+c) {
            assert(dev.h2c_channel_max==h && dev.c2h_channel_max==c && dev.engines_num==h+c);
            /* Exercise the exact helper used by error rollback to clean fixtures. */
            for(int i=c-1;i>=0;i--) engine_init_rollback(&dev,&dev.engine_c2h[i]);
            for(int i=h-1;i>=0;i--) engine_init_rollback(&dev,&dev.engine_h2c[i]);
        } else assert(dev.h2c_channel_max==0 && dev.c2h_channel_max==0);
        assert_clean(&dev); cases++;
        for(int fi=0;fi<h+c;fi++) for(int fs=1;fs<=5;fs++) {
            if((fs==2 && !poll_mode) || (fs==3 && fi<h)) continue;
            prepare(&dev,bar,h,c,fi,fs);
            rv=probe_engines(&dev);
            assert(rv==(fs==4?-EIO:(fs==5?-EINVAL:-ENOMEM)));
            assert(dev.h2c_channel_max==0 && dev.c2h_channel_max==0);
            assert_clean(&dev);
            assert(drain_count==fi+1);
            /* Failed partial first, then all earlier engines in reverse order. */
            for(int i=0;i<drain_count;i++) assert(drained[i]==fi-i);
            failures++; cases++;
        }
    }
    printf("PASS PROBE_ROLLBACK_C cases=%d injected_failures=%d\n",cases,failures);
    return 0;
}
'''


def main():
    source = LIB.read_text(encoding='utf-8')
    names = ('engine_init_rollback', 'engine_init', 'probe_for_engine',
             'engine_destroy', 'probe_engines')
    out = ROOT / 'evidence' / 'driver_probe07_hostcheck'
    out.mkdir(exist_ok=True)
    cfile = out / 'probe_rollback_hostcheck.c'
    cfile.write_text(PRELUDE + '\n\n'.join(function(source, n) for n in names)
                     + TESTS, encoding='utf-8')
    executable = out / 'probe_rollback_hostcheck.exe'
    compiler = 'C:/MinGW/bin/gcc.exe'
    build = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            '-O2', str(cfile), '-o', str(executable)],
                           capture_output=True, text=True)
    (out / 'compile.log').write_text(build.stdout + build.stderr, encoding='utf-8')
    if build.returncode:
        print(build.stdout + build.stderr)
        return build.returncode
    run = subprocess.run([str(executable)], capture_output=True, text=True)
    (out / 'selfcheck.log').write_text(run.stdout + run.stderr, encoding='utf-8')
    print(run.stdout + run.stderr)
    if run.returncode or 'PASS PROBE_ROLLBACK_C' not in run.stdout:
        return run.returncode or 1
    report = {'status': 'PASS_HOST_C_MOCKS', 'source_sha256': hashlib.sha256(LIB.read_bytes()).hexdigest(),
              'actual_functions_compiled': list(names), 'compiler': compiler,
              'compile_returncode': build.returncode, 'run_returncode': run.returncode,
              'result': run.stdout.strip(),
              'limitations': 'Mock MMIO/allocations/locks/thread drain; not kernel build, concurrency or PCIe quiescence proof.'}
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
