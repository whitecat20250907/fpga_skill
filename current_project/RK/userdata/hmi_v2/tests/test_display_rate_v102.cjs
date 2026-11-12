const assert=require('node:assert/strict');
const {DisplayRate}=require('../console/assets/display-rate.js');
const r=new DisplayRate();
assert.equal(r.observe('epoch1',0,0),null);
for(let i=1;i<=20;i++)r.observe('epoch1',i,50*i);
assert.equal(r.value,20);
// Repeated packets do not count as new model output.
for(let i=1;i<=20;i++)r.observe('epoch1',20,1000+50*i);
assert.equal(r.value,0);
// Loss of a valid face clears the displayed value immediately.
assert.equal(r.observe(null,null,2100),null);
assert.equal(r.value,null);
assert.equal(r.observe('epoch1',50,5000),null);
for(let i=1;i<=10;i++)r.observe('epoch1',50+i,5000+100*i);
assert.equal(r.value,10);
assert.equal(r.observe('epoch2',1,6100),null);
assert.equal(r.observe('epoch2',2,6000),null);
r.reset();assert.equal(r.value,null);assert.equal(r.started,null);
console.log('PASS: distinct display frames, duplicate zero, face absence, resume, epoch and clock reset');
