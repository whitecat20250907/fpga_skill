
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
static void engine_init_rollback(struct anlogic_dev *sgdev,
				 struct anlogic_dma_engine *engine)
{
	if (engine->dir == DMA_TO_DEVICE)
		sgdev->mask_irq_h2c &= ~engine->irq_bitmask;
	else
		sgdev->mask_irq_c2h &= ~engine->irq_bitmask;
	engine_destroy(sgdev, engine);
}

static int engine_init(struct anlogic_dma_engine *engine, struct anlogic_dev *sgdev,
			   int offset, enum dma_data_direction dir, int channel)
{
	int rv;
	u32 val;

	dbg_init("channel %d, offset 0x%x, dir %d.\n", channel, offset, dir);

	engine->channel = channel;

	/* engine interrupt request bit */
	engine->irq_bitmask = (1 << SGDMA_ENG_IRQ_NUM) - 1;
	engine->irq_bitmask <<= (sgdev->engines_num * SGDMA_ENG_IRQ_NUM);
	engine->bypass_offset = sgdev->engines_num * BYPASS_MODE_SPACING;

	/* parent */
	engine->sgdev = sgdev;
	/* register address */
	engine->regs = (sgdev->bar[sgdev->config_bar_idx] + offset);
	engine->sgdma_regs = sgdev->bar[sgdev->config_bar_idx] + offset +
				 SGDMA_OFFSET_FROM_CHANNEL;
	val = read_register(&engine->regs->identifier);
	if (val & 0x8000U)
		engine->streaming = 1;

	/* remember SG DMA direction */
	engine->dir = dir;
	sprintf(engine->name, "%d-%s%d-%s", sgdev->idx,
		(dir == DMA_TO_DEVICE) ? "H2C" : "C2H", channel,
		engine->streaming ? "ST" : "MM");

	/* initialize the deferred work for transfer completion */
	INIT_WORK(&engine->work, engine_service_work);

	if (st_c2h_credit_enabled(engine))
			engine->desc_max = SGDMA_ENGINE_CREDIT_XFER_MAX_DESC;
	else
			engine->desc_max = SGDMA_ENGINE_XFER_MAX_DESC;

	dbg_init("engine %p name %s irq_bitmask=0x%08x\n", engine, engine->name,
		 (int)engine->irq_bitmask);
	if (engine->streaming && engine->dir == DMA_FROM_DEVICE)
		pr_info("%s init: st_c2h credit=%u force_wb=%u desc_max=%u.\n",
			engine->name, enable_st_c2h_credit, force_st_c2h_wb,
			engine->desc_max);

	if (dir == DMA_TO_DEVICE)
		sgdev->mask_irq_h2c |= engine->irq_bitmask;
	else
		sgdev->mask_irq_c2h |= engine->irq_bitmask;
	sgdev->engines_num++;

#if DESC_BYPASS
	if (val & 0x1000U) {
		engine->is_desc_bypass = 1;
		engine->desc_bypass_reg = sgdma_desc_bypass_reg(sgdev, channel, (dir == DMA_TO_DEVICE));
		engine->desc_max = DESCBYPASS_DESC_MAX;
		dbg_init("engine %p name %s is desc bypass, desc_max %u, register 0x%lx\n",
			 engine, engine->name, engine->desc_max, (ulong)engine->desc_bypass_reg);
	}
#endif

	rv = engine_alloc_resource(engine);
	if (rv)
		goto rollback;

	rv = engine_init_regs(engine);
	if (rv)
		goto rollback;

	/* Publish only fully initialized engines to normal teardown/clients. */
	engine->magic = MAGIC_ENGINE;
	if (poll_mode)
		sgdma_thread_add_work(engine);

	return 0;

rollback:
	/* engine_alloc_resource already frees allocations it never exposed to
	 * hardware. Remaining/programmed allocations are released only after
	 * the same physical STOP confirmation used by normal driver06 teardown. */
	engine_init_rollback(sgdev, engine);
	return rv;
}

