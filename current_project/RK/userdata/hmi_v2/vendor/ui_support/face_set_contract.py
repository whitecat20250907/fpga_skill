"""Optional same-inference face collection. No model, capture, socket or file I/O."""
import json
import math
import os
from pathlib import Path
import sys

SCHEMA = 'EXISTING_FACE_SET_V1'
MAX_BODY = 30976  # Existing publisher adds its own session/boot/sequence envelope.
GEOMETRY_FIELDS = ('version','kind','timestamp_ns','sequence','source','coordinates',
                   'valid','capture_sequence','groups','size','landmarks','eye_left',
                   'eye_right','eye_left_ear','eye_right_ear')


def _uuid(value):
    return isinstance(value,str) and len(value)==32 and all(c in '0123456789abcdef' for c in value)


def current_model_session(aligner_class):
    """Reuse the loaded runtime UUID; never mint an independent face UUID."""
    runtime=sys.modules.get('gaze_runtime')
    app=os.environ.get('GAZE_APP_DIR')
    if runtime is None or not app or getattr(runtime,'MediaPipeFaceAlignment',None) is not aligner_class:
        raise ValueError('model_runtime_identity')
    if Path(runtime.__file__).resolve()!=Path(app,'gaze_runtime.py').resolve():
        raise ValueError('model_runtime_path')
    instance=getattr(runtime,'UI_SOURCE_INSTANCE',None)
    if not _uuid(instance):raise ValueError('model_session_unavailable')
    return instance


def unavailable(packet,reason):
    return dict(packet,face_set=dict(schema=SCHEMA,valid=False,reason=reason,faces=[]))


def extend_face_packet(packet,face,timestamp,sequence,encode,model_session):
    """Keep all legacy primary fields; encode only the one additional geometry.

    faces[0].geometry_ref points to the outer packet to avoid sending the primary
    478 points twice. Invalid extension preserves the original primary packet.
    """
    try:
        if not _uuid(model_session):raise ValueError('model_session_unavailable')
        capture=getattr(face,'capture_sequence',None)
        if type(timestamp) is not int or type(capture) is not int or not 0<=capture<2**32:
            raise ValueError('capture_identity')
        if packet.get('timestamp_ns')!=timestamp or packet.get('capture_sequence')!=capture:
            raise ValueError('primary_packet_identity')
        extra=list(getattr(face,'additional_faces',[]))
        if len(extra)>1:raise ValueError('face_capacity')
        source=[face]+extra if getattr(face,'status',False) else []
        if extra and not source:raise ValueError('additional_without_primary')
        faces=[];ids=set()
        for index,person in enumerate(source):
            key=getattr(person,'track_id',None)
            if type(key) is not int or not 0<key<0xffffffff or key in ids:
                raise ValueError('face_track_identity')
            if (type(getattr(person,'timestamp',None)) is not int or person.timestamp!=timestamp
                    or type(getattr(person,'capture_sequence',None)) is not int or person.capture_sequence!=capture):
                raise ValueError('mixed_face_frame')
            ids.add(key)
            row=dict(track_id=key,timestamp_ns=timestamp,capture_sequence=capture)
            if index==0:row['geometry_ref']='primary'
            else:
                geometry=encode(person,timestamp,sequence)
                if geometry.get('timestamp_ns')!=timestamp or geometry.get('capture_sequence')!=capture:
                    raise ValueError('additional_packet_identity')
                row['geometry']={k:geometry[k] for k in GEOMETRY_FIELDS if k in geometry}
            faces.append(row)
        extension=dict(schema=SCHEMA,valid=True,model_source_instance=model_session,
                       timestamp_ns=timestamp,capture_sequence=capture,
                       primary_track_id=faces[0]['track_id'] if faces else None,
                       faces=faces,track_ids_are_person_identity=False)
        result=dict(packet,face_set=extension)
        if len(json.dumps(result,separators=(',',':'),allow_nan=False).encode())>MAX_BODY:
            raise ValueError('face_packet_budget')
        return result
    except (ValueError,TypeError,AttributeError,KeyError,OverflowError) as error:
        return unavailable(packet,str(error))


