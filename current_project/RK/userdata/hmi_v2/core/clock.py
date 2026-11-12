from time import monotonic_ns

def fresh(stamp, ttl_ms, now=None):
    now = monotonic_ns() if now is None else now
    return type(stamp) is int and 0 < stamp <= now and now-stamp <= ttl_ms*1_000_000

def age_ms(stamp, now=None):
    now = monotonic_ns() if now is None else now
    return (now-stamp)/1e6 if type(stamp) is int and 0 < stamp <= now else None
