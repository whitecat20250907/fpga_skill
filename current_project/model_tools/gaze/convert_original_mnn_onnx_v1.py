"""Static batch-1 translation of the inspected original graph, never substitute weights.

All MNN shape/rank subgraphs must resolve exactly from original fixed inputs.
Numeric equivalence remains a separate MNN/ONNX execution gate.
"""
import argparse,collections,hashlib,json,math
from pathlib import Path
import numpy as np
import onnx
from onnx import helper as H,numpy_helper as NH,TensorProto as T
M=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
assert args.attempt.startswith('ONNX_conversion_v') and args.attempt.removeprefix('ONNX_conversion_v').isdigit()
O=M/'evidence'/args.attempt;O.mkdir(exist_ok=False)
gp=M/'evidence/MNN_graph_v2/result.json';cp=M/'evidence/MNN_constants_v2/result.json';g=json.loads(gp.read_text());c=json.loads(cp.read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(c['archive']['path'])==c['archive']['sha256'] and sha(g['model']['path'])==g['model']['sha256']
weights=np.load(c['archive']['path'],allow_pickle=False)
shapes={};values={};names={};nodes=[];initializers=[];inputs=[];trace=[];folded=collections.Counter();counter=0
def init(a,label):
 global counter
 counter+=1;n=f'{label}_{counter}';initializers.append(NH.from_array(np.asarray(a),n));return n
def tensor(i):
 if i not in names:names[i]=init(values[i],f'constant_t{i}')
 return names[i]
def emit(kind,ins,out,**attrs):nodes.append(H.make_node(kind,ins,[out],name=f'n{len(nodes)}_{kind}',**attrs))
def known(i):return values[i]
def ints(i):return [int(x) for x in known(i).reshape(-1)]
def reshape_shape(shape,dims):
 dims=[shape[i] if d==0 else d for i,d in enumerate(dims)];assert dims.count(-1)<=1
 if -1 in dims:dims[dims.index(-1)]=math.prod(shape)//(-math.prod(dims))
 assert math.prod(dims)==math.prod(shape) and all(d>=0 for d in dims);return tuple(dims)
def dims_slice(shape,start,end,steps):
 return tuple(len(range(d)[slice(start[i],end[i],steps[i])]) if i<len(start) else d for i,d in enumerate(shape))
for n,op in enumerate(g['network']['oplists']):
 typ=op['type']['name'];p=op['main']['fields'] if op['main'] else {};ii=op['inputIndexes'] or [];oo=op['outputIndexes'];assert len(oo)==1;out=oo[0];name=f't{out}';names[out]=name
 try:
  if typ=='Input':
   assert p['dformat']['name']=='NCHW';shapes[out]=tuple(p['dims']);names[out]=op['name'];inputs.append(H.make_tensor_value_info(op['name'],T.FLOAT,shapes[out]))
  elif typ=='Const':values[out]=weights[f'op_{n}_const'];shapes[out]=values[out].shape;names.pop(out)
  elif typ=='ConvertTensor':
   assert {p['source']['name'],p['dest']['name']}=={'NCHW','NC4HW4'};shapes[out]=shapes[ii[0]];names[out]=tensor(ii[0])
   if ii[0] in values:values[out]=values[ii[0]]
  elif typ=='Shape':values[out]=np.array(shapes[ii[0]],dtype=np.int32);shapes[out]=values[out].shape;names.pop(out)
  elif typ=='Rank':values[out]=np.array(len(shapes[ii[0]]),dtype=np.int32);shapes[out]=();names.pop(out)
  elif typ=='Reshape':
   assert p['dimType']['name']=='NCHW';dims=ints(ii[1]) if len(ii)>1 else p['dims'];shapes[out]=reshape_shape(shapes[ii[0]],dims)
   if ii[0] in values:values[out]=values[ii[0]].reshape(shapes[out]);names.pop(out)
   else:emit('Reshape',[tensor(ii[0]),init(np.array(shapes[out],dtype=np.int64),'reshape')],name)
  elif typ in ('Unsqueeze','Squeeze'):
   shape=list(shapes[ii[0]])
   if typ=='Unsqueeze':
    axes=sorted(p['squeezeDims']);assert all(x>=0 for x in axes)
    for axis in axes:shape.insert(axis,1)
   else:
    axes=p['squeezeDims'];assert axes is None;shape=[x for x in shape if x!=1]
   shapes[out]=tuple(shape)
   if ii[0] in values:values[out]=values[ii[0]].reshape(shape);names.pop(out)
   else:emit('Reshape',[tensor(ii[0]),init(np.array(shape,dtype=np.int64),'reshape')],name)
  elif typ=='BinaryOp':
   kind=p['opType']['name'];fn={'ADD':np.add,'SUB':np.subtract,'MUL':np.multiply,'MOD':np.mod}[kind];act=p['activationType'];assert act in (0,1)
   shapes[out]=np.broadcast_shapes(*(shapes[i] for i in ii))
   if all(i in values for i in ii):
    values[out]=fn(*(values[i] for i in ii));values[out]=np.maximum(values[out],0) if act else values[out];names.pop(out)
   else:
    rawname=name+'_before_relu' if act else name;attrs={'fmod':0} if kind=='MOD' else {};emit({'ADD':'Add','SUB':'Sub','MUL':'Mul','MOD':'Mod'}[kind],[tensor(i) for i in ii],rawname,**attrs)
    if act:emit('Relu',[rawname],name)
  elif typ in ('SliceTf','StridedSlice'):
   start=ints(ii[1]);v=ints(ii[2]);shape=shapes[ii[0]]
   if typ=='SliceTf':end=[shape[i] if size==-1 else start[i]+size for i,size in enumerate(v)];steps=[1]*len(start)
   else:
    assert all(p[k]==0 for k in ('beginMask','endMask','ellipsisMask','newAxisMask','shrinkAxisMask','fromType'));end=v;steps=ints(ii[3])
   assert len(start)==len(end)==len(steps) and all(x>0 for x in steps)
   slices=tuple(slice(a,b,d) for a,b,d in zip(start,end,steps));shapes[out]=dims_slice(shape,start,end,steps)
   if ii[0] in values:values[out]=values[ii[0]][slices];names.pop(out)
   else:emit('Slice',[tensor(ii[0])]+[init(np.array(x,dtype=np.int64),'slice') for x in (start,end,list(range(len(start))),steps)],name)
  elif typ=='GatherV2':
   axis=ints(ii[2])[0];shape=shapes[ii[0]];axis=axis%len(shape);indices=known(ii[1]);shapes[out]=shape[:axis]+indices.shape+shape[axis+1:]
   if ii[0] in values:values[out]=np.take(values[ii[0]],indices,axis=axis);names.pop(out)
   else:emit('Gather',[tensor(ii[0]),init(indices.astype(np.int64),'gather')],name,axis=axis)
  elif typ=='Concat':
   axis=p['axis'];shape=list(shapes[ii[0]]);axis%=len(shape);shape[axis]=sum(shapes[i][axis] for i in ii)
   assert all(all(d==shapes[ii[0]][k] for k,d in enumerate(shapes[i]) if k!=axis) for i in ii);shapes[out]=tuple(shape)
   if all(i in values for i in ii):values[out]=np.concatenate([values[i] for i in ii],axis=axis);names.pop(out)
   else:emit('Concat',[tensor(i) for i in ii],name,axis=axis)
  elif typ=='Convolution':
   common=p['common'];w=weights[f'op_{n}_weight'];b=weights[f'op_{n}_bias'];shape=shapes[ii[0]];assert len(shape)==4 and shape[1]==common['inputCount'];assert common['padMode']['name']=='CAFFE' and not common['hasOutputShape'] and not common['outPads']
   pads=common['pads'] or [common['padY'],common['padX']]*2;strides=[common['strideY'],common['strideX']];dil=[common['dilateY'],common['dilateX']];kernels=[common['kernelY'],common['kernelX']]
   shapes[out]=(shape[0],common['outputCount'],*[(shape[i+2]+pads[i]+pads[i+2]-dil[i]*(kernels[i]-1)-1)//strides[i]+1 for i in range(2)])
   assert not common['relu6'];rawname=name+'_before_relu' if common['relu'] else name
   emit('Conv',[tensor(ii[0]),init(w,'weight'),init(b,'bias')],rawname,pads=pads,strides=strides,dilations=dil,group=common['group'])
   if common['relu']:emit('Relu',[rawname],name)
  elif typ=='Pooling':
   assert p['type']['name']=='MAXPOOL' and p['padType']['name']=='CAFFE' and not p['isGlobal'];shape=shapes[ii[0]];pads=p['pads'] or [p['padY'],p['padX']]*2;ks=[p['kernelY'],p['kernelX']];strides=[p['strideY'],p['strideX']];assert not p['ceilModel']
   shapes[out]=(shape[0],shape[1],*[(shape[i+2]+pads[i]+pads[i+2]-ks[i])//strides[i]+1 for i in range(2)]);emit('MaxPool',[tensor(ii[0])],name,kernel_shape=ks,strides=strides,pads=pads,ceil_mode=0)
  elif typ=='Pooling3D':
   assert p['isGlobal'] and p['type']['name']=='AVEPOOL';shape=shapes[ii[0]];assert len(shape)>=3;shapes[out]=shape[:2]+(1,)*(len(shape)-2);emit('GlobalAveragePool',[tensor(ii[0])],name)
  elif typ=='UnaryOp':
   assert p['opType']['name']=='SIGMOID';shapes[out]=shapes[ii[0]];emit('Sigmoid',[tensor(ii[0])],name)
  elif typ=='ReLU':
   shapes[out]=shapes[ii[0]]
   if p['slope']==0:emit('Relu',[tensor(ii[0])],name)
   else:emit('LeakyRelu',[tensor(ii[0])],name,alpha=p['slope'])
  else:raise NotImplementedError(typ)
  if out in values:folded[typ]+=1;assert values[out].shape==shapes[out]
  trace.append({'op_index':n,'type':typ,'name':op['name'],'output_tensor':out,'shape':shapes[out],'constant_folded':out in values})
 except Exception:
  (O/'partial_trace.json').write_text(json.dumps({'at_op':n,'op':op,'input_shapes':{i:shapes.get(i) for i in ii},'input_constants':{i:values[i].tolist() for i in ii if i in values},'trace':trace},indent=2));raise
outid=g['network']['tensorName'].index('output_0');assert shapes[outid]==(1,258)
emit('Identity',[tensor(outid)],'output_0');graph=H.make_graph(nodes,'original_MGazeNet_static_batch1',inputs,[H.make_tensor_value_info('output_0',T.FLOAT,[1,258])],initializer=initializers)
model=H.make_model(graph,producer_name='Original MNN graph and exact original weights translator',opset_imports=[H.make_opsetid('',13)]);model.ir_version=9
onnx.checker.check_model(model,full_check=True);model=onnx.shape_inference.infer_shapes(model,strict_mode=True);onnx.save(model,O/'original_gaze.onnx')
(O/'shape_trace.json').write_text(json.dumps(trace,indent=2))
r={'status':'CONVERTED_STATIC_ONNX_CHECKER_PASS_NUMERIC_EQUIVALENCE_PENDING','source_graph':{'path':str(gp),'sha256':sha(gp)},'source_constants':{'path':str(cp),'sha256':sha(cp)},'source':{'path':str(Path(__file__)),'sha256':sha(__file__)},'ONNX':{'path':str(O/'original_gaze.onnx'),'sha256':sha(O/'original_gaze.onnx')},'original_ops':len(trace),'ONNX_nodes':len(nodes),'folded_counts':dict(folded),'ONNX_op_counts':dict(collections.Counter(x.op_type for x in nodes)),'input_layout':'NCHW fixed batch1; application NHWC must transpose exactly once','output_shape':[1,258],'numeric_equivalence_verified':False,'RK_NPU_executed':False}
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
