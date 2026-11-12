/* Framing and latest-only rendering, independent of network chunk boundaries. */
(function(root){
 class PreviewFrames {
  constructor(accept){this.accept=accept;this.header=new Uint8Array(4);this.head=0;this.body=null;this.used=0;}
  feed(chunk){let at=0;while(at<chunk.length){
   if(!this.body){const n=Math.min(4-this.head,chunk.length-at);this.header.set(chunk.subarray(at,at+n),this.head);this.head+=n;at+=n;if(this.head<4)continue;
    const size=new DataView(this.header.buffer).getUint32(0,true);if(size<8||size>4*1024*1024)throw Error('预览长度错误');this.body=new Uint8Array(size);this.used=0;
   }
   const n=Math.min(this.body.length-this.used,chunk.length-at);this.body.set(chunk.subarray(at,at+n),this.used);this.used+=n;at+=n;
   if(this.used===this.body.length){const packet=this.body.buffer;this.body=null;this.head=0;this.used=0;this.accept(packet);}
  }}
  finish(){if(this.head||this.body)throw Error('预览连接中断');}
 }
 class LatestPreview {
  constructor(paint,onError){this.paint=paint;this.onError=onError;this.pending=null;this.busy=false;this.closed=false;this.dropped=0;}
  offer(value){if(this.closed)return;if(this.pending!==null)this.dropped++;this.pending=value;if(!this.busy)this.drain();}
  async drain(){this.busy=true;try{while(this.pending!==null&&!this.closed){const value=this.pending;this.pending=null;await this.paint(value);}}catch(e){this.onError(e);}finally{this.busy=false;}}
  close(){this.closed=true;this.pending=null;}
 }
 root.PreviewFrames=PreviewFrames;root.LatestPreview=LatestPreview;
})(typeof module==='object'?module.exports:globalThis);