static int probe_for_engine(struct anlogic_dev *sgdev, enum dma_data_direction dir,
				int channel)
{
	struct engine_regs *regs;
	int offset = channel * CHANNEL_SPACING;
	u32 engine_id_expected;
	u32 engine_id;
	u32 channel_id;
	struct anlogic_dma_engine *engine;
	int rv;

	/* register offset for the engine */
	/* read channels at 0x0000, write channels at 0x1000,
	 * channels at 0x100 interval
	 */
	if (dir == DMA_TO_DEVICE) {
		engine_id_expected = SGDMA_ID_H2C;
		engine = &sgdev->engine_h2c[channel];
	} else {
		offset += H2C_CHANNEL_OFFSET;
		engine_id_expected = SGDMA_ID_C2H;
		engine = &sgdev->engine_c2h[channel];
	}

	regs = sgdev->bar[sgdev->config_bar_idx] + offset;
	engine_id = get_engine_id(regs);
	channel_id = get_engine_channel_id(regs);

	if ((engine_id != engine_id_expected) || (channel_id != (u32)channel)) {
		dbg_init(
			"%s %d engine, reg off 0x%x, id mismatch 0x%x,0x%x,exp 0x%x,0x%x, SKIP.\n",
			dir == DMA_TO_DEVICE ? "H2C" : "C2H", channel, offset,
			engine_id, channel_id, engine_id_expected,
			channel_id != (u32)channel);
		/* End of implemented channels, distinct from initialization failure. */
		return -ENODEV;
	}

	dbg_init("found AXI %s %d engine, reg. off 0x%x.\n",
		 dir == DMA_TO_DEVICE ? "H2C" : "C2H", channel, offset);

	/* allocate and initialize engine */
	rv = engine_init(engine, sgdev, offset, dir, channel);
	if (rv != 0) {
		pr_info("failed to create AXI %s %d engine.\n",
			dir == DMA_TO_DEVICE ? "H2C" : "C2H", channel);
		return rv;
	}

	return 0;
}

static int engine_destroy(struct anlogic_dev *sgdev, struct anlogic_dma_engine *engine)
{
	unsigned long flags;

	if (!sgdev) {
		pr_err("Invalid sgdev\n");
		return -EINVAL;
	}

	if (!engine) {
		pr_err("dma engine NULL\n");
		return -EINVAL;
	}

	dbg_sg("Shutting down engine %s%d", engine->name, engine->channel);

	spin_lock_irqsave(&engine->lock, flags);
	engine->poll_removing = true;
	engine->dma_quiescing = true;
	engine_service_shutdown(engine);
	spin_unlock_irqrestore(&engine->lock, flags);

	/* Disable interrupts to stop processing new events during shutdown */
	write_register(0x0, &engine->regs->interrupt_enable_mask,
			   (unsigned long)(&engine->regs->interrupt_enable_mask) -
				   (unsigned long)(engine->regs));

	if (st_c2h_credit_enabled(engine)) {
		u32 reg_value = (0x1 << engine->channel) << 16;
		struct sgdma_common_regs *reg =
			(struct sgdma_common_regs *)(sgdev->bar[sgdev->config_bar_idx] +
					(0x6 * TARGET_SPACING));

		write_register(reg_value, &reg->credit_mode_enable_w1c,
			   (unsigned long)(&reg->credit_mode_enable_w1c) -
				   (unsigned long)(reg));
	}

	if (poll_mode)
		sgdma_thread_remove_work(engine);
	/* IRQ teardown precedes remove_engines; drain already queued IRQ work. */
	cancel_work_sync(&engine->work);
	engine_wait_stopped(engine);

	/* Release memory use for descriptor writebacks */
	engine_free_resource(engine);

	memset(engine, 0, sizeof(struct anlogic_dma_engine));
	/* Decrement the number of engines available */
	sgdev->engines_num--;

	return 0;
}

static int probe_engines(struct anlogic_dev *sgdev)
{
	int i;
	int rv;
	int h2c_count = 0, c2h_count = 0;

	if (!sgdev) {
		pr_err("Invalid sgdev\n");
		return -EINVAL;
	}

	/* iterate over channels */
	for (i = 0; i < sgdev->h2c_channel_max; i++) {
		rv = probe_for_engine(sgdev, DMA_TO_DEVICE, i);
		if (rv == -ENODEV)
			break;
		if (rv)
			goto rollback;
		h2c_count++;
	}

	for (i = 0; i < sgdev->c2h_channel_max; i++) {
		rv = probe_for_engine(sgdev, DMA_FROM_DEVICE, i);
		if (rv == -ENODEV)
			break;
		if (rv)
			goto rollback;
		c2h_count++;
	}
	if (!h2c_count && !c2h_count) {
		rv = -ENODEV;
		goto rollback;
	}
	sgdev->h2c_channel_max = h2c_count;
	sgdev->c2h_channel_max = c2h_count;

	return 0;

rollback:
	/* The failed partial engine was already rolled back by engine_init.
	 * Undo previously published engines in reverse initialization order.
	 * This joins their poll leases/deferred work before descriptors/WB free.
	 * Device-open cleanup then joins the global threads without double free. */
	for (i = c2h_count - 1; i >= 0; i--)
		engine_init_rollback(sgdev, &sgdev->engine_c2h[i]);
	for (i = h2c_count - 1; i >= 0; i--)
		engine_init_rollback(sgdev, &sgdev->engine_h2c[i]);
	sgdev->h2c_channel_max = 0;
	sgdev->c2h_channel_max = 0;
	return rv;
}
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
