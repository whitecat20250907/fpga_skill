/*
 * This file is part of the Anlogic DMA IP Core driver for Linux
 *
 * Copyright (c) 2020-present,  anlogic, Inc.
 * All rights reserved.
 *
 * This source code is free software; you can redistribute it and/or modify it
 * under the terms and conditions of the GNU General Public License,
 * version 2, as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
 * more details.
 *
 * The full GNU General Public License is included in this distribution in
 * the file called "COPYING".
 */

#define pr_fmt(fmt) KBUILD_MODNAME ":%s: " fmt, __func__

#include "anlogic_thread.h"

#include <linux/kernel.h>
#include <linux/slab.h>


/* ********************* global variables *********************************** */
static struct sgdma_kthread *cs_threads;
static unsigned int thread_cnt;


/* ********************* static function definitions ************************ */
/* The work-list lock is acquired before engine->lock whenever both are needed. */
static int sgdma_thread_cmpl_status_pend(struct list_head *work_item)
{
    struct anlogic_dma_engine *engine = list_entry(work_item,
                            struct anlogic_dma_engine, cmplthp_list);
    unsigned long flags;
    int pend;

    spin_lock_irqsave(&engine->lock, flags);
    pend = !engine->poll_removing && engine->running &&
           (engine->cyclic_req || !list_empty(&engine->transfer_list));
    spin_unlock_irqrestore(&engine->lock, flags);
    return pend;
}

static int sgdma_thread_cmpl_status_proc(struct list_head *work_item)
{
    struct anlogic_dma_engine *engine = list_entry(work_item,
                            struct anlogic_dma_engine, cmplthp_list);
    unsigned long flags;
    u64 generation;
    u32 expected = 0;

    /* Copy only scalars while the transfer head is protected by its lock. */
    spin_lock_irqsave(&engine->lock, flags);
    if (engine->poll_removing || !engine->running ||
        (!engine->cyclic_req && list_empty(&engine->transfer_list))) {
        spin_unlock_irqrestore(&engine->lock, flags);
        return 0;
    }
    if (!engine->cyclic_req) {
        struct sgdma_transfer *head = list_first_entry(&engine->transfer_list,
                                                     struct sgdma_transfer, entry);
        expected = head->desc_cmpl_th;
    }
    generation = engine->poll_generation;
    spin_unlock_irqrestore(&engine->lock, flags);
    return engine_service_poll_generation(engine, expected, generation);
}

/* Caller holds thp->lock. Lease one engine, then rotate it for fairness.
 * No next/list pointer survives across fproc or concurrent engine removal. */
static struct anlogic_dma_engine *xthread_take_work(struct sgdma_kthread *thp)
{
    struct anlogic_dma_engine *engine;
    unsigned long flags;

    list_for_each_entry(engine, &thp->work_list, cmplthp_list) {
        spin_lock_irqsave(&engine->lock, flags);
        if (!engine->poll_removing && engine->running &&
            (engine->cyclic_req || !list_empty(&engine->transfer_list))) {
            engine->poll_worker_active++;
            spin_unlock_irqrestore(&engine->lock, flags);
            list_move_tail(&engine->cmplthp_list, &thp->work_list);
            return engine;
        }
        spin_unlock_irqrestore(&engine->lock, flags);
    }
    return NULL;
}

static inline void xthread_reschedule(struct sgdma_kthread *thp)
{
    if (thp->timeout) {
        pr_debug_thread("%s rescheduling for %u seconds",
                thp->name, thp->timeout);
        wait_event_interruptible_timeout(thp->waitq,
                          READ_ONCE(thp->schedule) || kthread_should_stop(),
                          msecs_to_jiffies(thp->timeout));
    } else {
        pr_debug_thread("%s rescheduling", thp->name);
        wait_event_interruptible(thp->waitq,
                                 READ_ONCE(thp->schedule) || kthread_should_stop());
    }
}

static int xthread_main(void *data)
{
    struct sgdma_kthread *thp = (struct sgdma_kthread *)data;

    pr_debug_thread("%s UP.\n", thp->name);

    disallow_signal(SIGPIPE);

    if (thp->finit)
        thp->finit(thp);

    while (!kthread_should_stop()) {
        struct anlogic_dma_engine *engine;
        unsigned long flags;

        lock_thread(thp);
        WRITE_ONCE(thp->schedule, 0);
        engine = xthread_take_work(thp);
        unlock_thread(thp);
        if (!engine) {
            xthread_reschedule(thp);
            continue;
        }

        /* remove_work waits for this lease before freeing engine/WB memory. */
        thp->fproc(&engine->cmplthp_list);
        spin_lock_irqsave(&engine->lock, flags);
        engine->poll_worker_active--;
        if (!engine->poll_worker_active)
            wake_up_all(&engine->poll_idle_wq);
        spin_unlock_irqrestore(&engine->lock, flags);
        /* Do not access engine after returning its final lifetime lease. */
        cond_resched();
    }

    pr_debug_thread("%s, work done.\n", thp->name);

    if (thp->fdone)
        thp->fdone(thp);

    pr_debug_thread("%s, exit.\n", thp->name);
    return 0;
}


