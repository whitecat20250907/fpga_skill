from console.comparison import Comparison, cpu_percent


def inputs(now, serial=100, packets=200, epoch=1, error=0):
    return {'sys.metrics.fpga-io': dict(src_ns=now,epoch=epoch,instance='owner',ok=True,
            native=dict(serial=serial,display=dict(accepted_packets=packets,crc_errors=error,format_errors=0,sequence_errors=0))),
            'frame.meta':dict(src_ns=now-10_000_000,epoch=epoch)}


def reader(path):
    return 'cpu 100 0 100 800 0 0 0 0\n' if path=='/proc/stat' else 'NPU load: Core0: 12%, Core1: 0%'


def test_actual_counter_deltas_and_missing_power():
    c=Comparison();a=c.sample(inputs(1_000_000_000),1_000_000_000,reader)
    assert a['model_hz'] is None and a['cpu_percent'] is None
    b=c.sample(inputs(2_000_000_000,140,245,error=2),2_000_000_000,reader)
    assert b['model_hz']==40 and b['display_packet_hz']==45
    assert b['display_error_delta']==2 and b['frame_age_ms']==10
    assert b['npu_percent']=={'0':12.,'1':0.}
    assert b['power_w'] is None and b['fpga_utilization'] is None


def test_stale_and_new_epoch_do_not_splice_rates():
    c=Comparison();c.sample(inputs(1_000_000_000),1_000_000_000,reader)
    b=c.sample(inputs(1_000_000_000),4_000_000_001,reader)
    assert not b['online'] and b['model_hz'] is None and b['frame_age_ms'] is None
    b=c.sample(inputs(6_000_000_000,2,3,epoch=2),6_000_000_000,reader)
    assert b['model_hz'] is None and b['display_error_delta'] is None
    b=c.sample(inputs(7_000_000_000,42,43,epoch=3),7_000_000_000,reader)
    assert b['model_hz'] is None


def test_missing_files_are_unknown_not_zero_and_sampling_is_bounded():
    def missing(_):raise OSError('unavailable')
    c=Comparison();b=c.sample({},1_000_000_000,missing)
    assert b['cpu_percent'] is None and b['npu_percent']=={}
    assert c.sample({},1_000_000_001,lambda _:1/0) is b


def test_cpu_denominator_and_counter_reset():
    assert cpu_percent([0]*8,[10,0,10,70,10,0,0,0])==20
    assert cpu_percent([10]*8,[0]*8) is None
    c=Comparison();c.sample(inputs(1_000_000_000),1_000_000_000,reader)
    b=c.sample(inputs(2_000_000_000,1,2),2_000_000_000,reader)
    assert b['model_hz'] is None and b['display_packet_hz'] is None
