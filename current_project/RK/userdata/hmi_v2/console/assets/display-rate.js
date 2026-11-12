// Count distinct frames actually presented, rather than inference attempts.
class DisplayRate {
  constructor(){this.reset();}
  reset(){this.identity=null;this.last=null;this.started=null;this.count=0;this.value=null;}
  observe(identity,sequence,now){
    if(identity==null||sequence==null||!Number.isFinite(now)){this.reset();return null;}
    if(identity!==this.identity||this.started===null||now<this.started){
      this.reset();this.identity=identity;this.last=sequence;this.started=now;return null;
    }
    if(sequence!==this.last){this.count++;this.last=sequence;}
    const elapsed=now-this.started;
    if(elapsed>=1000){this.value=this.count*1000/elapsed;this.count=0;this.started=now;}
    return this.value;
  }
}
if(typeof module!=='undefined')module.exports={DisplayRate};