int sgdma_kthread_start(struct sgdma_kthread *thp, char *name, int id)
{
    int len;
    int node;

    if (thp->task) {
        pr_warn("kthread %s task already running?\n", thp->name);
        return -EINVAL;
    }

    len = snprintf(thp->name, sizeof(thp->name), "%s%d", name, id);
    if (len < 0) {
        pr_err("thread %d, error in snprintf name %s.\n", id, name);
        return -EINVAL;
    }

    thp->id = id;

    spin_lock_init(&thp->lock);
    INIT_LIST_HEAD(&thp->work_list);
    init_waitqueue_head(&thp->waitq);

    node = cpu_to_node(thp->cpu);
    pr_debug("node : %d\n", node);

    thp->task = kthread_create_on_node(xthread_main, (void *)thp,
                    node, "%s", thp->name);
    if (IS_ERR(thp->task)) {
        pr_err("kthread %s, create task failed: 0x%lx\n",
            thp->name, (unsigned long)IS_ERR(thp->task));
        thp->task = NULL;
        return -EFAULT;
    }

    kthread_bind(thp->task, thp->cpu);

    pr_debug_thread("kthread 0x%p, %s, cpu %u, task 0x%p.\n",
        thp, thp->name, thp->cpu, thp->task);

    wake_up_process(thp->task);
    return 0;
}

int sgdma_kthread_stop(struct sgdma_kthread *thp)
{
    int rv;

    if (!thp->task) {
        pr_debug_thread("kthread %s, already stopped.\n", thp->name);
        return 0;
    }

    WRITE_ONCE(thp->schedule, 1);
    wake_up_interruptible(&thp->waitq);
    rv = kthread_stop(thp->task);
    if (rv < 0) {
        pr_warn("kthread %s, stop err %d.\n", thp->name, rv);
        return rv;
    }

    pr_debug_thread("kthread %s, 0x%p, stopped.\n", thp->name, thp->task);
    thp->task = NULL;

    return 0;
}



void sgdma_thread_remove_work(struct anlogic_dma_engine *engine)
{
    struct sgdma_kthread *cmpl_thread;
    unsigned long flags;

    /* Release engine->lock before taking the work-list lock: same order as
     * xthread_take_work. Invalidate any worker that already owns a lease. */
    spin_lock_irqsave(&engine->lock, flags);
    engine->poll_removing = true;
    engine->poll_generation++;
    cmpl_thread = engine->cmplthp;
    engine->cmplthp = NULL;
    spin_unlock_irqrestore(&engine->lock, flags);

    if (cmpl_thread) {
        lock_thread(cmpl_thread);
        list_del_init(&engine->cmplthp_list);
        cmpl_thread->work_cnt--;
        unlock_thread(cmpl_thread);
    }
    wait_event(engine->poll_idle_wq, !READ_ONCE(engine->poll_worker_active));
    /* The counter can reach zero before the worker releases engine->lock.
     * Wait for that final critical section, including its wake_up, to finish. */
    spin_lock_irqsave(&engine->lock, flags);
    spin_unlock_irqrestore(&engine->lock, flags);
}

void sgdma_thread_add_work(struct anlogic_dma_engine *engine)
{
    struct sgdma_kthread *thp = cs_threads;
    unsigned int v = 0;
    int i, idx = thread_cnt;
    unsigned long flags;


    /* Polled mode only */
    for (i = 0; i < thread_cnt; i++, thp++) {
        lock_thread(thp);
        if (idx == thread_cnt) {
            v = thp->work_cnt;
            idx = i;
        } else if (!thp->work_cnt) {
            idx = i;
            unlock_thread(thp);
            break;
        } else if (thp->work_cnt < v) {
            v = thp->work_cnt;
            idx = i;
        }
        unlock_thread(thp);
    }

    thp = cs_threads + idx;
    lock_thread(thp);
    list_add_tail(&engine->cmplthp_list, &thp->work_list);
    engine->intr_work_cpu = idx;
    thp->work_cnt++;
    unlock_thread(thp);

    pr_info("%s 0x%p assigned to cmpl status thread %s,%u.\n",
        engine->name, engine, thp->name, thp->work_cnt);


    spin_lock_irqsave(&engine->lock, flags);
    engine->poll_removing = false;
    engine->cmplthp = thp;
    spin_unlock_irqrestore(&engine->lock, flags);
}

int sgdma_threads_create(unsigned int num_threads)
{
    struct sgdma_kthread *thp;
    int rv;
    int cpu;

    if (thread_cnt) {
        pr_warn("threads already created!");
        return 0;
    }

    cs_threads = kzalloc(num_threads * sizeof(struct sgdma_kthread),
                    GFP_KERNEL);
    if (!cs_threads) {
        pr_err("OOM, # threads %u.\n", num_threads);
        return -ENOMEM;
    }

    /* N dma writeback monitoring threads */
    thp = cs_threads;
    for_each_online_cpu(cpu) {
        pr_debug("index %d cpu %d online\n", thread_cnt, cpu);
        thp->cpu = cpu;
        thp->timeout = 0;
        thp->fproc = sgdma_thread_cmpl_status_proc;
        thp->fpending = sgdma_thread_cmpl_status_pend;
        rv = sgdma_kthread_start(thp, "sgdma_poll_th", thread_cnt);
        if (rv < 0)
            goto cleanup_threads;

        thread_cnt++;
        if (thread_cnt == num_threads)
            break;
        thp++;
    }

    return 0;

cleanup_threads:
    /* Earlier kthreads are already live: join them before freeing cs_threads. */
    thp = cs_threads;
    for (cpu = 0; cpu < thread_cnt; cpu++, thp++)
        sgdma_kthread_stop(thp);
    kfree(cs_threads);
    cs_threads = NULL;
    thread_cnt = 0;

    return rv;
}

void sgdma_threads_destroy(void)
{
    int i;
    struct sgdma_kthread *thp;

    if (!thread_cnt)
        return;

    /* N dma writeback monitoring threads */
    thp = cs_threads;
    for (i = 0; i < thread_cnt; i++, thp++)
        if (thp->fproc)
            sgdma_kthread_stop(thp);

    kfree(cs_threads);
    cs_threads = NULL;
    thread_cnt = 0;
}
