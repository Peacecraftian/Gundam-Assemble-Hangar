const el = id => document.getElementById(id);
const canvas = document.querySelector('canvas'), result = document.querySelector('output');
const ctx = canvas.getContext('2d');
const params = new URLSearchParams(location.search);
const attack = params.has('attack');
const saved = JSON.parse(params.get('saved') || 'null');
const disarmed = Boolean(saved?.disarmed);
const threshold = saved?.threshold ?? 9;
let pendingDisarm = disarmed && !saved?.finalized, busy = false, values = saved?.values ?? null;
const selected = new Set();
el('pool').value = params.get('count') || 3;
el('poolLabel').hidden = attack;
el('accLabel').hidden = !attack;
el('accuracy').value = params.get('accuracy') || 0;
el('disarm').hidden = !disarmed;
function accuracy() { return el('accuracy').valueAsNumber; }
function hit(n) { return n >= threshold || (n !== 1 && n + accuracy() >= 4); }
function validAccuracy() { return Number.isInteger(accuracy()) && Math.abs(accuracy()) <= 99; }
function sync() {
    const count = el('pool').valueAsNumber;
    el('roll').textContent = 'Roll ' + count + ' D10s';
    el('roll').disabled = busy || (attack && values !== null) || !Number.isInteger(count)
        || count < (attack ? 0 : 1) || count > 60 || !validAccuracy();
    el('reroll').disabled = busy || !selected.size || (disarmed && !pendingDisarm) || !validAccuracy();
    el('disarm').disabled = busy || !values || !pendingDisarm || !validAccuracy();
    el('pool').disabled = busy;
    el('accuracy').disabled = busy || (disarmed && !pendingDisarm);
}
function results() {
    const facesEl = el('faces');
    facesEl.replaceChildren();
    values.forEach((n,i) => {
        const btn = document.createElement('button');
        const mark = !attack ? '' : (hit(n) ? (n >= threshold && !disarmed ? ' CRIT' : ' HIT') : ' MISS');
        btn.textContent = n + mark;
        btn.setAttribute('aria-label','Die '+(i+1)+': '+n+mark);
        btn.setAttribute('aria-pressed',selected.has(i));
        btn.disabled = busy || (disarmed && !pendingDisarm);
        btn.onclick = () => {
            if (selected.has(i)) selected.delete(i); else selected.add(i);
            btn.setAttribute('aria-pressed',selected.has(i)); sync();
        };
        facesEl.append(btn);
    });
    result.textContent = attack ? values.filter(hit).length+' hits · '+(disarmed ? 0 : values.filter(n=>n>=threshold).length)
        +' critical'+(pendingDisarm ? ' · Disarm pending' : '') : (values.length>12 ? 'Results · '+values.length+' dice' : 'Results · '+values.join(' · '));
    sync();
}
function snapshot() {
    if (!attack || busy || !values || pendingDisarm || !validAccuracy()) return null;
    return {values,accuracy:accuracy()};
}
// Keep the same physical tray and poses when the keyboard or result list resizes the canvas.
let fieldWidth=1, fieldHeight=1, lastPoses=[], lastLabels=null;
function render() {
    const width=canvas.clientWidth,height=canvas.clientHeight;
    const ratio=window.devicePixelRatio || 1;
    const pixelsWide=Math.round(width*ratio),pixelsHigh=Math.round(height*ratio);
    if(canvas.width!==pixelsWide || canvas.height!==pixelsHigh){
        canvas.width=pixelsWide;canvas.height=pixelsHigh;
    }
    ctx.setTransform(ratio,0,0,ratio,0,0);
    const scale=Math.min(width/(fieldWidth+.5),height/(fieldHeight+1.4));
    ctx.clearRect(0,0,width,height);
    lastPoses.forEach(([x,y,z,qx,qy,qz,qw],index) => {
        const rotation = new Quaternion(qx,qy,qz,qw);
        const points = vertices.map(v => {
            const p = rotation.vmult(v);
            return [width/2+(x+p.x)*scale,height/2-(y+p.y)*scale-(z+p.z)*scale*.12,p.z];
        });
        const depth = face => face.reduce((sum,i) => sum+points[i][2],0);
        faces.slice().sort((a,b) => depth(a)-depth(b)).forEach(face => {
            ctx.beginPath();
            face.forEach((i,n) => n ? ctx.lineTo(points[i][0],points[i][1]) : ctx.moveTo(points[i][0],points[i][1]));
            ctx.closePath();
            ctx.fillStyle = ['#77d6c1','#ffa88d','#ffcf81'][index%3]; ctx.fill();
            ctx.strokeStyle='#293b49'; ctx.stroke();
        });
        if(lastLabels){
            ctx.fillStyle='#142022';
            ctx.font='bold '+Math.round(scale*.67)+'px sans-serif';
            ctx.textAlign='center';ctx.textBaseline='middle';
            ctx.fillText(lastLabels[index],width/2+x*scale,height/2-(y+z*.12)*scale);
        }
    });
}
new ResizeObserver(render).observe(canvas);
function start(indices, fresh, mandatory=false) {
    if (busy) return;
    busy=true; sync();
    el('faces').replaceChildren(); result.textContent='Rolling…';
    const finish = rolled => {
        if (fresh) values=rolled;
        else indices.forEach((idx,i) => { values[idx]=rolled[i]; });
        selected.clear();
        if (attack) RollHost.settled(JSON.stringify(values),accuracy(),mandatory);
        else { busy=false; results(); }
    };
    lastPoses=[];lastLabels=null;render();
    if (!indices.length) { finish([]); return; }
    const aspect=canvas.clientWidth/Math.max(1,canvas.clientHeight);
    // Leave room for collisions in a large pool. Bring the camera closer for everyday rolls.
    fieldWidth=Math.max(13,8*aspect,Math.sqrt(indices.length*aspect)*3.65);
    fieldHeight=fieldWidth/aspect;
    startDice(fieldWidth,fieldHeight,indices.length);
    const offsets=indices.map(() => Math.floor(Math.random()*10));
    let last=performance.now(),carry=0;
    function frame(now) {
        carry+=Math.min(100,now-last)*.12; last=now;
        const ticks=Math.floor(carry); carry-=ticks;
        try {
            const [poses,settled]=JSON.parse(stepDice(ticks));
            lastPoses=poses;
            lastLabels=settled && settled.map((face,i) => faceNumbers[(face+offsets[i])%10]);
            render();
            if (settled) finish(lastLabels);
            else requestAnimationFrame(frame);
        } catch (err) {
            busy=false;
            if (values) results(); else sync();
            result.textContent=err.message;
        }
    }
    requestAnimationFrame(frame);
}
function rollSaved(mandatory) { if (mandatory) pendingDisarm=false; busy=false; results(); }
el('pool').oninput=sync;
el('accuracy').oninput=() => { if (values) results(); else sync(); };
el('roll').onclick=() => start(Array.from({length:el('pool').valueAsNumber},(_,i)=>i),true);
el('reroll').onclick=() => start([...selected],false);
el('disarm').onclick=() => start(values.map((n,i)=>hit(n)?i:-1).filter(i=>i>=0),false,true);
if (values !== null) results(); else sync();
