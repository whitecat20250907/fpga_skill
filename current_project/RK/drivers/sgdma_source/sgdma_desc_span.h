#ifndef SGDMA_DESC_SPAN_H
#define SGDMA_DESC_SPAN_H
/* Caller confirms real hardware idle before a wrap can reuse the ring head.
 * A fitting AXI-ST request must remain one contiguous descriptor chain. */
static inline int sgdma_desc_contiguous_span(unsigned int index,
        unsigned int requested, unsigned int capacity, bool idle,
        unsigned int *start)
{
    if (!start || !capacity || !requested || index >= capacity || requested > capacity)
        return -EINVAL;
    if (requested <= capacity - index) { *start = index; return 0; }
    if (!idle) return -EBUSY;
    *start = 0;
    return 0;
}
#endif
