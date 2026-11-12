"""Auditable static FP32 export for the seven pinned MediaPipe subgraphs.

Preserves NHWC semantics explicitly; constant FP16 DEQUANTIZE becomes FP32.
Unsupported operators/options fail, never substitute approximate operations.
The original TFLite interpreter is used only by validation, not deployment.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
import onnx
from onnx import helper as H, numpy_helper as N, TensorProto as T
import tflite_schema as S

ROOT=Path(__file__).resolve().parent
DT={S.TensorType.FLOAT32:np.float32,S.TensorType.FLOAT16:np.float16,S.TensorType.INT32:np.int32,S.TensorType.INT64:np.int64}
OPS={v:k for k,v in vars(S.BuiltinOperator).items() if isinstance(v,int)}

def convert(path):
    m=S.Model.GetRootAsModel(path.read_bytes(),0);g=m.Subgraphs(0)
    nodes=[];init=[];const={};shapes={};names={};counter=0
    def name(i):return 't'+str(i)
    def fresh():
        nonlocal counter
        counter+=1;return 'v'+str(counter)
    def value(x):
        n=fresh();x=np.asarray(x);init.append(N.from_array(x,n));return n
    def emit(op,ins,out=None,**kw):
        if out is None:out=fresh()
        nodes.append(H.make_node(op,ins,[out],name=out+'_'+op,**kw));return out
    def opts(op,cls):
        o=cls();b=op.BuiltinOptions();o.Init(b.Bytes,b.Pos);return o
    def activation(x,typ,out):
        if typ==S.ActivationFunctionType.NONE:emit('Identity',[x],out)
        elif typ==S.ActivationFunctionType.RELU:emit('Relu',[x],out)
        elif typ==S.ActivationFunctionType.RELU6:emit('Clip',[x,value(np.float32(0)),value(np.float32(6))],out)
        elif typ==S.ActivationFunctionType.TANH:emit('Tanh',[x],out)
        else:raise ValueError(('activation',typ))
    for i in range(g.TensorsLength()):
        t=g.Tensors(i);shapes[i]=list(map(int,t.ShapeAsNumpy())) if t.ShapeLength() else [];names[i]=t.Name().decode()
        b=m.Buffers(t.Buffer())
        if b.DataLength():
            a=np.frombuffer(b.DataAsNumpy().tobytes(),DT[t.Type()]).reshape(shapes[i]);const[i]=a
            init.append(N.from_array(a,name(i)))
    for j in range(g.OperatorsLength()):
        op=g.Operators(j);c=m.OperatorCodes(op.OpcodeIndex());kind=OPS[max(c.BuiltinCode(),c.DeprecatedBuiltinCode())]
        ids=list(map(int,op.InputsAsNumpy()));outs=list(map(int,op.OutputsAsNumpy()));ins=[name(i) for i in ids if i>=0];out=name(outs[0]);a=None
        if kind=='DEQUANTIZE':
            assert ids[0] in const and const[ids[0]].dtype==np.float16
            const[outs[0]]=const[ids[0]].astype(np.float32);init.append(N.from_array(const[outs[0]],out));continue
        if kind in ('CONV_2D','DEPTHWISE_CONV_2D','MAX_POOL_2D'):
            cl={'CONV_2D':S.Conv2DOptions,'DEPTHWISE_CONV_2D':S.DepthwiseConv2DOptions,'MAX_POOL_2D':S.Pool2DOptions}[kind];o=opts(op,cl)
            x=emit('Transpose',[ins[0]],perm=[0,3,1,2]);strides=[o.StrideH(),o.StrideW()]
            dil=[1,1] if kind=='MAX_POOL_2D' else [o.DilationHFactor(),o.DilationWFactor()]
            if kind=='MAX_POOL_2D':ks=[o.FilterHeight(),o.FilterWidth()]
            else:
                w=const[ids[1]];ks=list(w.shape[1:3])
                w=w.transpose(0,3,1,2) if kind=='CONV_2D' else w.transpose(3,0,1,2)
            pads=[0,0,0,0]
            if o.Padding()==S.Padding.SAME:
                totals=[max(0,(shapes[outs[0]][d+1]-1)*strides[d]+(ks[d]-1)*dil[d]+1-shapes[ids[0]][d+1]) for d in range(2)]
                pads=[totals[0]//2,totals[1]//2,totals[0]-totals[0]//2,totals[1]-totals[1]//2]
            if kind=='MAX_POOL_2D':y=emit('MaxPool',[x],kernel_shape=ks,strides=strides,pads=pads)
            else:
                ci=[x,value(w)]
                if len(ids)>2 and ids[2]>=0:ci.append(ins[2])
                y=emit('Conv',ci,strides=strides,pads=pads,dilations=dil,group=1 if kind=='CONV_2D' else shapes[ids[0]][3])
            y=emit('Transpose',[y],perm=[0,2,3,1]);activation(y,o.FusedActivationFunction(),out)
        elif kind in ('ADD','SUB','MUL','DIV'):
            o=opts(op,getattr(S,kind.title()+'Options'));y=emit(kind.title(),ins);activation(y,o.FusedActivationFunction(),out)
        elif kind in ('RELU','PRELU','LOGISTIC','SQRT','NEG'):
            emit({'RELU':'Relu','PRELU':'PRelu','LOGISTIC':'Sigmoid','SQRT':'Sqrt','NEG':'Neg'}[kind],ins,out)
        elif kind=='MAXIMUM':emit('Add',[ins[0],emit('Relu',[emit('Sub',[ins[1],ins[0]])])],out)
        elif kind=='MINIMUM':emit('Sub',[ins[0],emit('Relu',[emit('Sub',[ins[0],ins[1]])])],out)
        elif kind=='RSQRT':emit('Reciprocal',[emit('Sqrt',ins)],out)
        elif kind=='SQUARED_DIFFERENCE':
            y=emit('Sub',ins);emit('Mul',[y,y],out)
        elif kind=='PAD':
            p=const[ids[1]].astype(np.int64)
            if len(p)==4 and p[3].any() and not p[:3].any():
                ci=shapes[ids[0]][3];co=shapes[outs[0]][3];weight=np.zeros((co,ci,1,1),np.float32)
                for c in range(ci):weight[int(p[3,0])+c,c,0,0]=1.
                x=emit('Transpose',[ins[0]],perm=[0,3,1,2]);x=emit('Conv',[x,value(weight)],kernel_shape=[1,1])
                emit('Transpose',[x],out,perm=[0,2,3,1])
            elif p[0].any() or (len(p)==4 and p[3].any()):
                # Channel padding in BlazeFace otherwise dispatches to CPU in
                # RKNN 2.3.0. Constant-zero concatenation is exact and NPU mapped.
                x=ins[0];shape=list(shapes[ids[0]])
                for axis,(before,after) in enumerate(p):
                    if not before and not after:continue
                    parts=[]
                    if before:
                        z=shape.copy();z[axis]=int(before);parts.append(value(np.zeros(z,np.float32)))
                    parts.append(x)
                    if after:
                        z=shape.copy();z[axis]=int(after);parts.append(value(np.zeros(z,np.float32)))
                    x=emit('Concat',parts,axis=axis);shape[axis]+=int(before+after)
                emit('Identity',[x],out)
            else:emit('Pad',[ins[0],value(np.concatenate([p[:,0],p[:,1]]))],out,mode='constant')
        elif kind=='RESHAPE':
            # All source models are fixed batch 1. Exact output shape preserves -1 semantics.
            emit('Reshape',[ins[0],value(np.array(shapes[outs[0]],np.int64))],out)
        elif kind=='CONCATENATION':
            o=opts(op,S.ConcatenationOptions);activation(emit('Concat',ins,axis=o.Axis()),o.FusedActivationFunction(),out)
        elif kind=='FULLY_CONNECTED':
            o=opts(op,S.FullyConnectedOptions);w=const[ids[1]]
            assert o.WeightsFormat()==0 and not o.AsymmetricQuantizeInputs()
            x=ins[0]
            if not o.KeepNumDims():x=emit('Reshape',[x,value(np.array([-1,w.shape[1]],np.int64))])
            y=emit('MatMul',[x,value(w.T)])
            if len(ids)>2 and ids[2]>=0:y=emit('Add',[y,ins[2]])
            activation(y,o.FusedActivationFunction(),out)
        elif kind in ('MEAN','SUM','REDUCE_MAX','REDUCE_MIN'):
            o=opts(op,S.ReducerOptions);axes=const[ids[1]].astype(np.int64).reshape(-1)
            typ={'MEAN':'ReduceMean','SUM':'ReduceSum','REDUCE_MAX':'ReduceMax','REDUCE_MIN':'ReduceMin'}[kind]
            if typ in ('ReduceMax','ReduceMin'):
                shape=shapes[ids[0]];axes=[int(a)%len(shape) for a in axes];remain=[i for i in range(len(shape)) if i not in axes]
                reduced=int(np.prod([shape[a] for a in axes]));channels=int(np.prod([shape[a] for a in remain]))
                x=emit('Transpose',[ins[0]],perm=remain+axes);x=emit('Reshape',[x,value(np.array([1,channels,reduced,1],np.int64))])
                if typ=='ReduceMin':x=emit('Neg',[x])
                # Pairwise pool without zero padding, retaining an odd tail.
                while reduced>1:
                    even=reduced-reduced%2
                    if reduced%2:
                        first=emit('Slice',[x,value(np.array([0],np.int64)),value(np.array([even],np.int64)),value(np.array([2],np.int64))])
                        tail=emit('Slice',[x,value(np.array([even],np.int64)),value(np.array([reduced],np.int64)),value(np.array([2],np.int64))])
                    else:first=x
                    x=emit('MaxPool',[first],kernel_shape=[2,1],strides=[2,1])
                    if reduced%2:x=emit('Concat',[x,tail],axis=2)
                    reduced=(reduced+1)//2
                if typ=='ReduceMin':x=emit('Neg',[x])
                emit('Reshape',[x,value(np.array(shapes[outs[0]],np.int64))],out)
            elif typ=='ReduceSum':emit(typ,[ins[0],value(axes)],out,keepdims=int(o.KeepDims()))
            else:emit(typ,[ins[0]],out,axes=axes.tolist(),keepdims=int(o.KeepDims()))
        elif kind=='TRANSPOSE':emit('Transpose',[ins[0]],out,perm=const[ids[1]].tolist())
        elif kind=='GATHER':
            o=opts(op,S.GatherOptions);assert o.BatchDims()==0
            emit('Gather',[ins[0],value(const[ids[1]].astype(np.int64))],out,axis=o.Axis())
        elif kind=='UNPACK':
            o=opts(op,S.UnpackOptions)
            for k,v in enumerate(outs):emit('Gather',[ins[0],value(np.array(k,np.int64))],name(v),axis=o.Axis())
        elif kind=='STRIDED_SLICE':
            o=opts(op,S.StridedSliceOptions);assert o.EllipsisMask()==0 and o.NewAxisMask()==0
            starts=const[ids[1]].copy();ends=const[ids[2]].copy();steps=const[ids[3]].copy();squeeze=[]
            for k in range(len(starts)):
                size=shapes[ids[0]][k]
                if o.BeginMask()&(1<<k):starts[k]=0 if steps[k]>0 else size-1
                if o.EndMask()&(1<<k):ends[k]=size if steps[k]>0 else -2147483647
                if o.ShrinkAxisMask()&(1<<k):
                    if starts[k]<0:starts[k]+=size
                    ends[k]=starts[k]+1;steps[k]=1;squeeze.append(k)
            y=emit('Slice',[ins[0],value(starts.astype(np.int64)),value(ends.astype(np.int64)),value(np.arange(len(starts),dtype=np.int64)),value(steps.astype(np.int64))])
            if squeeze:emit('Squeeze',[y,value(np.array(squeeze,np.int64))],out)
            else:emit('Identity',[y],out)
        elif kind=='SOFTMAX':
            o=opts(op,S.SoftmaxOptions);emit('Softmax',[emit('Mul',[ins[0],value(np.float32(o.Beta()))])],out,axis=-1)
        elif kind=='RESIZE_BILINEAR':
            o=opts(op,S.ResizeBilinearOptions)
            s=shapes[outs[0]];src=shapes[ids[0]]
            # RKNN 2.3.0 Resize produced large boundary discrepancies on this
            # pinned palm graph. Express exact separable bilinear interpolation
            # as constant matrices, including clamped-edge half-pixel samples.
            def weights(n,k):
                pos=np.arange(k,dtype=np.float64)
                pos=pos*(n-1)/(k-1) if o.AlignCorners() and k>1 else (pos+.5)*n/k-.5 if o.HalfPixelCenters() else pos*n/k
                pos=np.clip(pos,0,n-1);lo=np.floor(pos).astype(int);hi=np.minimum(lo+1,n-1);a=pos-lo
                mat=np.zeros((n,k),np.float32)
                for j in range(k):mat[lo[j],j]+=1-a[j];mat[hi[j],j]+=a[j]
                return mat
            x=emit('Transpose',[ins[0]],perm=[0,3,1,2])
            x=emit('MatMul',[x,value(weights(src[2],s[2]))]);x=emit('Transpose',[x],perm=[0,1,3,2])
            y=emit('MatMul',[x,value(weights(src[1],s[1]))]);emit('Transpose',[y],out,perm=[0,3,2,1])
        else:raise NotImplementedError((j,kind))
    inputs=[];prefix=[]
    for i in map(int,g.InputsAsNumpy()):
        if len(shapes[i])==4:
            n=name(i)+'_nchw';s=shapes[i]
            inputs.append(H.make_tensor_value_info(n,T.FLOAT,[s[0],s[3],s[1],s[2]]))
            prefix.append(H.make_node('Transpose',[n],[name(i)],perm=[0,2,3,1]))
        else:inputs.append(H.make_tensor_value_info(name(i),T.FLOAT,shapes[i]))
    nodes=prefix+nodes
    outputs=[H.make_tensor_value_info(name(int(i)),T.FLOAT,shapes[int(i)]) for i in g.OutputsAsNumpy()]
    # The pinned embedder exposes handedness/world inputs that its learned
    # graph does not use. Record pruning explicitly; never send phantom inputs.
    needed={v.name for v in outputs};live=[]
    for node in reversed(nodes):
        if any(v in needed for v in node.output):live.append(node);needed.update(node.input)
    nodes=list(reversed(live));inputs=[x for x in inputs if x.name in needed]
    used={v for n in nodes for v in n.input}|{v.name for v in outputs}
    init=[i for i in init if i.name in used]
    graph=H.make_graph(nodes,path.stem,inputs,outputs,initializer=init)
    model=H.make_model(graph,opset_imports=[H.make_opsetid('',13)],ir_version=8,producer_name='pinned-mediapipe-static-export')
    model=onnx.shape_inference.infer_shapes(model);onnx.checker.check_model(model)
    onnx.save(model,str(path.with_suffix('.onnx')))
    meta={side:[dict(name=name(int(i)),source_name=names[int(i)],shape=shapes[int(i)]) for i in seq] for side,seq in [('inputs',g.InputsAsNumpy()),('outputs',g.OutputsAsNumpy())]}
    for d in meta['inputs']:
        d['format']='nhwc' if len(d['shape'])==4 else 'nchw'
        if len(d['shape'])==4:d['name']+='_nchw'
        d['active']=d['name'] in needed
    path.with_suffix('.io.json').write_text(json.dumps(meta,indent=2)+'\n')
    return meta

def validate(path,meta):
    sys.path.insert(0,str(ROOT/'reference_packages'))
    from tflite_runtime.interpreter import Interpreter
    import onnxruntime as ort
    ref=Interpreter(model_path=str(path),num_threads=1);ref.allocate_tensors()
    opt=ort.SessionOptions();opt.intra_op_num_threads=1;opt.inter_op_num_threads=1
    sess=ort.InferenceSession(str(path.with_suffix('.onnx')),opt,providers=['CPUExecutionProvider'])
    rng=np.random.default_rng(3576);records=[];vectors={}
    for trial in range(4):
        arrays=[(np.zeros(x['shape']) if trial==0 and path.stem!='face_blendshapes' else rng.uniform(-1 if path.stem=='face_detector' else 0,1,x['shape'])).astype(np.float32) for x in meta['inputs']]
        for d,x in zip(ref.get_input_details(),arrays):ref.set_tensor(d['index'],x)
        ref.invoke();expected=[ref.get_tensor(d['index']) for d in ref.get_output_details()]
        actual=sess.run(None,{x['name']:(v.transpose(0,3,1,2) if len(v.shape)==4 else v) for x,v in zip(meta['inputs'],arrays) if x['active']})
        errs=[]
        for k,(a,b) in enumerate(zip(expected,actual)):
            # Large detector regressors near zero can have cancellation; test max error relative to full output scale.
            err=float(np.max(np.abs(a-b)));scale=max(1.,float(np.max(np.abs(a))))
            if not np.isfinite(b).all() or err>0.0002*scale:raise AssertionError((path.stem,trial,k,err,scale))
            errs.append(dict(max_abs=err,scale=scale))
            vectors[f'out_{trial}_{k}']=a
        for k,x in enumerate(arrays):vectors[f'in_{trial}_{k}']=x
        records.append(errs)
    np.savez_compressed(path.with_suffix('.reference.npz'),**vectors)
    path.with_suffix('.onnx_validation.json').write_text(json.dumps(dict(vectors=4,outputs=records,status='PASS',synthetic=True),indent=2)+'\n')
    print(path.stem,'ONNX reference PASS',records,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args();path=ROOT/'models'/(a.name+'.tflite');validate(path,convert(path))
