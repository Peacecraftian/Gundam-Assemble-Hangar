let mapData, editingMap=false;
function loadMap(text,edit) {
    mapData=JSON.parse(text);
    editingMap=edit;
    showBattlefield(mapData);
}
function boardDraft() {
    if (!mapData || !mapData.scenario) return null;
    return mapData.scenario;
}
function showBattlefield(data) {
    const main=document.querySelector('main'), board=document.querySelector('#board');
    const brief=document.querySelector('#brief'), keys=document.querySelector('#keys');
    const hud=document.querySelector('#hud'), controls=document.querySelector('#mapControls');
    document.querySelector('#empty').textContent=data.message || '';
    main.hidden=!data.scenario;
    if (!data.scenario) return;
    const {scenario,special,tokens,stars,columns}=data;
    let colors=data.colors;
    let brush={layer:'terrain',value:'height1'}, stroke=null, last=null, pointer=null;
    const past=[],future=[];
    board.replaceChildren(); brief.replaceChildren(); keys.replaceChildren(); controls.replaceChildren();
    hud.textContent='';
    const add=(parent,tag,text) => {
        const el=document.createElement(tag); el.textContent=text; parent.append(el); return el;
    };
    for (const [label,field] of data.fields) {
        add(brief,'h2',label);
        if (editingMap) {
            const input=add(brief,field==='name'||field==='location'?'input':'textarea','');
            input.value=scenario[field]; input.setAttribute('aria-label',label);
            input.oninput=()=>{scenario[field]=input.value;};
        } else add(brief,'p',scenario[field]);
    }
    document.querySelector('#north').textContent='Player 2 · '+data.players[1]+' / North';
    document.querySelector('#south').textContent='Player 1 · '+data.players[0]+' / South';
    const art=name=>'map-art/'+name+'.svg';
    const palette=add(keys,'details','');
    const paletteLabel=add(palette,'summary','');
    const displayName=name=>name[0].toUpperCase()+name.slice(1);
    paletteLabel.textContent=displayName(scenario.palette)+' palette';
    for (const name of Object.keys(data.palettes || {[scenario.palette]:colors})) {
        const option=add(palette,'button',displayName(name));
        option.onclick=()=>setPalette(name);
    }
    const swatches={};
    function legend(title,entries,layer) {
        add(keys,'h2',title);
        let index=0;
        for (const [key,entry] of Object.entries(entries)) {
            const row=add(keys,editingMap?'button':'div','');
            row.className='key';
            const icon=add(row,layer==='terrain'?'i':'img','');
            if (layer==='terrain') {icon.className='swatch'; icon.style.background=colors[key]; swatches[key]=icon;}
            else {icon.src=art(entry[1]); icon.alt='';}
            const id=add(row,'span',String(++index).padStart(2,'0'));id.className='legend-id';id.setAttribute('aria-hidden','true');
            add(row,'span',layer==='terrain'?entry:entry[0]);
            if (editingMap) {
                row.setAttribute('aria-pressed',brush.layer===layer && brush.value===key);
                row.onclick=()=>selectBrush(layer,key,row);
            }
        }
    }
    function selectBrush(layer,value,row) {
        brush={layer,value};
        for (const b of keys.querySelectorAll('button')) b.setAttribute('aria-pressed',b===row);
    }
    legend('Terrain',data.terrain,'terrain'); legend('Special terrain',special,'special_terrain'); legend('Tokens',tokens,'token');
    if (editingMap) for (const [label,layer] of [['Clear special terrain','special_terrain'],['Remove token','token']]) {
        const btn=add(keys,'button',label); btn.onclick=()=>selectBrush(layer,null,btn);
    }
    const svg=(parent,tag,attrs)=>{
        const node=document.createElementNS('http://www.w3.org/2000/svg',tag);
        for (const [attr,value] of Object.entries(attrs)) node.setAttribute(attr,value);
        parent.append(node); return node;
    };
    const step=Math.sqrt(3)*20;
    board.setAttribute('viewBox',[-2,-2,44+(columns.length-1)*30,4+Math.max(...columns)*step].join(' '));
    board.setAttribute('aria-label',scenario.name+' · '+Object.keys(scenario.cells).length+' hexes');
    const layers=['ground','stars','decals','grid','tokens'].map(id=>svg(board,'g',{id}));
    const pieces=new Map();
    function image(parent,name,x,y,width,height) {
        return svg(parent,'image',{href:art(name),x:x-width/2,y:y-height/2,width,height});
    }
    function paintCell(key) {
        const cell=scenario.cells[key];
        let groups=pieces.get(key);
        if (!groups) {
            groups=layers.map(layer=>svg(layer,'g',{})); pieces.set(key,groups);
        } else for (const g of groups) g.replaceChildren();

        const [row,col] = key.split('-').map(Number);
        const x=20+30*(col-1), y=(row-.5+(col%2===0?.5:0))*step;
        const points = [[20,0],[10,step/2],[-10,step/2],[-20,0],[-10,-step/2],[10,-step/2]]
            .map(([dx,dy]) => [x+dx,y+dy].join(',')).join(' ');
        svg(groups[0],'polygon',{points,fill:colors[cell.terrain],'data-cell':key});
        if (scenario.palette==='space' && cell.terrain==='ground')
            for (const [dx,dy,r,fill] of stars[key] || [])
                svg(groups[1],'circle',{cx:x+20*dx,cy:y+20*dy,r:Math.max(.4,20*r),fill});
        if (cell.special_terrain)
            image(groups[2],special[cell.special_terrain][1],x,y,40,40).dataset.cell=key;
        svg(groups[3],'polygon',{points,fill:'none',stroke:'#030710','stroke-width':2,'stroke-linejoin':'round'});
        if (!cell.token) return;
        const marker=svg(groups[4],'g',{'data-cell':key});
        image(marker,tokens[cell.token][1],x,y,23,23);
        if (cell.objective_number != null) {
            svg(marker,'rect',{x:x+1,y:y-2,width:12,height:13,rx:2,fill:'#192022'});
            svg(marker,'text',{x:x+7,y:y+8,fill:'#ffb762','font-size':11,'font-family':'monospace','text-anchor':'middle'}).textContent=cell.objective_number;
        }
    }
    for (const key of Object.keys(scenario.cells)) paintCell(key);
    function setPalette(name) {
        palette.open=false;
        paletteLabel.textContent=displayName(name)+' palette';
        scenario.palette=name; colors=data.palettes[name]; data.colors=colors;
        for (const [k,icon] of Object.entries(swatches)) icon.style.background=colors[k];
        for (const key of pieces.keys()) paintCell(key);
    };
    function tileAt(x,y) {
        const el=document.elementFromPoint(x,y);
        return el && board.contains(el) ? el.closest('[data-cell]')?.dataset.cell : null;
    }
    let highlighted=null;
    function inspect(key) {
        if(highlighted && highlighted!==key) pieces.get(highlighted)[3].classList.remove('highlight');
        highlighted=key; pieces.get(key)[3].classList.add('highlight');
        const c=scenario.cells[key];
        const desc=[key,data.terrain[c.terrain],c.special_terrain && special[c.special_terrain][0],
            c.token && (tokens[c.token][0]+(c.objective_number?' '+c.objective_number:''))].filter(Boolean);
        hud.textContent=desc.join(' · ')+(c.special_terrain?'\n'+(data.rules?.[c.special_terrain]||''):'');
    }
    if (!editingMap) {
        board.onpointerdown=e=>{const key=tileAt(e.clientX,e.clientY); if(key) inspect(key);};
        board.onpointermove=board.onpointerup=board.onpointercancel=null;
        return;
    }
    function apply(key,layer,value) {
        const cells=scenario.cells,c=cells[key],previous=c[layer]??null;
        if (previous===value) return;
        if (layer==='token') {
            const numbered=t=>t==='objective'||t==='special_objective';
            const count=Object.values(cells).filter(other=>other.token===value).length;
            if (value==='objective' && count>=4) {hud.textContent='All four Objectives are placed.'; return;}
            if (numbered(previous)) for (const [k,other] of Object.entries(cells)) {
                if(other.token===previous && other.objective_number>c.objective_number) {other.objective_number--; paintCell(k);}
            }
            delete c.objective_number;
            if (numbered(value)) c.objective_number=count+1;
        }
        if (value===null) delete c[layer]; else c[layer]=value;
        paintCell(key); inspect(key);
        if (layer==='token' && value) {
            const decal=pieces.get(key)[4];
            decal.querySelector('g')?.classList.add('placed');
            const ico=decal.querySelector('image');
            if(ico) svg(decal,'circle',{cx:Number(ico.getAttribute('x'))+11.5,cy:Number(ico.getAttribute('y'))+11.5,r:13,class:'puff'});
        }
    }
    const undo=add(controls,'button','Undo stroke'), redo=add(controls,'button','Redo stroke');
    function buttons(){undo.disabled=!past.length; redo.disabled=!future.length;}
    function restore(from,to){
        if (!from.length) return;
        to.push(JSON.stringify(scenario.cells)); scenario.cells=JSON.parse(from.pop());
        for (const key of pieces.keys()) paintCell(key);
        if(highlighted) pieces.get(highlighted)[3].classList.remove('highlight');
        highlighted=null; hud.textContent=''; buttons();
    }
    undo.onclick=()=>restore(past,future); redo.onclick=()=>restore(future,past); buttons();
    board.oncontextmenu=e=>e.preventDefault();
    let layer,value;
    board.onpointerdown=e=>{
        if (pointer!==null || (e.button!==0 && e.button!==2)) return;
        const key=tileAt(e.clientX,e.clientY);
        if (!key) return;
        e.preventDefault(); board.setPointerCapture(e.pointerId); pointer=e.pointerId;
        layer=brush.layer; value=e.button===2 ? (layer==='terrain'?'ground':null) : brush.value;
        stroke=JSON.stringify(scenario.cells); last=[e.clientX,e.clientY]; apply(key,layer,value);
    };
    board.onpointermove=e=>{
        if (e.pointerId!==pointer || layer==='token') return;
        const dx=e.clientX-last[0],dy=e.clientY-last[1],steps=Math.max(1,Math.ceil(Math.hypot(dx,dy)/5));
        for (let i=1;i<=steps;i++) {
            const key=tileAt(last[0]+dx*i/steps,last[1]+dy*i/steps);
            if (key) apply(key,layer,value);
        }
        last=[e.clientX,e.clientY];
    };
    board.onpointerup=board.onpointercancel=board.onlostpointercapture=e=>{
        if (e.pointerId!==pointer) return;
        if (JSON.stringify(scenario.cells)!==stroke) {past.push(stroke); if(past.length>20) past.shift(); future.length=0;}
        pointer=null; stroke=null; last=null; buttons();
    };
}