def _geometry(value,timestamp,capture):
    if type(value.get('timestamp_ns')) is not int or type(value.get('capture_sequence')) is not int:
        raise ValueError('face_geometry_identity_type')
    if (value.get('kind'),value.get('version'),value.get('timestamp_ns'),value.get('capture_sequence'))!=('face',1,timestamp,capture):
        raise ValueError('face_geometry_identity')
    if type(value.get('valid')) is not bool:raise ValueError('face_geometry_valid')
    if value['valid']:
        points=value.get('landmarks');size=value.get('size')
        if not isinstance(points,list) or len(points) not in (468,478):raise ValueError('face_geometry_shape')
        if not isinstance(size,list) or len(size)!=2 or any(type(v) is not int or v<=0 for v in size):raise ValueError('face_geometry_size')
        if value.get('coordinates')!='image_xy_normalized_z_width':raise ValueError('face_geometry_coordinates')
        for row in points:
            if not isinstance(row,list) or len(row)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>100 for v in row):
                raise ValueError('face_geometry_points')
        if any(max(p[a] for p in points)-min(p[a] for p in points)<=1e-6 for a in (0,1)):
            raise ValueError('face_geometry_degenerate')
        for key in ('eye_left','eye_right'):
            value_metric=value.get(key)
            if type(value_metric) not in (int,float) or not math.isfinite(value_metric):raise ValueError('face_eye_metric')
        for key in ('eye_left_ear','eye_right_ear'):
            metric=value.get(key)
            if metric is not None and (type(metric) not in (int,float) or not math.isfinite(metric) or metric<0):
                raise ValueError('face_eye_ear')
        groups=value.get('groups',{})
        if set(groups)!={'head','left_eye','right_eye','left_iris','right_iris'} or any(type(v) is not bool for v in groups.values()) or not groups['head']:
            raise ValueError('face_geometry_groups')
        for side in ('left','right'):
            if groups[side+'_iris'] and (not groups[side+'_eye'] or len(points)!=478):raise ValueError('face_iris_group')
    return {k:value[k] for k in GEOMETRY_FIELDS if k in value}


def expand_face_set(packet,*,now_ns,expected_model_session,people_packet=None):
    """New relay API after its existing FeatureState validation.

    expected_model_session must be bound to the current owned runtime, never
    learned from this untrusted packet. Optional people join requires an exact
    session, timestamp, capture sequence and track match; no nearest-frame join.
    """
    if not _uuid(expected_model_session):raise ValueError('owned_model_session_required')
    stamp=packet.get('timestamp_ns');capture=packet.get('capture_sequence');group=packet.get('face_set',{})
    if type(stamp) is not int or type(now_ns) is not int or not 0<=now_ns-stamp<=350_000_000:
        raise ValueError('face_set_stale')
    if type(capture) is not int or not 0<=capture<2**32:raise ValueError('capture_identity')
    if group.get('schema')!=SCHEMA or group.get('valid') is not True:raise ValueError('face_set_unavailable')
    if (type(group.get('timestamp_ns')) is not int or type(group.get('capture_sequence')) is not int
            or (group.get('model_source_instance'),group.get('timestamp_ns'),group.get('capture_sequence'))!=(expected_model_session,stamp,capture)):
        raise ValueError('face_set_identity')
    rows=group.get('faces')
    if not isinstance(rows,list) or len(rows)>2:raise ValueError('face_capacity')
    out=[];ids=set()
    for index,row in enumerate(rows):
        key=row.get('track_id')
        if type(key) is not int or not 0<key<0xffffffff or key in ids:raise ValueError('face_track_identity')
        if (type(row.get('timestamp_ns')) is not int or type(row.get('capture_sequence')) is not int
                or row.get('timestamp_ns')!=stamp or row.get('capture_sequence')!=capture):raise ValueError('mixed_face_frame')
        ids.add(key)
        if index==0:
            if row.get('geometry_ref')!='primary' or 'geometry' in row or key!=packet.get('selected_track_id'):
                raise ValueError('primary_geometry_reference')
            geometry=packet
        else:
            if 'geometry_ref' in row:raise ValueError('additional_geometry_reference')
            geometry=row.get('geometry',{})
        item=_geometry(geometry,stamp,capture)
        item.update(track_id=key,model_source_instance=expected_model_session)
        out.append(item)
    if group.get('primary_track_id')!=(out[0]['track_id'] if out else None):raise ValueError('primary_track_identity')
    if people_packet is not None:
        if (people_packet.get('source_instance'),people_packet.get('timestamp_ns'),people_packet.get('capture_sequence'),people_packet.get('primary_track_id'))!=(expected_model_session,stamp,capture,group.get('primary_track_id')):
            raise ValueError('gaze_people_identity')
        people=people_packet.get('people',[])
        keys=[person.get('track_id') for person in people]
        if len(keys)!=len(set(keys)) or set(keys)!=ids:raise ValueError('gaze_people_tracks')
    return out
