# 驱动审计候选补丁摘要

候选源码已经写入独立工程，原厂例程不动；以下是便于复核的核心改法，完整上下文以实际文件为准。

## SG 映射

~~~c
nents = dma_map_sg(&sgdev->pdev->dev, sg, sgt->orig_nents, dir);
if (!nents)
        return -EIO;
sgt->nents = nents;
~~~

sgdma_init_request 按 sgt->nents 迭代，transfer_destroy / unmap_sgl 按 orig_nents 解映射。不要将 mapped nents 写入 orig_nents。

## Streaming 租约

~~~c
/* engine->lock 下，禁止已拥有或有未完成描述符的通道被抢占。 */
spin_lock_irqsave(&engine->lock, flags);
if (engine->device_open || !list_empty(&engine->transfer_list) ||
    sgdma_device_flag_check(engine->sgdev, XDEV_FLAG_OFFLINE)) {
        ret = -EBUSY;
} else {
        engine->device_open = 1;
        if (engine->streaming && engine->dir == DMA_FROM_DEVICE)
                engine->eop_flush = !!eop_flush;
}
spin_unlock_irqrestore(&engine->lock, flags);
~~~

V4L2 的 C2H lease 覆盖 start→worker→stop，而不是一笔 xfer。streaming 字符 H2C/C2H 覆盖 open→release。同一方向同一通道不能多人消费/生产；不同方向正常并发。V4L2 start 失败要 release，仅成功 claim 的实例可 release。

## STREAMON 尺寸保护

~~~c
if (hw_mode != mdev->cam_mode || hw_width != mdev->width ||
    hw_height != mdev->height || hw_padded != mdev->read_size ||
    mdev->read_size != mdev->pixel_bytes) {
        ret = -EINVAL;
        goto fail_return_bufs;
}
~~~

S_FMT 在 buffers 分配后返回 -EBUSY；需 REQBUFS(0) 才能切换。setup 的 BAR 初始化在加载 V4L2 前完成。后续改善可令空闲 S_FMT 总写所选模式，以便相同缓存格式也能恢复外部 BAR 误操作。

## 错误与退出

DMA worker 用 READ_ONCE / WRITE_ONCE 共享 streaming。3 次连续意外 DMA 负返回触发 vb2_queue_error并退出，累计 dma_errors 独立于 rejected short packets。STREAMOFF 的停止中断不当作运行错误，stop 要等待 worker 后才放开 lease。

全图工具已改为 atomic failed/stop、SIGINT/SIGTERM handler、先 open 两路 DMA 后改 BAR、统一 cleanup。工具既要恢复 A4/20/CTRL，也需要 FPGA 让 CTRL soft reset 实际清空回环 FIFO；主任务已补独立 loop_reset_n。终止测试后必须再验首帧，避免旧 FIFO bytes 混入。

## Boot 补丁

- source.resolve()==dest.resolve() 明确拒绝。
- FIT payload 不能超出镜像或与 FIT metadata 重叠。
- 遇到实际非空 signature/value，拒绝仅更新内容 hash。
- before_present/after_present 区分无值属性被删除与未变化。
- 当前已验 boot 的 signature 节点没有 value，不应宣称完成密码学签名校验。
