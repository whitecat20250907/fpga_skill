"""Bind existing loopback publishers to the actual generation's child PIDs.

The owner supplies a fresh private binding after starting its original model
and hand children. A packet never supplies its own trusted owner/capture token.
"""
import copy
import json
import os
from pathlib import Path


def identity(pid):
    parts=(Path('/proc')/str(pid)/'stat').read_text().rpartition(')')[2].split()
    return dict(pid=pid,start_ticks=int(parts[19]))


def exact_identity(value):
    if not isinstance(value,dict) or set(value)!={'pid','start_ticks'} or any(type(v) is not int or v<=0 for v in value.values()):
        raise ValueError('exact positive process identity')
    return dict(value)


def bounded_bytes(path,maximum=131072):
    path=Path(path)
    if not path.is_absolute() or path.is_symlink():raise ValueError('absolute non-symlink source file')
    with path.open('rb') as stream:raw=stream.read(maximum+1)
    if len(raw)>maximum:raise ValueError('bounded source file')
    return raw


def json_object(raw):
    try:value=json.loads(raw)
    except RecursionError as exc:raise ValueError('source JSON nesting exceeded') from exc
    if not isinstance(value,dict):raise ValueError('source object')
    return value


def read_json(path,maximum=131072):
    return json_object(bounded_bytes(path,maximum))


def owns_udp(pid,port):
    """Exact /proc socket inode + peer source port; no anonymous first-packet bind."""
    sockets=set()
    for fd in (Path('/proc')/str(pid)/'fd').iterdir():
        try:target=os.readlink(fd)
        except FileNotFoundError:continue
        if target.startswith('socket:[') and target.endswith(']'):sockets.add(target[8:-1])
    for line in Path('/proc/net/udp').read_text().splitlines()[1:]:
        fields=line.split();address,local_port=fields[1].split(':')
        if int(local_port,16)==port and address in ('00000000','0100007F') and fields[9] in sockets:return True
    return False


class OwnedProducers:
    def __init__(self,path,*,boot_id,controller,read_identity=identity,udp_owner=owns_udp,reader=read_json):
        self.path=Path(path);self.boot_id=boot_id;self.controller=exact_identity(controller)
        self.read_identity,self.udp_owner,self.reader=read_identity,udp_owner,reader
        self.binding=None;self.publisher_sources={};self.model_session=None
        self.last_check_ns=0

    def refresh(self,now_ns):
        if self.binding is not None and now_ns-self.last_check_ns<100_000_000:return self.binding
        if self.read_identity(self.controller['pid'])!=self.controller:raise ValueError('controller process changed')
        b=self.reader(self.path)
        if b.get('schema')!='APP_UI_PRODUCERS_V1' or b.get('boot_id')!=self.boot_id or b.get('controller')!=self.controller:
            raise ValueError('owned generation binding')
        for key in ('owner_generation','capture_session'):
            if not isinstance(b.get(key),str) or not b[key]:raise ValueError('owned source context')
        for key in ('main','hand','capture'):
            expected=exact_identity(b[key])
            if self.read_identity(expected['pid'])!=expected:raise ValueError(key+' process changed')
        if type(b.get('not_before_ns')) is not int or not 0<b['not_before_ns']<=now_ns:raise ValueError('generation source boundary')
        root=Path(b['generation_directory'])
        if not root.is_absolute():raise ValueError('generation directory')
        for key in ('people_path','filtered_path'):
            path=Path(b[key])
            # Existing exporters use exact per-model-PID tmpfs names. Their
            # current runtime UUID and monotonic start boundary are also checked;
            # a directory glob or an arbitrary previous export is not accepted.
            basename='gaze_npu_people_' if key=='people_path' else 'gaze_ui_filtered_'
            original=Path('/dev/shm')/(basename+str(b['main']['pid'])+'.json')
            if not path.is_absolute() or path.is_symlink() or (root.resolve() not in path.resolve().parents and path!=original):
                raise ValueError('source export outside owned generation')
        if self.binding is not None and b!=self.binding:raise ValueError('live generation binding changed')
        self.binding=copy.deepcopy(b);self.last_check_ns=now_ns
        return b

    def _fresh_file(self,key,now_ns):
        b=self.refresh(now_ns);p=self.reader(b[key]);stamp=p.get('timestamp_ns')
        if type(stamp) is not int or not b['not_before_ns']<=stamp<=now_ns or now_ns-stamp>350_000_000:
            raise ValueError('owned source export expired')
        source=p.get('source_instance')
        if not isinstance(source,str) or len(source)!=32 or any(c not in '0123456789abcdef' for c in source):
            raise ValueError('owned model source UUID')
        if self.model_session is None:
            if key!='people_path':raise ValueError('model source handshake not ready')
            self.model_session=source
        if source!=self.model_session:raise ValueError('owned runtime source changed')
        return p

    def people(self,now_ns):
        return self._fresh_file('people_path',now_ns)

    def filtered(self,now_ns):
        p=self._fresh_file('filtered_path',now_ns)
        if p.get('kind')!='filtered_gaze_ui' or p.get('version')!=1:raise ValueError('filtered export schema')
        return self.attach_context(p)

    def attach_context(self,packet):
        if self.binding is None:raise ValueError('source binding not ready')
        return dict(packet,owner_generation=self.binding['owner_generation'],capture_session=self.binding['capture_session'])

    def accept_peer(self,packet,peer,now_ns,*,commit=True):
        b=self.refresh(now_ns);kind=packet.get('kind')
        if kind not in ('face','hand') or peer[0]!='127.0.0.1' or type(peer[1]) is not int:raise ValueError('local source peer')
        if packet.get('boot_id')!=self.boot_id:raise ValueError('source boot')
        stamp=packet.get('timestamp_ns')
        if type(stamp) is not int or not b['not_before_ns']<=stamp<=now_ns:raise ValueError('source predates generation')
        pid=b['main' if kind=='face' else 'hand']['pid']
        if not self.udp_owner(pid,peer[1]):raise ValueError('publisher socket not owned by actual child')
        source=packet.get('source_instance')
        if kind in self.publisher_sources and self.publisher_sources[kind]!=source:raise ValueError('publisher UUID changed')
        if not isinstance(source,str) or len(source)!=32 or any(c not in '0123456789abcdef' for c in source):raise ValueError('publisher UUID')
        if commit:self.commit_peer(packet)
        return self.attach_context(packet)

    def commit_peer(self,packet):
        """Call only after the original FeatureState accepted the entire body."""
        kind,source=packet['kind'],packet['source_instance']
        if kind in self.publisher_sources and self.publisher_sources[kind]!=source:raise ValueError('publisher UUID changed before commit')
        self.publisher_sources[kind]=source
