class H{constructor(t={}){this.wrapper=document.getElementById(t.wrapperId||"workflowCanvasWrapper"),this.viewport=document.getElementById(t.viewportId||"workflowCanvasViewport"),this.svg=document.getElementById(t.svgId||"workflowConnectionsSvg"),this.tempWire=document.getElementById(t.tempWireId||"connectionTempWire"),this.availableNodes=t.availableNodes||[],this.nodesMap=new Map,this.availableNodes.forEach(e=>this.nodesMap.set(e.id,e)),this.workflow=t.workflow||{},this.nodes=Array.isArray(this.workflow.nodes)?JSON.parse(JSON.stringify(this.workflow.nodes)):[],this.connections=Array.isArray(this.workflow.connections)?JSON.parse(JSON.stringify(this.workflow.connections)):[],this.customTypes=Array.isArray(this.workflow.custom_types)?JSON.parse(JSON.stringify(this.workflow.custom_types)):[],this.selectedCustomTypeId=null,this.selectedNodeId=null,this.connectingFrom=null,this.draggedNode=null,this.isPanning=!1,this.panStart={x:0,y:0},this.panOffset={x:60,y:60},this.zoom=1,this.simulationResult=null,this.simulationInitialPayload=null,this._customFieldModes={},this.debugIoViewMode="structured",this.currentDebugSubtab="node_io",this.debugVarCategory="all",this.init()}init(){this.normalizeWorkflowData(),this.renderNodes(),this.renderConnections(),this.setupCanvasInteractions(),this.updateSerializedInputs(),this.applyTransform(),this.setupDebugConsole()}normalizeWorkflowData(){if(this.nodes.length===0){this.nodes.push({id:"node_trigger_1",type:this.workflow.trigger_type==="webhook"?"core.trigger_webhook":"core.trigger_event",name:this.workflow.trigger_type==="webhook"?"D\xE9clencheur Webhook":"D\xE9clencheur \xC9v\xE9nement",x:100,y:200,configuration:{trigger_module:this.workflow.trigger_module||"commerce",trigger_event:this.workflow.trigger_event||"order.created",webhook_token:this.workflow.webhook_token||""}});return}let t=100;this.nodes.forEach((e,s)=>{typeof e.x!="number"&&(e.x=t),typeof e.y!="number"&&(e.y=200+(s%2===0?0:40)),t+=300}),this.connections.forEach(e=>{e.source_output||(e.source_output="main"),e.target_input||(e.target_input="main")})}renderNodes(){this.viewport.querySelectorAll(".graph-node").forEach(e=>e.remove()),this.nodes.forEach(e=>{const s=this.createNodeElement(e);this.viewport.appendChild(s)})}createNodeElement(t){const e=this.nodesMap.get(t.type)||{name:t.name||t.type,category:"generic",icon:"fas fa-cube",color:"#4f46e5",inputs:[{id:"main",label:"Entr\xE9e"}],outputs:[{id:"main",label:"Sortie"}]},s=document.createElement("div");s.className="graph-node",s.id=`nodeEl_${t.id}`,s.style.left=`${t.x}px`,s.style.top=`${t.y}px`,this.selectedNodeId===t.id&&s.classList.add("is-selected");const n=e.color||"#4f46e5",a=this.renderNodeIcon(e.icon,16);s.innerHTML=`
      <div class="graph-node-strip" style="background-color: ${n};"></div>
      <div class="graph-node-header">
        <div class="graph-node-icon" style="background-color: ${n};">
          ${a}
        </div>
        <div class="graph-node-title-wrap">
          <h6 class="graph-node-title" title="${this.escapeHtml(t.name||e.name)}">${this.escapeHtml(t.name||e.name)}</h6>
          <span class="graph-node-subtitle">${this.escapeHtml(e.name)}</span>
        </div>
      </div>
      <div class="node-ports-container">
        <div class="node-inputs"></div>
        <div class="node-outputs"></div>
      </div>
    `;const i=s.querySelector(".node-inputs");(e.inputs||[]).forEach(l=>{const d=document.createElement("div");d.className="node-port node-input-port",d.dataset.nodeId=t.id,d.dataset.portId=l.id,d.dataset.direction="input",d.innerHTML=`<span class="node-port-label">${this.escapeHtml(l.label)}</span>`,i.appendChild(d)});const o=s.querySelector(".node-outputs");if((e.outputs||[]).forEach(l=>{const d=document.createElement("div");d.className="node-port node-output-port",d.dataset.nodeId=t.id,d.dataset.portId=l.id,d.dataset.direction="output",l.color&&(d.style.borderColor=l.color),d.innerHTML=`<span class="node-port-label" style="color: ${l.color||""}">${this.escapeHtml(l.label)}</span>`,o.appendChild(d)}),s.addEventListener("mousedown",l=>{l.target.closest(".node-port")||(l.stopPropagation(),this.selectNode(t.id),this.startDraggingNode(t.id,l))}),this.simulationResult?.nodes_trace?.[t.id]){const l=this.simulationResult.nodes_trace[t.id],d=document.createElement("div");l.status==="success"?(d.className="node-sim-badge is-success",d.title="Ex\xE9cut\xE9 avec succ\xE8s",d.innerHTML='<img src="/static_base_icons?name=check&fill=white&size=10">'):l.status==="error"?(d.className="node-sim-badge is-error",d.title=`Erreur : ${l.error||"\xC9chec"}`,d.innerHTML='<img src="/static_base_icons?name=close&fill=white&size=10">'):(d.className="node-sim-badge is-skipped",d.title="Branche non emprunt\xE9e",d.innerHTML='<span style="font-weight:bold;line-height:1;">-</span>'),s.appendChild(d)}return s}renderConnections(){this.svg.querySelectorAll(".connection-path").forEach(e=>e.remove()),this.connections.forEach((e,s)=>{const n=this.getPortCoordinates(e.source_node,e.source_output||"main","output"),a=this.getPortCoordinates(e.target_node,e.target_input||"main","input");if(!n||!a)return;const i=document.createElementNS("http://www.w3.org/2000/svg","path");i.setAttribute("d",this.calculateBezierPath(n.x,n.y,a.x,a.y)),i.setAttribute("class","connection-path"),i.dataset.index=s,i.setAttribute("title",`Liaison: ${e.source_node} (${e.source_output}) -> ${e.target_node}. Clic pour supprimer.`),e.source_output==="true"?i.style.stroke="#10b981":(e.source_output==="false"||e.source_output==="error")&&(i.style.stroke="#ef4444"),i.addEventListener("click",r=>{r.stopPropagation(),confirm("Supprimer cette liaison entre les n\u0153uds ?")&&this.removeConnection(s)}),this.svg.appendChild(i)})}getPortCoordinates(t,e,s){const n=document.getElementById(`nodeEl_${t}`);if(!n)return null;const a=s==="output"?`.node-output-port[data-port-id="${e}"]`:`.node-input-port[data-port-id="${e}"]`;let i=n.querySelector(a);if(i||(i=n.querySelector(s==="output"?".node-output-port":".node-input-port")),!i)return null;const r=this.nodes.find(h=>h.id===t);if(!r)return null;const o=i.getBoundingClientRect(),c=n.getBoundingClientRect(),l=r.x+(o.left-c.left)+o.width/2,d=r.y+(o.top-c.top)+o.height/2;return{x:l,y:d}}calculateBezierPath(t,e,s,n){const a=Math.abs(s-t)*.55,i=Math.max(a,40);return`M ${t} ${e} C ${t+i} ${e}, ${s-i} ${n}, ${s} ${n}`}setupCanvasInteractions(){this.viewport.addEventListener("mousedown",t=>{const e=t.target.closest(".node-port");if(e&&e.dataset.direction==="output"){t.stopPropagation(),t.preventDefault();const s=e.dataset.nodeId,n=e.dataset.portId,a=this.getPortCoordinates(s,n,"output");a&&(this.connectingFrom={nodeId:s,portId:n,x:a.x,y:a.y});return}(t.target===this.wrapper||t.target===this.viewport||t.target===this.svg)&&(this.selectNode(null),this.isPanning=!0,this.panStart={x:t.clientX-this.panOffset.x,y:t.clientY-this.panOffset.y},this.viewport.classList.add("is-panning"))}),window.addEventListener("mousemove",t=>{if(this.draggedNode){const e=(t.clientX-this.draggedNode.startX)/this.zoom,s=(t.clientY-this.draggedNode.startY)/this.zoom,n=this.nodes.find(a=>a.id===this.draggedNode.nodeId);if(n){n.x=Math.max(20,Math.round(this.draggedNode.origX+e)),n.y=Math.max(20,Math.round(this.draggedNode.origY+s));const a=document.getElementById(`nodeEl_${n.id}`);a&&(a.style.left=`${n.x}px`,a.style.top=`${n.y}px`),this.renderConnections()}return}if(this.connectingFrom){const e=this.wrapper.getBoundingClientRect(),s=(t.clientX-e.left-this.panOffset.x)/this.zoom,n=(t.clientY-e.top-this.panOffset.y)/this.zoom;this.tempWire&&(this.tempWire.setAttribute("d",this.calculateBezierPath(this.connectingFrom.x,this.connectingFrom.y,s,n)),this.tempWire.style.display="block");return}this.isPanning&&(this.panOffset.x=t.clientX-this.panStart.x,this.panOffset.y=t.clientY-this.panStart.y,this.applyTransform())}),window.addEventListener("mouseup",t=>{if(this.draggedNode&&(this.draggedNode=null,this.updateSerializedInputs()),this.isPanning&&(this.isPanning=!1,this.viewport.classList.remove("is-panning")),this.connectingFrom){this.tempWire&&(this.tempWire.style.display="none");const e=document.elementFromPoint(t.clientX,t.clientY)?.closest(".node-port");if(e&&e.dataset.direction==="input"){const s=e.dataset.nodeId,n=e.dataset.portId;s!==this.connectingFrom.nodeId&&this.addConnection(this.connectingFrom.nodeId,this.connectingFrom.portId,s,n)}this.connectingFrom=null}})}startDraggingNode(t,e){const s=this.nodes.find(n=>n.id===t);s&&(this.draggedNode={nodeId:t,startX:e.clientX,startY:e.clientY,origX:s.x,origY:s.y})}applyTransform(){this.viewport.style.transform=`translate(${this.panOffset.x}px, ${this.panOffset.y}px) scale(${this.zoom})`}zoomIn(){this.zoom=Math.min(2,this.zoom+.15),this.applyTransform()}zoomOut(){this.zoom=Math.max(.4,this.zoom-.15),this.applyTransform()}resetZoom(){this.zoom=1,this.panOffset={x:60,y:60},this.applyTransform()}addConnection(t,e,s,n){this.connections.some(i=>i.source_node===t&&i.source_output===e&&i.target_node===s&&i.target_input===n)||(this.connections.push({source_node:t,source_output:e,target_node:s,target_input:n}),this.renderConnections(),this.updateSerializedInputs())}removeConnection(t){this.connections.splice(t,1),this.renderConnections(),this.updateSerializedInputs()}addNode(t,e=null,s=null){const n=this.nodesMap.get(t);if(!n)return;const a="node_"+Math.random().toString(36).substr(2,8),i=e!==null?e:150+this.nodes.length*40,r=s!==null?s:180+this.nodes.length*30,o={id:a,type:t,name:n.name,x:i,y:r,configuration:{}},c=n.schema||{};Object.keys(c).forEach(l=>{c[l].default!==void 0&&(o.configuration[l]=JSON.parse(JSON.stringify(c[l].default)))}),this.nodes.push(o),this.renderNodes(),this.selectNode(a),this.updateSerializedInputs()}deleteNode(t){confirm("Voulez-vous vraiment supprimer ce n\u0153ud ?")&&(this.nodes=this.nodes.filter(e=>e.id!==t),this.connections=this.connections.filter(e=>e.source_node!==t&&e.target_node!==t),this.selectedNodeId===t&&this.selectNode(null),this.renderNodes(),this.renderConnections(),this.updateSerializedInputs())}selectNode(t){this.selectedNodeId=t,document.querySelectorAll(".graph-node").forEach(e=>{e.classList.toggle("is-selected",e.id===`nodeEl_${t}`)}),this.renderInspector(),t&&this.inspectNodeInConsole(t)}evaluateDisplayCondition(t,e){if(!t||typeof t!="object")return!0;if(Array.isArray(t.and))return t.and.every(r=>this.evaluateDisplayCondition(r,e));if(Array.isArray(t.or))return t.or.some(r=>this.evaluateDisplayCondition(r,e));const s=t.field;if(!s)return!0;const n=String(t.operator||"==").toLowerCase(),a=t.value,i=e?e[s]:void 0;switch(n){case"==":case"===":case"equals":return String(i)===String(a);case"!=":case"!==":case"not_equals":return String(i)!==String(a);case"in":return Array.isArray(a)?a.map(String).includes(String(i)):!1;case"not_in":return Array.isArray(a)?!a.map(String).includes(String(i)):!0;case">":return Number(i)>Number(a);case">=":return Number(i)>=Number(a);case"<":return Number(i)<Number(a);case"<=":return Number(i)<=Number(a);case"empty":case"is_empty":return i==null||i===""||Array.isArray(i)&&i.length===0;case"not_empty":case"is_not_empty":return i!=null&&i!==""&&(!Array.isArray(i)||i.length>0);case"truthy":return!!i;case"falsy":return!i;default:return String(i)===String(a)}}toggleSection(t){this._collapsedSections||(this._collapsedSections={}),this._collapsedSections[t]=!this._collapsedSections[t];const e=document.getElementById(`inspectorSection_${t}`);e&&e.classList.toggle("is-collapsed",!!this._collapsedSections[t])}updateFieldsVisibility(t){const e=this.nodes.find(r=>r.id===t);if(!e)return;const n=(this.nodesMap.get(e.type)||{schema:{}}).schema||{},a=e.configuration||{},i={};Object.keys(n).forEach(r=>{const o=n[r],c=document.getElementById(`fieldGroup_${e.id}_${r}`);if(!c)return;const l=this.evaluateDisplayCondition(o.display_if,a);l?c.classList.remove("d-none"):c.classList.add("d-none");const d=o.section||"default";i[d]||(i[d]=0),l&&i[d]++}),Object.keys(i).forEach(r=>{const o=document.getElementById(`inspectorSection_${r}`);o&&(i[r]===0?o.classList.add("d-none"):o.classList.remove("d-none"))})}renderInspector(){const t=document.getElementById("nodeInspectorDrawer"),e=document.getElementById("nodeInspectorBody"),s=document.getElementById("inspectorNodeTitle"),n=document.getElementById("inspectorNodeSubtitle"),a=document.getElementById("inspectorNodeIcon");if(!t||!e)return;if(!this.selectedNodeId){t.classList.remove("is-open");return}const i=this.nodes.find(f=>f.id===this.selectedNodeId);if(!i){t.classList.remove("is-open");return}const r=this.nodesMap.get(i.type)||{name:i.type,schema:{},sections:[]};s&&(s.innerText=i.name||r.name),n&&(n.innerText=`${r.name} \xB7 ID: ${i.id}`),a&&(a.innerHTML=this.renderNodeIcon(r.icon,16),a.style.backgroundColor=r.color||"#4f46e5");let o=`
      <div class="mb-3">
        <label class="form-label small fw-semibold">Nom d'affichage</label>
        <input type="text" class="form-control form-control-sm" value="${this.escapeHtml(i.name||"")}" oninput="canvas.updateNodeProp('${i.id}', 'name', this.value)">
      </div>
      <hr class="my-3">
    `;const c=r.schema||{},l=i.configuration||{},d=Array.isArray(r.sections)&&r.sections.length>0?r.sections:null;if(Object.keys(c).length===0)o+='<div class="p-3 bg-light rounded text-muted small text-center">Aucun param\xE8tre requis pour ce n\u0153ud.</div>';else{const f=new Map;d&&d.forEach(p=>f.set(p.id,{id:p.id,label:p.label,icon:p.icon,fields:[]})),f.set("default",{id:"default",label:"Param\xE8tres du N\u0153ud",icon:"sliders-h",fields:[]}),Object.keys(c).forEach(p=>{const m=c[p],b=m.section&&f.has(m.section)?m.section:"default";f.get(b).fields.push({key:p,field:m})}),f.forEach((p,m)=>{if(p.fields.length===0)return;const v=!!(this._collapsedSections&&this._collapsedSections[m])?"is-collapsed":"",I=p.icon?this.renderNodeIcon(p.icon,13):'<img src="/static_base_icons?name=layers&size=13" style="vertical-align:-2px">';o+=`
          <div class="inspector-section mb-3 ${v}" id="inspectorSection_${m}">
            <div class="inspector-section-header" onclick="canvas.toggleSection('${m}')">
              <div class="d-flex align-items-center gap-2">
                <span class="inspector-section-icon">${I}</span>
                <span class="inspector-section-title">${this.escapeHtml(p.label)}</span>
              </div>
              <img src="/static_base_icons?name=expand_more&size=14" class="inspector-section-chevron">
            </div>
            <div class="inspector-section-body">
        `,p.fields.forEach(({key:y,field:g})=>{const x=l[y]!==void 0?l[y]:g.default!==void 0?g.default:"",T=g.label||y,S=g.description?`<small class="text-muted d-block mt-1">${this.escapeHtml(g.description)}</small>`:"",_=this.evaluateDisplayCondition(g.display_if,l)?"":"d-none";if(o+=`<div class="schema-field-group mb-3 ${_}" id="fieldGroup_${i.id}_${y}" data-field-key="${this.escapeHtml(y)}">`,o+=`<label class="form-label small fw-semibold">${this.escapeHtml(T)}</label>`,g.type==="custom"||g.type==="custum")o+=this.renderCustomField(i,y,g,x);else if(g.type==="payload_schema")o+=this.renderPayloadSchemaField(i,y,g,x);else if(g.type==="test_payload")o+=this.renderTestPayloadField(i,y,g,x);else if(g.type==="select")o+=`<select class="form-select form-select-sm" onchange="canvas.updateNodeConfig('${i.id}', '${y}', this.value); canvas.updateFieldsVisibility('${i.id}');">`,(g.options||[]).forEach($=>{const E=String($.value)===String(x)?"selected":"";o+=`<option value="${this.escapeHtml($.value)}" ${E}>${this.escapeHtml($.label)}</option>`}),o+="</select>";else if(g.type==="textarea"){const $=`input_${i.id}_${y}`;o+=`
              <div class="position-relative">
                <textarea id="${$}" class="form-control form-control-sm font-monospace" rows="3" oninput="canvas.updateNodeConfig('${i.id}', '${y}', this.value); canvas.updateFieldsVisibility('${i.id}');">${this.escapeHtml(x)}</textarea>
                <button type="button" class="btn btn-variable-picker position-absolute" style="top: 6px; right: 6px; z-index: 5;" onclick="canvas.openVariablePicker(this, '${$}')" title="Ins\xE9rer une variable {chemin}">{}</button>
              </div>
            `}else if(g.type==="boolean"){const $=x?"checked":"";o+=`
              <div class="form-check form-switch mt-1">
                <input class="form-check-input" type="checkbox" id="cfg_${i.id}_${y}" ${$} onchange="canvas.updateNodeConfig('${i.id}', '${y}', this.checked); canvas.updateFieldsVisibility('${i.id}');">
                <label class="form-check-label small" for="cfg_${i.id}_${y}">Actif</label>
              </div>
            `}else if(g.type==="json"){const $=typeof x=="object"?JSON.stringify(x,null,2):String(x||"{}");o+=`<textarea class="form-control form-control-sm font-monospace" rows="4" placeholder="{}" onchange="try { canvas.updateNodeConfig('${i.id}', '${y}', JSON.parse(this.value)); canvas.updateFieldsVisibility('${i.id}'); } catch(e) { alert('Format JSON invalide'); }">${this.escapeHtml($)}</textarea>`}else{const $=`input_${i.id}_${y}`;o+=`
              <div class="input-group input-group-sm">
                <input type="${g.type==="number"?"number":"text"}" id="${$}" class="form-control" value="${this.escapeHtml(x)}" oninput="canvas.updateNodeConfig('${i.id}', '${y}', this.value); canvas.updateFieldsVisibility('${i.id}');">
                <button type="button" class="btn btn-variable-picker" onclick="canvas.openVariablePicker(this, '${$}')" title="Ins\xE9rer une variable {chemin}">{}</button>
              </div>
            `}o+=S,o+="</div>"}),o+=`
            </div>
          </div>
        `})}const h=i.type&&(i.type.includes("trigger")||i.type.startsWith("core.trigger"));let u='{"amount": 1500, "status": "paid", "customer": {"id": "c1", "name": "Alice"}}';h&&(i.configuration&&i.configuration.test_payload&&typeof i.configuration.test_payload=="object"&&Object.keys(i.configuration.test_payload).length>0?u=JSON.stringify(i.configuration.test_payload,null,2):this.simulationInitialPayload&&typeof this.simulationInitialPayload=="object"&&Object.keys(this.simulationInitialPayload).length>0?u=JSON.stringify(this.simulationInitialPayload,null,2):u="{}"),o+=`
      <hr class="my-3">
      <div class="card bg-light border-0 p-3 rounded-3">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <h6 class="fw-bold small mb-0 d-flex align-items-center gap-1">
            <img src="/static_base_icons?name=play_arrow&size=14" style="vertical-align:-2px"> Tester ce N\u0153ud en Isolation
          </h6>
          <span class="badge bg-secondary-subtle text-secondary" style="font-size: 10px;">Test Unitaire</span>
        </div>
        <p class="x-small text-muted mb-2">
          Ex\xE9cute <strong>uniquement ce n\u0153ud</strong> avec sa configuration actuelle et le payload simul\xE9 ci-dessous. Permet de v\xE9rifier les transformations, calculs et embranchements sans ex\xE9cuter l'ensemble du workflow.
        </p>
        <div class="mb-2">
          <label class="form-label x-small fw-semibold text-muted mb-1">Donn\xE9es d'entr\xE9e simul\xE9es (JSON) :</label>
          <textarea id="nodeTestSimulatedInput" class="form-control font-monospace x-small" rows="3" placeholder='{"amount": 1500, "status": "paid"}'>${this.escapeHtml(u)}</textarea>
        </div>
        <button type="button" class="btn btn-outline-primary btn-sm w-100 d-flex align-items-center justify-content-center gap-1" onclick="canvas.testCurrentNode('${i.id}')">
          <img src="/static_base_icons?name=science&size=14" style="vertical-align:-2px"> Lancer le test du n\u0153ud
        </button>
        <div id="nodeTestResultContainer" class="mt-2 d-none">
          <div class="x-small fw-semibold text-muted">R\xE9sultat d'ex\xE9cution :</div>
          <pre id="nodeTestResultOutput" class="bg-dark text-white p-2 rounded mt-1 font-monospace x-small" style="max-height: 180px; overflow-y: auto;"></pre>
        </div>
      </div>
    `,e.innerHTML=o,t.classList.add("is-open"),this.updateFieldsVisibility(i.id)}updateNodeProp(t,e,s){const n=this.nodes.find(i=>i.id===t);if(!n)return;n[e]=s;const a=document.querySelector(`#nodeEl_${t} .graph-node-title`);a&&(a.innerText=s),this.updateSerializedInputs()}updateNodeConfig(t,e,s){const n=this.nodes.find(a=>a.id===t);n&&(n.configuration||(n.configuration={}),n.configuration[e]=s,this.updateSerializedInputs())}renderNodeIcon(t,e=16){return t?t.startsWith("/")||t.startsWith("http://")||t.startsWith("https://")?`<img src="${this.escapeHtml(t)}" style="width:${e}px; height:${e}px; object-fit:contain; vertical-align:middle;">`:t.startsWith("fa-")||t.startsWith("fas ")||t.startsWith("far ")||t.startsWith("fab ")?`<i class="${this.escapeHtml(t)}"></i>`:`<img src="/static_base_icons?name=${encodeURIComponent(t)}&fill=white&size=${e}" alt="${this.escapeHtml(t)}" style="width:${e}px; height:${e}px; vertical-align:middle;">`:`<img src="/static_base_icons?name=data_object&fill=white&size=${e}" style="width:${e}px; height:${e}px; vertical-align:middle;">`}async testCurrentNode(t){const e=this.nodes.find(r=>r.id===t);if(!e)return;const s=document.getElementById("nodeTestResultContainer"),n=document.getElementById("nodeTestResultOutput"),a=document.getElementById("nodeTestSimulatedInput");if(!s||!n)return;let i={test:!0};if(a&&a.value.trim())try{i=JSON.parse(a.value.trim())}catch(r){s.classList.remove("d-none"),n.innerHTML=`<span class="text-danger">Erreur de syntaxe JSON dans les donn\xE9es d'entr\xE9e : ${this.escapeHtml(r.message)}</span>`;return}s.classList.remove("d-none"),n.innerHTML='<span class="text-warning"><img src="/static_base_icons?name=sync&size=12" class="me-1" style="vertical-align:-2px"> Ex\xE9cution du n\u0153ud en cours...</span>';try{const r=await fetch("/api/melodi_automation/nodes/test-step",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:e.id,node_type:e.type,configuration:e.configuration||{},input_data:i,context:{payload:i,steps:{}}})}),o=await r.json();if(r.ok&&o.status==="success"){let c="";Array.isArray(o.output_variables)&&o.output_variables.length>0&&(c=`
            <div class="mb-2 p-2 bg-secondary-subtle rounded border">
              <div class="x-small fw-bold text-dark mb-1 d-flex align-items-center gap-1">
                <img src="/static_base_icons?name=tag&size=12" style="vertical-align:-2px"> Variables extraites de la sortie :
              </div>
              <div class="d-flex flex-wrap gap-1">
                ${o.output_variables.map(l=>`<span class="badge bg-white text-dark border p-1" style="font-size:10px;">
                    <span class="n8n-type-badge ${`type-${(l.type||"other").toLowerCase()}`} me-1">${this.escapeHtml(l.type)}</span>
                    <code>{${this.escapeHtml(l.path)}}</code>
                  </span>`).join("")}
              </div>
            </div>
          `),n.innerHTML=`
          ${c}
          <div class="x-small text-success mb-1">\u2713 Ex\xE9cut\xE9 en ${o.duration_ms||0}ms (Port activ\xE9: ${(o.active_ports||["main"]).join(", ")})</div>
          <pre class="bg-dark text-white p-2 rounded mb-0 font-monospace x-small" style="max-height: 180px; overflow-y: auto;">${this.escapeHtml(JSON.stringify(o.output_data,null,2))}</pre>
        `}else{let c=this.escapeHtml(o.error||o.message||"\xC9chec");o.output_data&&Array.isArray(o.output_data.validation_errors)&&o.output_data.validation_errors.length>0&&(c+='<br><ul class="mt-1 mb-0 ps-3">'+o.output_data.validation_errors.map(l=>`<li><strong>${this.escapeHtml(l.field)}</strong>: ${this.escapeHtml(l.message)}</li>`).join("")+"</ul>"),n.innerHTML=`
          <div class="x-small text-danger mb-1">\u2717 ${c}</div>
          ${o.output_data?`<pre class="bg-dark text-danger-subtle p-2 rounded mb-0 font-monospace x-small" style="max-height: 180px; overflow-y: auto;">${this.escapeHtml(JSON.stringify(o.output_data,null,2))}</pre>`:""}
        `}}catch(r){n.innerHTML=`<span class="text-danger">\u2717 Erreur r\xE9seau : ${this.escapeHtml(r.message)}</span>`}}updateSerializedInputs(){const t=document.getElementById("nodesJsonInput"),e=document.getElementById("connectionsJsonInput"),s=document.getElementById("customTypesJsonInput");t&&(t.value=JSON.stringify(this.nodes)),e&&(e.value=JSON.stringify(this.connections)),s&&(s.value=JSON.stringify(this.customTypes||[]));const n=document.getElementById("customTypesCountBadge");n&&(n.innerText=String((this.customTypes||[]).length))}escapeHtml(t){return t?String(t).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;"):""}renderCustomField(t,e,s,n){const a=`${t.id}_${e}`,i=this._customFieldModes[a]||"visual";let r=[];if(Array.isArray(n))r=n.map(c=>{if(typeof c=="object"&&c!==null){if("key"in c)return{key:c.key||"",value:c.value!==void 0?c.value:"",type:c.type||"string"};{const l=Object.keys(c)[0]||"";return{key:l,value:c[l]!==void 0?c[l]:"",type:"string"}}}return{key:String(c),value:"",type:"string"}});else if(typeof n=="object"&&n!==null)"key"in n&&"value"in n?r=[{key:n.key||"",value:n.value!==void 0?n.value:"",type:n.type||"string"}]:r=Object.entries(n).map(([c,l])=>({key:c,value:typeof l=="object"?JSON.stringify(l):l,type:typeof l=="number"?"number":typeof l=="boolean"?"boolean":typeof l=="object"?"json":"string"}));else if(typeof n=="string"&&n.trim())try{const c=JSON.parse(n);return this.renderCustomField(t,e,s,c)}catch{r=[{key:"var1",value:n,type:"string"}]}r.length===0&&(r=[{key:"",value:"",type:"string"}]),(!t.configuration[e]||i==="visual"&&!Array.isArray(t.configuration[e]))&&(t.configuration[e]=r);let o=`
      <div class="custom-field-container mb-3" data-field-key="${this.escapeHtml(e)}">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <label class="form-label small fw-semibold mb-0">${this.escapeHtml(s.label||e)}</label>
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-secondary py-0 px-2 ${i==="visual"?"active":""}" onclick="canvas.switchCustomFieldMode('${t.id}', '${e}', 'visual')">Visuel</button>
            <button type="button" class="btn btn-outline-secondary py-0 px-2 ${i==="code"?"active":""}" onclick="canvas.switchCustomFieldMode('${t.id}', '${e}', 'code')">Code JSON</button>
          </div>
        </div>
        ${s.description?`<small class="text-muted d-block mb-2">${this.escapeHtml(s.description)}</small>`:""}
    `;if(i==="visual")o+=`
        <div class="custom-var-table">
          <div class="custom-var-table-header d-flex gap-1 mb-1 px-1 text-muted x-small fw-semibold">
            <div style="flex: 1.2;">Nom variable (cl\xE9)</div>
            <div style="width: 85px;">Type</div>
            <div style="flex: 1.8;">Valeur / Expression</div>
            <div style="width: 32px;"></div>
          </div>
          <div class="custom-var-rows-container">
      `,r.forEach((c,l)=>{const d=`customVal_${t.id}_${e}_${l}`;o+=`
          <div class="custom-var-row d-flex align-items-center gap-1 mb-1">
            <input type="text" class="form-control form-control-sm font-monospace" style="flex: 1.2; font-size: 11px;" placeholder="cl\xE9" value="${this.escapeHtml(c.key)}" oninput="canvas.updateCustomFieldRow('${t.id}', '${e}', ${l}, 'key', this.value)">
            <select class="form-select form-select-sm" style="width: 85px; font-size: 11px;" onchange="canvas.updateCustomFieldRow('${t.id}', '${e}', ${l}, 'type', this.value)">
              <option value="string" ${c.type==="string"?"selected":""}>Texte</option>
              <option value="number" ${c.type==="number"?"selected":""}>Nombre</option>
              <option value="boolean" ${c.type==="boolean"?"selected":""}>Bool\xE9en</option>
              <option value="json" ${c.type==="json"?"selected":""}>JSON</option>
              <option value="expression" ${c.type==="expression"?"selected":""}>Expr.</option>
            </select>
            <div class="input-group input-group-sm" style="flex: 1.8;">
              <input type="text" id="${d}" class="form-control font-monospace" style="font-size: 11px;" placeholder="valeur ou {var}" value="${this.escapeHtml(String(c.value!==void 0?c.value:""))}" oninput="canvas.updateCustomFieldRow('${t.id}', '${e}', ${l}, 'value', this.value)">
              <button type="button" class="btn btn-variable-picker" onclick="canvas.openVariablePicker(this, '${d}')" title="Ins\xE9rer une variable {chemin}">{}</button>
            </div>
            <button type="button" class="btn btn-outline-danger btn-sm p-1" style="width: 32px; height: 31px;" onclick="canvas.removeCustomFieldRow('${t.id}', '${e}', ${l})" title="Supprimer">
              <img src="/static_base_icons?name=delete&fill=%23dc3545&size=14" style="vertical-align:-2px">
            </button>
          </div>
        `}),o+=`
          </div>
          <button type="button" class="btn btn-outline-primary btn-sm mt-2 w-100 d-flex align-items-center justify-content-center gap-1" onclick="canvas.addCustomFieldRow('${t.id}', '${e}')">
            <img src="/static_base_icons?name=add&size=14" style="vertical-align:-2px"> Ajouter une variable
          </button>
        </div>
      `;else{const c=typeof t.configuration[e]=="string"?t.configuration[e]:JSON.stringify(t.configuration[e]||r,null,2);o+=`
        <div class="custom-code-container">
          <textarea class="form-control font-monospace custom-code-area" rows="7" style="font-size: 11px;" oninput="canvas.updateCustomFieldFromCode('${t.id}', '${e}', this.value)">${this.escapeHtml(c)}</textarea>
          <div id="customCodeFeedback_${t.id}_${e}" class="text-muted x-small mt-1">JSON synchronis\xE9 avec le mode visuel.</div>
        </div>
      `}return o+="</div>",o}switchCustomFieldMode(t,e,s){this._customFieldModes[`${t}_${e}`]=s,this.renderInspector()}addCustomFieldRow(t,e){const s=this.nodes.find(n=>n.id===t);s&&(Array.isArray(s.configuration[e])||(s.configuration[e]=[]),s.configuration[e].push({key:"",value:"",type:"string"}),this.updateSerializedInputs(),this.renderInspector())}updateCustomFieldRow(t,e,s,n,a){const i=this.nodes.find(r=>r.id===t);!i||!Array.isArray(i.configuration[e])||(i.configuration[e][s]||(i.configuration[e][s]={key:"",value:"",type:"string"}),i.configuration[e][s][n]=a,this.updateSerializedInputs())}removeCustomFieldRow(t,e,s){const n=this.nodes.find(a=>a.id===t);!n||!Array.isArray(n.configuration[e])||(n.configuration[e].splice(s,1),this.updateSerializedInputs(),this.renderInspector())}updateCustomFieldFromCode(t,e,s){const n=this.nodes.find(i=>i.id===t);if(!n)return;const a=document.getElementById(`customCodeFeedback_${t}_${e}`);try{const i=JSON.parse(s);n.configuration[e]=i,this.updateSerializedInputs(),a&&(a.className="text-success x-small mt-1",a.innerText="\u2713 JSON valide et synchronis\xE9.")}catch(i){a&&(a.className="text-danger x-small mt-1",a.innerText="\u2717 Syntaxe JSON invalide : "+i.message)}}renderPayloadSchemaField(t,e,s,n){const a=`${t.id}_${e}`,i=this._customFieldModes[a]||"visual",r=t.configuration?.validation_mode==="strict";let o=[];Array.isArray(n)?o=n.map(l=>typeof l=="object"&&l!==null?{key:l.key||l.name||"",type:l.type||"string",required:l.required!==void 0?!!l.required:!0,default:l.default!==void 0&&l.default!==null?l.default:"",description:l.description||"",custom_type:l.custom_type||l.custom_type_ref||"",custom_type_ref:l.custom_type_ref||l.custom_type||"",item_type:l.item_type||""}:{key:String(l),type:"string",required:!0,default:"",description:"",custom_type:"",custom_type_ref:"",item_type:""}):typeof n=="object"&&n!==null&&(o=Object.entries(n).map(([l,d])=>typeof d=="object"&&d!==null?{key:l,type:d.type||"string",required:d.required!==void 0?!!d.required:!0,default:d.default!==void 0&&d.default!==null?d.default:"",description:d.description||"",custom_type:d.custom_type||d.custom_type_ref||"",custom_type_ref:d.custom_type_ref||d.custom_type||"",item_type:d.item_type||""}:{key:l,type:String(d||"string"),required:!0,default:"",description:"",custom_type:"",custom_type_ref:"",item_type:""})),o.length===0&&(o=[{key:"",type:"string",required:!0,default:"",description:"",custom_type:"",custom_type_ref:"",item_type:""}]),(!t.configuration[e]||i==="visual"&&!Array.isArray(t.configuration[e]))&&(t.configuration[e]=o);let c=`
      <div class="payload-schema-container mb-3" data-field-key="${this.escapeHtml(e)}">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <label class="form-label small fw-semibold mb-0">
            <img src="/static_base_icons?name=category&size=14" style="vertical-align:-2px" class="me-1"> ${this.escapeHtml(s.label||e)}
          </label>
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-secondary py-0 px-2 ${i==="visual"?"active":""}" onclick="canvas.switchPayloadSchemaMode('${t.id}', '${e}', 'visual')">Visuel</button>
            <button type="button" class="btn btn-outline-secondary py-0 px-2 ${i==="code"?"active":""}" onclick="canvas.switchPayloadSchemaMode('${t.id}', '${e}', 'code')">Code JSON</button>
          </div>
        </div>
        ${s.description?`<small class="text-muted d-block mb-2">${this.escapeHtml(s.description)}</small>`:""}
    `;if(r||(c+=`
        <div class="alert alert-light border py-1 px-2 mb-2 x-small text-muted d-flex align-items-center gap-1">
          <img src="/static_base_icons?name=info&size=14" style="vertical-align:-2px">
          <span>Mode <strong>Permissif</strong> actif : les valeurs par d\xE9faut sont inject\xE9es et la validation stricte s'active si vous s\xE9lectionnez <strong>Structure stricte</strong>.</span>
        </div>
      `),i==="visual"){const l=this.customTypes||[];c+=`
        <div class="payload-schema-table">
          <div class="d-flex gap-1 mb-1 px-1 text-muted x-small fw-semibold">
            <div style="flex: 1.2;">Champ (cl\xE9)</div>
            <div style="width: 125px;">Type attendu</div>
            <div style="flex: 1.0;">Valeur par d\xE9faut</div>
            <div style="width: 50px;" class="text-center">Requis</div>
            <div style="width: 28px;"></div>
          </div>
          <div class="payload-schema-rows-container">
      `,o.forEach((d,h)=>{const u=String(d.type||"string"),f=String(d.custom_type||d.custom_type_ref||(u.startsWith("custom:")?u.split(":")[1]:u!=="custom"?u:"")),p=u==="custom"||u.startsWith("custom:")||l.some(v=>v.name===u||v.name===f),m=p?f||l.find(v=>v.name===u)?.name||"":u,b=l.find(v=>v.name===m);c+=`
          <div class="mb-1 p-1 bg-white rounded border">
            <div class="d-flex align-items-center gap-1">
              <input type="text" class="form-control form-control-sm font-monospace" style="flex: 1.2; font-size: 11px;" placeholder="ex: order_id" value="${this.escapeHtml(d.key)}" oninput="canvas.updatePayloadSchemaRow('${t.id}', '${e}', ${h}, 'key', this.value)">
              <select class="form-select form-select-sm" style="width: 125px; font-size: 11px;" onchange="canvas.onPayloadSchemaTypeChanged('${t.id}', '${e}', ${h}, this.value)">
                <optgroup label="Types Primitifs">
                  <option value="string" ${!p&&u==="string"?"selected":""}>Texte (str)</option>
                  <option value="number" ${!p&&u==="number"?"selected":""}>Nombre (float)</option>
                  <option value="integer" ${!p&&(u==="integer"||u==="int")?"selected":""}>Entier (int)</option>
                  <option value="boolean" ${!p&&(u==="boolean"||u==="bool")?"selected":""}>Bool\xE9en</option>
                  <option value="array" ${!p&&u==="array"?"selected":""}>Tableau []</option>
                  <option value="object" ${!p&&u==="object"?"selected":""}>Objet {}</option>
                  <option value="any" ${!p&&u==="any"?"selected":""}>Tous (any)</option>
                </optgroup>
                <optgroup label="Formats Sp\xE9cifiques">
                  <option value="email" ${!p&&u==="email"?"selected":""}>Email</option>
                  <option value="date" ${!p&&(u==="date"||u==="datetime")?"selected":""}>Date / Heure</option>
                  <option value="uuid" ${!p&&u==="uuid"?"selected":""}>UUID</option>
                </optgroup>
                ${l.length>0?`
                <optgroup label="Types Personnalis\xE9s (Structs)">
                  ${l.map(v=>{const I=p&&(m===v.name||f===v.name||u===v.name);return`<option value="custom:${this.escapeHtml(v.name)}" ${I?"selected":""}>\u{1F4E6} ${this.escapeHtml(v.name)}</option>`}).join("")}
                </optgroup>
                `:""}
              </select>
              <input type="text" class="form-control form-control-sm font-monospace" style="flex: 1.0; font-size: 11px;" placeholder="D\xE9faut (opt.)" value="${this.escapeHtml(d.default!==void 0&&d.default!==null?String(d.default):"")}" oninput="canvas.updatePayloadSchemaRow('${t.id}', '${e}', ${h}, 'default', this.value)" title="Valeur inject\xE9e automatiquement si omise">
              <div style="width: 50px;" class="text-center form-check form-switch m-0 d-flex justify-content-center">
                <input class="form-check-input" type="checkbox" ${d.required?"checked":""} onchange="canvas.updatePayloadSchemaRow('${t.id}', '${e}', ${h}, 'required', this.checked)" title="Champ obligatoire">
              </div>
              <button type="button" class="btn btn-outline-danger btn-sm p-1" style="width: 28px; height: 30px;" onclick="canvas.removePayloadSchemaRow('${t.id}', '${e}', ${h})" title="Supprimer ce champ">
                <img src="/static_base_icons?name=delete&fill=%23dc3545&size=14" style="vertical-align:-2px">
              </button>
            </div>
            ${b?`
            <div class="mt-1 pt-1 border-top d-flex align-items-center justify-content-between x-small text-muted" style="font-size: 10px;">
              <span>
                <img src="/static_base_icons?name=layers&size=12" class="me-1" style="vertical-align:-2px">
                Structure <strong>${this.escapeHtml(b.name)}</strong> : ${(b.fields||[]).map(v=>`<code class="text-dark">${this.escapeHtml(v.key)}:${this.escapeHtml(v.type)}</code>`).join(", ")||"aucun champ"}
              </span>
              <button type="button" class="btn btn-link btn-sm p-0 text-decoration-none x-small" onclick="canvas.openCustomTypesModal('${this.escapeHtml(b.id)}')">Modifier</button>
            </div>
            `:""}
          </div>
        `}),c+=`
          </div>
          <div class="d-flex gap-2 mt-2">
            <button type="button" class="btn btn-outline-primary btn-sm flex-grow-1" onclick="canvas.addPayloadSchemaRow('${t.id}', '${e}')">
              <img src="/static_base_icons?name=add&size=13" class="me-1" style="vertical-align:-2px"> Ajouter un champ
            </button>
            <button type="button" class="btn btn-outline-secondary btn-sm" onclick="canvas.openCustomTypesModal()" title="Cr\xE9er ou g\xE9rer les structures r\xE9utilisables">
              <img src="/static_base_icons?name=category&size=13" class="me-1" style="vertical-align:-2px"> G\xE9rer les Types
            </button>
            <button type="button" class="btn btn-outline-secondary btn-sm" onclick="canvas.inferPayloadSchema('${t.id}', '${e}')" title="D\xE9duire les types automatiquement depuis le payload de test">
              <img src="/static_base_icons?name=auto_fix_high&size=13" class="me-1" style="vertical-align:-2px"> D\xE9duire
            </button>
          </div>
        </div>
      `}else{const l=typeof t.configuration[e]=="string"?t.configuration[e]:JSON.stringify(t.configuration[e]||o,null,2);c+=`
        <div class="payload-schema-code-container">
          <textarea class="form-control font-monospace custom-code-area" rows="7" style="font-size: 11px;" oninput="canvas.updatePayloadSchemaFromCode('${t.id}', '${e}', this.value)">${this.escapeHtml(l)}</textarea>
          <div id="payloadSchemaCodeFeedback_${t.id}_${e}" class="text-muted x-small mt-1">JSON synchronis\xE9 avec le mode visuel (champs 'key', 'type', 'required', 'default').</div>
        </div>
      `}return c+="</div>",c}switchPayloadSchemaMode(t,e,s){this._customFieldModes[`${t}_${e}`]=s,this.renderInspector()}addPayloadSchemaRow(t,e){const s=this.nodes.find(n=>n.id===t);s&&(Array.isArray(s.configuration[e])||(s.configuration[e]=[]),s.configuration[e].push({key:"",type:"string",required:!0,default:"",description:""}),(!s.configuration.validation_mode||s.configuration.validation_mode==="any")&&(s.configuration.validation_mode="strict"),this.updateSerializedInputs(),this.renderInspector())}onPayloadSchemaTypeChanged(t,e,s,n){const a=this.nodes.find(r=>r.id===t);if(!a||!Array.isArray(a.configuration[e]))return;a.configuration[e][s]||(a.configuration[e][s]={key:"",type:"string",required:!0,default:"",description:""});const i=a.configuration[e][s];if(n.startsWith("custom:")){const r=n.split(":",2)[1];i.type="custom",i.custom_type=r,i.custom_type_ref=r}else i.type=n,delete i.custom_type,delete i.custom_type_ref;this.updateSerializedInputs(),this.renderInspector()}updatePayloadSchemaRow(t,e,s,n,a){const i=this.nodes.find(r=>r.id===t);!i||!Array.isArray(i.configuration[e])||(i.configuration[e][s]||(i.configuration[e][s]={key:"",type:"string",required:!0,default:"",description:""}),i.configuration[e][s][n]=a,this.updateSerializedInputs())}removePayloadSchemaRow(t,e,s){const n=this.nodes.find(a=>a.id===t);!n||!Array.isArray(n.configuration[e])||(n.configuration[e].splice(s,1),this.updateSerializedInputs(),this.renderInspector())}updatePayloadSchemaFromCode(t,e,s){const n=this.nodes.find(i=>i.id===t);if(!n)return;const a=document.getElementById(`payloadSchemaCodeFeedback_${t}_${e}`);try{const i=JSON.parse(s);n.configuration[e]=i,Array.isArray(i)&&i.length>0&&(!n.configuration.validation_mode||n.configuration.validation_mode==="any")&&(n.configuration.validation_mode="strict"),this.updateSerializedInputs(),a&&(a.className="text-success x-small mt-1",a.innerText="\u2713 JSON valide et synchronis\xE9.")}catch(i){a&&(a.className="text-danger x-small mt-1",a.innerText="\u2717 Syntaxe JSON invalide : "+i.message)}}inferPayloadSchema(t,e){const s=this.nodes.find(r=>r.id===t);if(!s)return;const n=this.getEffectiveTestPayload();if(!n||Object.keys(n).length===0){alert("Aucun payload de test disponible pour d\xE9duire le sch\xE9ma. Renseignez un payload de test ci-dessous ou ouvrez le modal de payload.");return}const a=[],i=(r,o="")=>{typeof r=="object"&&r!==null&&(Array.isArray(r)?a.push({key:o,type:"array",required:!0,default:""}):Object.entries(r).forEach(([c,l])=>{const d=o?`${o}.${c}`:c;typeof l=="object"&&l!==null&&!Array.isArray(l)?(a.push({key:d,type:"object",required:!0,default:""}),i(l,d)):Array.isArray(l)?a.push({key:d,type:"array",required:!0,default:""}):typeof l=="number"?a.push({key:d,type:"number",required:!0,default:String(l)}):typeof l=="boolean"?a.push({key:d,type:"boolean",required:!0,default:String(l)}):a.push({key:d,type:"string",required:!0,default:String(l||"")})}))};i(n),a.length>0&&(s.configuration[e]=a,this.updateSerializedInputs(),this.renderInspector())}renderTestPayloadField(t,e,s,n){let a="";return typeof n=="object"&&n!==null?a=JSON.stringify(n,null,2):typeof n=="string"&&n.trim()?a=n:a="{}",`
      <div class="test-payload-box mb-3 border rounded p-2 bg-light">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <label class="form-label small fw-semibold mb-0 text-primary d-flex align-items-center gap-1">
            <img src="/static_base_icons?name=science&size=14" style="vertical-align:-2px"> ${this.escapeHtml(s.label||"Payload de test")}
          </label>
          <span class="badge bg-warning-subtle text-dark border x-small">Build uniquement</span>
        </div>
        <small class="text-muted d-block mb-2" style="font-size: 11px;">
          <img src="/static_base_icons?name=shield&size=13" class="me-1" style="vertical-align:-2px">
          Donn\xE9es simul\xE9es pour tester le workflow dans le Builder. <strong>Strictement ignor\xE9 en production</strong>.
        </small>
        <textarea id="testPayloadInput_${t.id}" class="form-control font-monospace" rows="6" style="font-size: 11px;" oninput="canvas.updateTestPayloadFromInspector('${t.id}', '${e}', this.value)">${this.escapeHtml(a)}</textarea>
        <div id="testPayloadFeedback_${t.id}" class="text-muted x-small mt-1">Payload de simulation synchronis\xE9.</div>
        <div class="d-flex gap-2 mt-2">
          <button type="button" class="btn btn-outline-primary btn-sm flex-grow-1 d-flex align-items-center justify-content-center gap-1" style="font-size: 11px;" onclick="canvas.generateAndFillTestPayload('${t.id}', '${e}')" title="G\xE9n\xE9rer un payload de test depuis les cl\xE9s et valeurs par d\xE9faut du sch\xE9ma">
            <img src="/static_base_icons?name=auto_fix_high&size=12" style="vertical-align:-2px"> G\xE9n\xE9rer depuis le sch\xE9ma
          </button>
          <button type="button" class="btn btn-primary btn-sm d-flex align-items-center justify-content-center gap-1" style="font-size: 11px;" onclick="canvas.runSimulationWithNodeTestPayload('${t.id}', '${e}')" title="Simuler imm\xE9diatement le graphe avec ce payload">
            <img src="/static_base_icons?name=play_arrow&fill=white&size=12" style="vertical-align:-2px"> Simuler
          </button>
        </div>
      </div>
    `}updateTestPayloadFromInspector(t,e,s){const n=this.nodes.find(i=>i.id===t);if(!n)return;const a=document.getElementById(`testPayloadFeedback_${t}`);try{const i=JSON.parse(s||"{}");n.configuration||(n.configuration={}),n.configuration[e]=i,this.simulationInitialPayload=i,this.updateSerializedInputs(),a&&(a.className="text-success x-small mt-1",a.innerText="\u2713 Payload de test valide et m\xE9moris\xE9.")}catch(i){a&&(a.className="text-danger x-small mt-1",a.innerText="\u2717 Syntaxe JSON invalide : "+i.message)}}generateAndFillTestPayload(t,e){const s=this.nodes.find(i=>i.id===t);if(!s)return;const n=s.configuration?.payload_schema||[],a=this.generateTestPayloadFromSchema(n);s.configuration||(s.configuration={}),s.configuration[e]=a,this.simulationInitialPayload=a,this.updateSerializedInputs(),this.renderInspector()}runSimulationWithNodeTestPayload(t,e){const s=this.nodes.find(n=>n.id===t);if(s&&s.configuration&&s.configuration[e]){let n=s.configuration[e];if(typeof n=="string")try{n=JSON.parse(n)}catch{n={}}this.simulationInitialPayload=n}this.runGraphSimulation()}generateTestPayloadFromSchema(t){const e={};if(!t)return e;let s=[];Array.isArray(t)?s=t:typeof t=="object"&&(s=Object.entries(t).map(([o,c])=>({key:o,...typeof c=="object"&&c!==null?c:{type:String(c)}})));const n=(o,c,l)=>{const d=c.split(".");let h=o;for(let u=0;u<d.length-1;u++){const f=d[u];(!h[f]||typeof h[f]!="object"||Array.isArray(h[f]))&&(h[f]={}),h=h[f]}h[d[d.length-1]]=l},a=this.customTypes||[],i=new Map;a.forEach(o=>{o.name&&(i.set(o.name,o),i.set(o.name.toLowerCase(),o))});const r=(o,c,l,d,h=0)=>{if(h>5)return{};const u=(o||"string").toLowerCase().trim(),f=l||(u.startsWith("custom:")?u.split(":")[1]:u==="custom"?l:u),p=i.get(f)||i.get(f?.toLowerCase());if(p){const m={};return(p.fields||[]).forEach(b=>{m[b.key]=r(b.type,b.default,b.custom_type||b.custom_type_ref,b.key,h+1)}),m}if(c!=null&&String(c).trim()!==""){const m=String(c).trim();if(u==="number"||u==="float")return Number(m)||0;if(u==="integer"||u==="int")return parseInt(m,10)||0;if(u==="boolean"||u==="bool")return["true","1","yes","oui"].includes(m.toLowerCase());if(u==="array")try{return JSON.parse(m)}catch{return[]}if(u==="object")try{return JSON.parse(m)}catch{return{}}return m}return u==="number"||u==="float"?42:u==="integer"||u==="int"?10:u==="boolean"||u==="bool"?!0:u==="array"?[]:u==="object"?{}:u==="email"?`contact@${d||"example"}.com`:u==="date"||u==="datetime"?new Date().toISOString().split("T")[0]:u==="uuid"?"a1b2c3d4-e5f6-7890-abcd-ef1234567890":u==="any"?"exemple":`valeur_${d.split(".").pop()}`};return s.forEach(o=>{const c=(o.key||o.name||"").trim();if(!c)return;const l=o.type||"string",d=o.custom_type||o.custom_type_ref,h=r(l,o.default,d,c,0);n(e,c,h)}),e}getEffectiveTestPayload(){if(this.simulationInitialPayload!==null&&this.simulationInitialPayload!==void 0)return this.simulationInitialPayload;const t=this.nodes.find(e=>e.type&&(e.type.includes("trigger")||e.type.startsWith("core.trigger")));if(t&&t.configuration){if(t.configuration.test_payload!==void 0&&t.configuration.test_payload!==null&&t.configuration.test_payload!==""){let e=t.configuration.test_payload;if(typeof e=="string")try{e=JSON.parse(e)}catch{e=null}if(e!==null&&typeof e=="object")return e}if(Array.isArray(t.configuration.payload_schema)&&t.configuration.payload_schema.length>0){const e=this.generateTestPayloadFromSchema(t.configuration.payload_schema);if(Object.keys(e).length>0)return e}}return{}}openVariablePicker(t,e){this.closeVariablePicker();const s=this.getAvailableVariables(),n=document.createElement("div");n.id="activeVariablePickerPopover",n.className="variable-picker-popover",n.innerHTML=`
      <div class="variable-picker-header">
        <div class="input-group input-group-sm mb-1">
          <span class="input-group-text bg-white"><img src="/static_base_icons?name=search&size=11" style="vertical-align:-2px"></span>
          <input type="text" id="varPickerSearchInput" class="form-control form-control-sm" placeholder="Rechercher une variable..." autofocus>
        </div>
        <div class="variable-picker-categories" id="varPickerCategories">
          <button type="button" class="variable-picker-cat-btn is-active" data-cat="all">Tous</button>
          <button type="button" class="variable-picker-cat-btn" data-cat="node_io">N\u0153ud E/S</button>
          <button type="button" class="variable-picker-cat-btn" data-cat="payload">Payload</button>
          <button type="button" class="variable-picker-cat-btn" data-cat="steps">\xC9tapes</button>
          <button type="button" class="variable-picker-cat-btn" data-cat="context">Contexte</button>
        </div>
      </div>
      <div class="variable-picker-list" id="varPickerList"></div>
    `,document.body.appendChild(n);let a="all";const i=(h="")=>{const u=n.querySelector("#varPickerList");if(!u)return;const f=h.toLowerCase().trim(),p=s.filter(m=>{const b=!f||m.path.toLowerCase().includes(f)||m.name&&m.name.toLowerCase().includes(f)||m.source&&m.source.toLowerCase().includes(f)||m.node_name&&m.node_name.toLowerCase().includes(f),v=a==="all"||m.category===a;return b&&v});if(p.length===0){u.innerHTML='<div class="p-3 text-center text-muted x-small">Aucune variable correspondante.</div>';return}u.innerHTML=p.map(m=>{const b=m.node_name?`${m.node_name} (${m.source||""})`:m.source||"",v=`type-${(m.type||"other").toLowerCase()}`;return`
          <div class="variable-picker-item" data-path="${this.escapeHtml(m.path)}">
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 68%;">
              <span class="variable-picker-path">{${this.escapeHtml(m.path)}}</span>
              <span class="n8n-type-badge ${v} ms-1">${this.escapeHtml(m.type||"var")}</span>
              ${b?`<small class="text-muted ms-1" style="font-size: 10px;">(${this.escapeHtml(b)})</small>`:""}
            </div>
            <span class="variable-picker-preview" title="${this.escapeHtml(String(m.preview??""))}">${this.escapeHtml(String(m.preview??""))}</span>
          </div>
        `}).join(""),u.querySelectorAll(".variable-picker-item").forEach(m=>{m.addEventListener("click",()=>{const b=m.dataset.path;this.insertVariableIntoInput(e,b),this.closeVariablePicker()})})};i();const r=n.querySelector("#varPickerSearchInput");r&&(r.addEventListener("input",h=>i(h.target.value)),setTimeout(()=>r.focus(),50)),n.querySelectorAll(".variable-picker-cat-btn").forEach(h=>{h.addEventListener("click",()=>{n.querySelectorAll(".variable-picker-cat-btn").forEach(u=>u.classList.remove("is-active")),h.classList.add("is-active"),a=h.dataset.cat,i(r?r.value:"")})});const o=t.getBoundingClientRect();let c=o.left-260;c<10&&(c=o.left);let l=o.bottom+4;l+280>window.innerHeight&&(l=o.top-290),n.style.left=`${Math.max(10,Math.round(c))}px`,n.style.top=`${Math.max(10,Math.round(l))}px`;const d=h=>{!n.contains(h.target)&&h.target!==t&&!t.contains(h.target)&&(this.closeVariablePicker(),document.removeEventListener("mousedown",d))};setTimeout(()=>{document.addEventListener("mousedown",d)},10)}closeVariablePicker(){const t=document.getElementById("activeVariablePickerPopover");t&&t.remove()}insertVariableIntoInput(t,e){const s=document.getElementById(t);if(!s)return;const n=`{${e}}`,a=s.selectionStart,i=s.selectionEnd,r=s.value||"";a!==void 0&&i!==void 0?(s.value=r.substring(0,a)+n+r.substring(i),s.selectionStart=s.selectionEnd=a+n.length):s.value=r+n,s.focus(),s.dispatchEvent(new Event("input",{bubbles:!0}))}setupDebugConsole(){document.getElementById("canvasDebugConsole")&&this.renderDebugVariablesTable()}toggleDebugConsole(t=null){const e=document.getElementById("canvasDebugConsole"),s=document.getElementById("debugConsoleToggleIcon");if(!e)return;t===!0?e.classList.remove("is-collapsed"):t===!1?e.classList.add("is-collapsed"):e.classList.toggle("is-collapsed");const n=e.classList.contains("is-collapsed");s&&(s.tagName==="IMG"?s.src=n?"/static_base_icons?name=expand_less&size=16":"/static_base_icons?name=expand_more&size=16":s.className=n?"fas fa-chevron-up":"fas fa-chevron-down")}switchDebugTab(t){document.querySelectorAll(".canvas-debug-tab-btn").forEach(s=>{s.classList.toggle("is-active",s.dataset.tab===t)}),document.querySelectorAll(".canvas-debug-tab-pane").forEach(s=>{s.classList.remove("is-active")});const e=document.getElementById(`debugPane_${t}`);e&&e.classList.add("is-active"),this.toggleDebugConsole(!0)}async runGraphSimulation(){this.toggleDebugConsole(!0),this.switchDebugTab("stream");const t=document.getElementById("debugStreamOutput");t&&(t.innerHTML=`
        <div class="debug-stream-line is-info">[${new Date().toLocaleTimeString()}] D\xE9marrage de la simulation du graphe en m\xE9moire...</div>
        <div class="debug-stream-line is-info">N\u0153uds : ${this.nodes.length} | Liaisons : ${this.connections.length}</div>
      `);try{const e=await fetch("/api/melodi_automation/workflows/simulate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nodes:this.nodes,connections:this.connections,initial_payload:this.getEffectiveTestPayload(),custom_types:this.customTypes||[]})}),s=await e.json();if(!e.ok&&(!s||!s.status))throw new Error(s&&s.message||"\xC9chec de la simulation");if(this.simulationResult=s,t){const n=s.status==="success";let a=`<div class="debug-stream-line ${n?"is-info":"is-error"}">[${new Date().toLocaleTimeString()}] ${n?"Simulation termin\xE9e avec succ\xE8s":"Simulation arr\xEAt\xE9e sur \xE9chec"} (${s.duration_ms||0}ms)</div>`;Array.isArray(s.timeline)&&s.timeline.forEach((i,r)=>{const o=i.status==="success",c=o?"\u2713":"\u2717";a+=`
              <div class="debug-stream-line ${o?"is-success":"is-error"}">
                ${r+1}. [${i.duration_ms||0}ms] ${c} ${this.escapeHtml(i.node_name)} (${i.node_type})
                ${i.error?`<br>&nbsp;&nbsp;&nbsp;\u21B3 Erreur : ${this.escapeHtml(i.error)}`:""}
                ${i.active_ports?`<br>&nbsp;&nbsp;&nbsp;\u21B3 Ports activ\xE9s : [${i.active_ports.join(", ")}]`:""}
              </div>
            `}),s.error?a+=`<div class="debug-stream-line is-error">Arr\xEAt sur erreur : ${this.escapeHtml(s.error)}</div>`:a+='<div class="debug-stream-line is-success">Fin du parcours du graphe : flux compl\xE9t\xE9.</div>',t.innerHTML=a,t.scrollTop=t.scrollHeight}this.renderSimulationBadges(),this.renderDebugVariablesTable(),this.selectedNodeId&&this.inspectNodeInConsole(this.selectedNodeId)}catch(e){t&&(t.innerHTML+=`<div class="debug-stream-line is-error">[Erreur R\xE9seau / Moteur] ${this.escapeHtml(e.message)}</div>`)}}toggleDebugIoView(t){this.debugIoViewMode=t;const e=document.getElementById("btnDebugViewStructured"),s=document.getElementById("btnDebugViewJson"),n=document.getElementById("debugIoGridStructured"),a=document.getElementById("debugIoGridJson");e&&e.classList.toggle("active",t==="structured"),s&&s.classList.toggle("active",t==="json"),n&&n.classList.toggle("d-none",t!=="structured"),a&&a.classList.toggle("d-none",t!=="json")}switchDebugSubtab(t){this.currentDebugSubtab=t,document.querySelectorAll(".debug-subnav-btn").forEach(s=>{s.classList.toggle("is-active",s.dataset.subtab===t)}),document.querySelectorAll(".debug-subpane").forEach(s=>{s.classList.remove("is-active")});const e=document.getElementById(`debugSubpane_${t}`);e&&e.classList.add("is-active")}setDebugVariableCategory(t){this.debugVarCategory=t,document.querySelectorAll("#debugVarCategoryPills .debug-category-pill").forEach(s=>{s.classList.toggle("is-active",s.dataset.cat===t)});const e=document.getElementById("debugVarFilterInput");this.renderDebugVariablesTable(e?e.value:"")}renderVariablesCardList(t,e,s="Aucune variable disponible."){if(t){if(!Array.isArray(e)||e.length===0){t.innerHTML=`<div class="text-center text-muted x-small py-3">${this.escapeHtml(s)}</div>`;return}t.innerHTML=e.map(n=>{const a=`type-${(n.type||"other").toLowerCase()}`;return`
      <div class="debug-var-card">
        <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 60%;">
          <span class="debug-var-path">{${this.escapeHtml(n.path)}}</span>
          <span class="n8n-type-badge ${a} ms-1">${this.escapeHtml(n.type||"var")}</span>
          ${n.source?`<small class="text-muted ms-1" style="font-size: 10px;">(${this.escapeHtml(n.source)})</small>`:""}
        </div>
        <div class="d-flex align-items-center gap-2">
          <span class="debug-var-val" title="${this.escapeHtml(String(n.preview??""))}">${this.escapeHtml(String(n.preview??""))}</span>
          <button type="button" class="debug-copy-btn" onclick="navigator.clipboard.writeText('{${this.escapeHtml(n.path)}}'); alert('Copi\xE9 : {${this.escapeHtml(n.path)}}');" title="Copier la r\xE9f\xE9rence">
            <img src="/static_base_icons?name=content_copy&size=11" style="vertical-align:-1px">
          </button>
        </div>
      </div>
    `}).join("")}}inspectNodeInConsole(t){const e=document.getElementById("debugIoInputPre"),s=document.getElementById("debugIoOutputPre"),n=document.getElementById("debugIoInputVarsTree"),a=document.getElementById("debugIoOutputVarsTree"),i=document.getElementById("debugIoSelectedNodeName"),r=document.getElementById("debugIoStatusBadge"),o=document.getElementById("debugPayloadVarsTree"),c=document.getElementById("debugPayloadRawPre"),l=document.getElementById("debugStepsAccordion"),d=document.getElementById("debugStepsCountBadge"),h=document.getElementById("debugContextVarsTree"),u=document.getElementById("debugContextRawPre"),f=this.nodes.find(y=>y.id===t);if(!f){i&&(i.innerText="Aucun n\u0153ud s\xE9lectionn\xE9"),r&&(r.innerHTML=""),e&&(e.innerText="S\xE9lectionnez un n\u0153ud sur le canvas pour visualiser ses entr\xE9es."),s&&(s.innerText="S\xE9lectionnez un n\u0153ud sur le canvas pour visualiser ses sorties."),n&&(n.innerHTML='<div class="text-center text-muted x-small py-3">S\xE9lectionnez un n\u0153ud.</div>'),a&&(a.innerHTML='<div class="text-center text-muted x-small py-3">S\xE9lectionnez un n\u0153ud.</div>');return}i&&(i.innerText=`${f.name||f.type} (${f.id})`);const p=this.simulationResult&&this.simulationResult.nodes_trace?this.simulationResult.nodes_trace[t]:null;if(r&&(p?p.status==="success"?p.active_ports&&p.active_ports.includes("error")?r.innerHTML=`<span class="badge bg-danger-subtle text-danger border"><img src="/static_base_icons?name=warning&size=11" class="me-1" style="vertical-align:-1px">D\xE9rout\xE9 vers Port Erreur (${p.duration_ms}ms)</span>`:r.innerHTML=`<span class="badge bg-success-subtle text-success border"><img src="/static_base_icons?name=check&size=11" class="me-1" style="vertical-align:-1px">Succ\xE8s (${p.duration_ms}ms)</span>`:p.status==="error"?r.innerHTML=`<span class="badge bg-danger-subtle text-danger border"><img src="/static_base_icons?name=close&size=11" class="me-1" style="vertical-align:-1px">Erreur (${p.duration_ms}ms)</span>`:r.innerHTML='<span class="badge bg-secondary-subtle text-secondary border">- Non ex\xE9cut\xE9</span>':r.innerHTML='<span class="badge bg-warning-subtle text-warning border">Non simul\xE9</span>'),p)e&&(e.innerText=JSON.stringify(p.input_data||{},null,2)),s&&(s.innerText=p.error?`Erreur lors de l'ex\xE9cution :
${p.error}`:JSON.stringify(p.output_data!==void 0?p.output_data:{},null,2)),this.renderVariablesCardList(n,p.input_variables,"Aucune variable d'entr\xE9e pour ce n\u0153ud."),this.renderVariablesCardList(a,p.output_variables,"Aucune variable produite en sortie.");else{const y=JSON.stringify(f.configuration||{},null,2);e&&(e.innerText=`Configuration actuelle du n\u0153ud :
${y}

(Lancez une simulation pour voir les donn\xE9es r\xE9elles re\xE7ues en entr\xE9e).`),s&&(s.innerText=`En attente de simulation.
Cliquez sur "Simuler le Graphe" dans la console pour ex\xE9cuter ce n\u0153ud et inspecter ses sorties.`),n&&(n.innerHTML='<div class="text-center text-muted x-small py-3">Lancez une simulation pour voir les entr\xE9es re\xE7ues.</div>'),a&&(a.innerHTML='<div class="text-center text-muted x-small py-3">Lancez une simulation pour voir les sorties produites.</div>')}const m=p&&p.payload||this.getEffectiveTestPayload();if(c&&(c.innerText=JSON.stringify(m,null,2)),o){const y=[],g=(x,T)=>{typeof x=="object"&&x!==null&&(Array.isArray(x)?y.push({path:`payload.${T}`,name:T,type:"array",preview:`[${x.length} \xE9l\xE9ments]`,source:"Payload D\xE9clencheur"}):Object.entries(x).forEach(([S,w])=>{const _=T?`${T}.${S}`:S;typeof w=="object"&&w!==null&&!Array.isArray(w)?g(w,_):y.push({path:`payload.${_}`,name:S,type:Array.isArray(w)?"array":typeof w,preview:Array.isArray(w)?`[${w.length} \xE9l\xE9ments]`:String(w),source:"Payload D\xE9clencheur"})}))};g(m,""),this.renderVariablesCardList(o,y,"Aucun payload d\xE9clencheur disponible.")}const b=p&&p.preceding_steps||{},v=Object.keys(b);d&&(d.innerText=String(v.length)),l&&(v.length===0?l.innerHTML='<div class="text-center text-muted x-small py-3">Aucune \xE9tape pr\xE9c\xE9dente enregistr\xE9e avant ce n\u0153ud.</div>':l.innerHTML=v.map(y=>{const g=b[y],x=g.output,T=JSON.stringify(x,null,2),S=[],w=(_,$)=>{typeof _=="object"&&_!==null&&(Array.isArray(_)||Object.entries(_).forEach(([E,C])=>{const N=$?`${$}.${E}`:E;typeof C=="object"&&C!==null&&!Array.isArray(C)?w(C,N):S.push({path:`steps.${y}.${N}`,name:E,type:Array.isArray(C)?"array":typeof C,preview:Array.isArray(C)?`[${C.length} \xE9l\xE9ments]`:String(C),source:g.name})}))};return w(x,""),`
            <div class="debug-step-item">
              <div class="debug-step-header" onclick="this.nextElementSibling.classList.toggle('d-none')">
                <div class="d-flex align-items-center gap-2">
                  <img src="/static_base_icons?name=layers&size=13" style="vertical-align:-2px">
                  <span class="fw-bold">${this.escapeHtml(g.name)}</span>
                  <code class="text-muted" style="font-size:10px;">(steps.${this.escapeHtml(y)})</code>
                  <span class="badge bg-light text-dark border" style="font-size:9px;">${this.escapeHtml(g.type)}</span>
                </div>
                <div class="d-flex align-items-center gap-2">
                  <small class="text-muted" style="font-size:10px;">${S.length} variable(s)</small>
                  <img src="/static_base_icons?name=expand_more&size=12" style="vertical-align:-2px">
                </div>
              </div>
              <div class="debug-step-body d-none">
                <div class="d-flex align-items-center justify-content-between mb-2">
                  <span class="x-small text-muted fw-bold">Variables produites par cette \xE9tape :</span>
                  <button type="button" class="btn btn-link p-0 text-decoration-none x-small" onclick="navigator.clipboard.writeText('${this.escapeHtml(T).replace(/'/g,"\\'")}'); alert('Sortie copi\xE9e');">Copier JSON</button>
                </div>
                <div class="debug-var-tree mb-2">
                  ${S.length>0?S.map(_=>{const $=`type-${(_.type||"other").toLowerCase()}`;return`
                    <div class="debug-var-card">
                      <div>
                        <span class="debug-var-path">{${this.escapeHtml(_.path)}}</span>
                        <span class="n8n-type-badge ${$} ms-1">${this.escapeHtml(_.type)}</span>
                      </div>
                      <div class="d-flex align-items-center gap-2">
                        <span class="debug-var-val" title="${this.escapeHtml(String(_.preview))}">${this.escapeHtml(String(_.preview))}</span>
                        <button type="button" class="debug-copy-btn" onclick="navigator.clipboard.writeText('{${this.escapeHtml(_.path)}}'); alert('Copi\xE9 : {${this.escapeHtml(_.path)}}');" title="Copier">
                          <img src="/static_base_icons?name=content_copy&size=11" style="vertical-align:-1px">
                        </button>
                      </div>
                    </div>
                  `}).join(""):'<div class="text-muted x-small py-1">Sortie non structur\xE9e ou vide.</div>'}
                </div>
                <pre class="debug-io-pre mt-1" style="max-height: 80px;">${this.escapeHtml(T)}</pre>
              </div>
            </div>
          `}).join(""));const I=p&&p.context_snapshot||{};if(u&&(u.innerText=JSON.stringify(I,null,2)),h){const y=[{path:"context.timestamp",name:"timestamp",type:"number",preview:String(Date.now()),source:"Syst\xE8me"},{path:"context.execution_id",name:"execution_id",type:"string",preview:"sim_dry_run",source:"Syst\xE8me"}];I.variables&&typeof I.variables=="object"&&Object.entries(I.variables).forEach(([g,x])=>{y.push({path:`context.variables.${g}`,name:g,type:typeof x,preview:String(x),source:"Variables Contexte"})}),this.renderVariablesCardList(h,y,"Aucune variable de contexte disponible.")}}renderSimulationBadges(){!this.simulationResult||!this.simulationResult.nodes_trace||this.nodes.forEach(t=>{const e=document.getElementById(`nodeEl_${t.id}`);if(!e)return;let s=e.querySelector(".node-sim-badge");const n=this.simulationResult.nodes_trace[t.id];n?(s||(s=document.createElement("div"),e.appendChild(s)),n.status==="success"?n.active_ports&&n.active_ports.includes("error")?(s.className="node-sim-badge is-error",s.title=`D\xE9rout\xE9 vers Port Erreur (${n.duration_ms}ms)`,s.innerHTML='<img src="/static_base_icons?name=warning&fill=white&size=10">'):(s.className="node-sim-badge is-success",s.title=`Ex\xE9cut\xE9 avec succ\xE8s (${n.duration_ms}ms)`,s.innerHTML='<img src="/static_base_icons?name=check&fill=white&size=10">'):n.status==="error"?(s.className="node-sim-badge is-error",s.title=`Erreur : ${n.error||"\xC9chec"}`,s.innerHTML='<img src="/static_base_icons?name=close&fill=white&size=10">'):(s.className="node-sim-badge is-skipped",s.title="Branche ignor\xE9e",s.innerHTML='<span style="font-weight:bold;line-height:1;">-</span>')):s&&(s.className="node-sim-badge is-skipped",s.title="Non atteint lors de la simulation",s.innerHTML='<span style="font-weight:bold;line-height:1;">-</span>')})}getAvailableVariables(){const t=[],e=new Set;if(this.selectedNodeId&&this.simulationResult&&this.simulationResult.nodes_trace){const a=this.simulationResult.nodes_trace[this.selectedNodeId];a&&(Array.isArray(a.input_variables)&&a.input_variables.forEach(i=>{e.has(i.path)||(e.add(i.path),t.push({...i,category:"node_io"}))}),Array.isArray(a.output_variables)&&a.output_variables.forEach(i=>{e.has(i.path)||(e.add(i.path),t.push({...i,category:"steps"}))}))}if(this.simulationResult&&Array.isArray(this.simulationResult.available_variables)&&this.simulationResult.available_variables.length>0)return this.simulationResult.available_variables.forEach(a=>{e.has(a.path)||(e.add(a.path),t.push(a))}),t;const s=(a,i,r,o="payload")=>{typeof a=="object"&&a!==null&&(Array.isArray(a)?(e.has(i)||(e.add(i),t.push({path:i,name:i.split(".").pop(),type:"array",preview:`[${a.length} \xE9l\xE9ments]`,source:r,category:o})),a.length>0&&typeof a[0]=="object"&&s(a[0],`${i}[0]`,r,o)):Object.entries(a).forEach(([c,l])=>{const d=i?`${i}.${c}`:c;typeof l=="object"&&l!==null?s(l,d,r,o):e.has(d)||(e.add(d),t.push({path:d,name:c,type:typeof l,preview:String(l),source:r,category:o}))}))},n=this.getEffectiveTestPayload();return n&&Object.keys(n).length>0&&(s(n,"payload","D\xE9clencheur","payload"),s(n,"","D\xE9clencheur","payload")),this.nodes.forEach(a=>{const i=`steps.${a.id}`;if(e.has(i)||(e.add(i),t.push({path:i,name:a.name||a.id,type:"object",preview:`{Donn\xE9es ${a.name||a.type}}`,source:a.name||a.id,category:"steps",node_id:a.id,node_name:a.name})),a.type==="core.set_fields"&&Array.isArray(a.configuration?.fields))a.configuration.fields.forEach(r=>{if(r.key){const o=r.key,c=`steps.${a.id}.${r.key}`;e.has(o)||(e.add(o),t.push({path:o,name:r.key,type:r.type||"string",preview:r.value||"",source:a.name||"Set Fields",category:"steps",node_id:a.id,node_name:a.name})),e.has(c)||(e.add(c),t.push({path:c,name:r.key,type:r.type||"string",preview:r.value||"",source:a.name||"Set Fields",category:"steps",node_id:a.id,node_name:a.name}))}});else if(a.type==="core.ai_chat"){const r=`steps.${a.id}.content`;e.has(r)||(e.add(r),t.push({path:r,name:"content",type:"string",preview:"R\xE9ponse texte g\xE9n\xE9r\xE9e par l'IA",source:a.name||"Chat IA",category:"steps",node_id:a.id,node_name:a.name}));const o=`steps.${a.id}.json`;e.has(o)||(e.add(o),t.push({path:o,name:"json",type:"object",preview:"{Objet JSON structur\xE9}",source:a.name||"Chat IA",category:"steps",node_id:a.id,node_name:a.name}))}else if(a.type==="core.ai_agent"){const r=`steps.${a.id}.content`;e.has(r)||(e.add(r),t.push({path:r,name:"content",type:"string",preview:"R\xE9ponse finale de l'agent autonome",source:a.name||"Agent IA",category:"steps",node_id:a.id,node_name:a.name}));const o=`steps.${a.id}.steps`;e.has(o)||(e.add(o),t.push({path:o,name:"steps",type:"array",preview:"[Historique des outils ex\xE9cut\xE9s]",source:a.name||"Agent IA",category:"steps",node_id:a.id,node_name:a.name}));const c=`steps.${a.id}.tool_calls_count`;e.has(c)||(e.add(c),t.push({path:c,name:"tool_calls_count",type:"number",preview:"1",source:a.name||"Agent IA",category:"steps",node_id:a.id,node_name:a.name}))}}),t.push({path:"context.timestamp",name:"timestamp",type:"number",preview:String(Date.now()),source:"Contexte Global",category:"context"}),t}renderDebugVariablesTable(t=""){const e=document.getElementById("debugVariablesTableBody");if(!e)return;const s=this.getAvailableVariables(),n=t.toLowerCase().trim(),a=this.debugVarCategory||"all",i=s.filter(o=>{const c=!n||o.path.toLowerCase().includes(n)||o.name&&o.name.toLowerCase().includes(n)||o.source&&o.source.toLowerCase().includes(n)||o.node_name&&o.node_name.toLowerCase().includes(n),l=a==="all"||o.category===a;return c&&l});if(i.length===0){e.innerHTML='<tr><td colspan="5" class="text-center text-muted py-3">Aucune variable trouv\xE9e.</td></tr>';return}const r=o=>o==="node_io"?'<span class="badge bg-success-subtle text-success border me-1" style="font-size:9px;">N\u0153ud E/S</span>':o==="payload"?'<span class="badge bg-warning-subtle text-warning border me-1" style="font-size:9px;">Payload</span>':o==="steps"?'<span class="badge bg-primary-subtle text-primary border me-1" style="font-size:9px;">Step</span>':o==="context"?'<span class="badge bg-info-subtle text-info border me-1" style="font-size:9px;">Contexte</span>':'<span class="badge bg-secondary-subtle text-secondary border me-1" style="font-size:9px;">Autre</span>';e.innerHTML=i.map(o=>{const c=o.node_name?`${o.node_name} (${o.source||""})`:o.source||"";return`
        <tr>
          <td>
            <div class="d-flex align-items-center">
              ${r(o.category)}
              <code class="fw-bold">{${this.escapeHtml(o.path)}}</code>
            </div>
          </td>
          <td><span class="badge bg-light text-dark border">${this.escapeHtml(o.type||"any")}</span></td>
          <td class="text-muted"><small>${this.escapeHtml(c)}</small></td>
          <td><span class="text-truncate d-inline-block font-monospace" style="max-width: 250px;">${this.escapeHtml(String(o.preview??""))}</span></td>
          <td class="text-end">
            <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2" style="font-size: 10px;" onclick="navigator.clipboard.writeText('{${this.escapeHtml(o.path)}}'); alert('Copi\xE9 : {${this.escapeHtml(o.path)}}');" title="Copier la variable">
              Copier
            </button>
          </td>
        </tr>
      `}).join("")}filterDebugVariables(t){this.renderDebugVariablesTable(t)}saveSimulationPayloadFromModal(){const t=document.getElementById("simulationModalPayloadTextarea");if(t)try{const e=JSON.parse(t.value||"{}");this.simulationInitialPayload=e;const s=this.nodes.find(a=>a.type&&(a.type.includes("trigger")||a.type.startsWith("core.trigger")));s&&(s.configuration||(s.configuration={}),s.configuration.test_payload=e,this.updateSerializedInputs(),this.selectedNodeId===s.id&&this.renderInspector()),this.runGraphSimulation();const n=document.getElementById("simulationPayloadModal");if(n){const a=window.melodi?.Modal||window.MelodiUI?.Modal;a?a.getOrCreateInstance(n).hide():(n.classList.remove("show"),n.style.display="none")}}catch(e){alert("Erreur de format JSON dans le payload : "+e.message)}}fillSimulationModalFromTriggerSchema(){const e=this.nodes.find(a=>a.type&&(a.type.includes("trigger")||a.type.startsWith("core.trigger")))?.configuration?.payload_schema||[],s=this.generateTestPayloadFromSchema(e),n=document.getElementById("simulationModalPayloadTextarea");n&&(n.value=JSON.stringify(s,null,2))}prepareSimulationModal(){const t=document.getElementById("simulationModalPayloadTextarea");if(!t)return;const e=this.getEffectiveTestPayload();t.value=JSON.stringify(e,null,2)}openCustomTypesModal(t=null){Array.isArray(this.customTypes)||(this.customTypes=[]),t?this.selectedCustomTypeId=t:this.customTypes.length>0&&!this.selectedCustomTypeId&&(this.selectedCustomTypeId=this.customTypes[0].id),this.renderCustomTypesModal();const e=document.getElementById("customTypesModal");if(e){e._hasSaveOnCloseBound||(e.addEventListener("hidden.bs.modal",()=>{this.saveCustomTypesFromModal()}),e._hasSaveOnCloseBound=!0);const s=window.melodi?.Modal||window.MelodiUI?.Modal;s?s.getOrCreateInstance(e).show():(e.classList.add("show"),e.style.display="block")}}renderCustomTypesModal(){const t=document.getElementById("customTypesListContainer"),e=document.getElementById("customTypeEditorContainer");if(!t||!e)return;this.customTypes.length===0?t.innerHTML=`
        <div class="p-3 text-center text-muted x-small">
          Aucun type personnalis\xE9.<br>Cliquez sur "+ Nouveau" pour d\xE9marrer.
        </div>
      `:t.innerHTML=this.customTypes.map(i=>{const r=i.id===this.selectedCustomTypeId,o=Array.isArray(i.fields)?i.fields.length:0;return`
          <button type="button" class="list-group-item list-group-item-action py-2 px-3 d-flex align-items-center justify-content-between ${r?"active":""}" onclick="canvas.selectCustomType('${this.escapeHtml(i.id)}')">
            <div class="overflow-hidden me-2">
              <div class="fw-bold x-small text-truncate">\u{1F4E6} ${this.escapeHtml(i.name||"Sans nom")}</div>
              <small class="${r?"text-white-50":"text-muted"}" style="font-size: 10px;">${this.escapeHtml(i.label||i.name||"")} &bull; ${o} champ(s)</small>
            </div>
            <span class="badge ${r?"bg-light text-dark":"bg-secondary-subtle text-secondary"}" style="font-size: 9px;">Struct</span>
          </button>
        `}).join("");const s=this.customTypes.find(i=>i.id===this.selectedCustomTypeId);if(!s){e.innerHTML=`
        <div class="text-center text-muted py-5">
          <img src="/static_base_icons?name=category&size=36" class="mb-2 opacity-50">
          <p class="small mb-0">S\xE9lectionnez un type dans la liste de gauche ou cliquez sur <strong>+ Nouveau</strong>.</p>
        </div>
      `;return}const n=Array.isArray(s.fields)?s.fields:[],a=this.customTypes.filter(i=>i.id!==s.id);e.innerHTML=`
      <div class="custom-type-editor">
        <div class="d-flex align-items-center justify-content-between mb-3 pb-2 border-bottom">
          <h6 class="fw-bold text-dark mb-0 d-flex align-items-center gap-1">
            <img src="/static_base_icons?name=view_in_ar&size=16" style="vertical-align:-2px"> Structure : <code>${this.escapeHtml(s.name)}</code>
          </h6>
          <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2 d-flex align-items-center gap-1" style="font-size: 11px;" onclick="canvas.deleteCustomType('${this.escapeHtml(s.id)}')">
            <img src="/static_base_icons?name=delete&fill=%23dc3545&size=12" style="vertical-align:-2px"> Supprimer ce type
          </button>
        </div>

        <div class="row g-2 mb-3">
          <div class="col-md-6">
            <label class="form-label x-small fw-semibold text-muted mb-1">Nom technique du type (ex: Address, Customer) *</label>
            <input type="text" class="form-control form-control-sm font-monospace" placeholder="NomSansEspace" value="${this.escapeHtml(s.name||"")}" oninput="canvas.updateCustomTypeProp('${s.id}', 'name', this.value)">
          </div>
          <div class="col-md-6">
            <label class="form-label x-small fw-semibold text-muted mb-1">Libell\xE9 d'affichage (ex: Adresse Postale)</label>
            <input type="text" class="form-control form-control-sm" placeholder="Nom lisible..." value="${this.escapeHtml(s.label||"")}" oninput="canvas.updateCustomTypeProp('${s.id}', 'label', this.value)">
          </div>
          <div class="col-12">
            <label class="form-label x-small fw-semibold text-muted mb-1">Description (optionnelle)</label>
            <input type="text" class="form-control form-control-sm" placeholder="Description de la structure de donn\xE9es..." value="${this.escapeHtml(s.description||"")}" oninput="canvas.updateCustomTypeProp('${s.id}', 'description', this.value)">
          </div>
        </div>

        <div class="mb-2 d-flex align-items-center justify-content-between">
          <label class="form-label x-small fw-bold text-uppercase text-muted mb-0">Champs internes de la structure (${n.length})</label>
          <button type="button" class="btn btn-outline-primary btn-sm py-0 px-2 d-flex align-items-center gap-1" style="font-size: 11px;" onclick="canvas.addCustomTypeField('${s.id}')">
            <img src="/static_base_icons?name=add&size=12" style="vertical-align:-2px"> Ajouter un champ
          </button>
        </div>

        <div class="custom-type-fields-table border rounded p-2 bg-light mb-3" style="max-height: 250px; overflow-y: auto;">
          ${n.length===0?`
            <div class="text-center text-muted x-small py-3">Aucun champ d\xE9fini dans cette structure. Cliquez sur "+ Ajouter un champ".</div>
          `:`
            <div class="d-flex gap-1 mb-1 px-1 text-muted x-small fw-semibold" style="font-size: 10px;">
              <div style="flex: 1.2;">Nom du champ (cl\xE9)</div>
              <div style="width: 125px;">Type de donn\xE9es</div>
              <div style="flex: 1.0;">Valeur par d\xE9faut</div>
              <div style="width: 45px;" class="text-center">Requis</div>
              <div style="width: 26px;"></div>
            </div>
            ${n.map((i,r)=>{const o=String(i.type||"string"),c=String(i.custom_type||i.custom_type_ref||(o.startsWith("custom:")?o.split(":")[1]:"")),l=o==="custom"||o.startsWith("custom:")||a.some(h=>h.name===o),d=l&&c||o;return`
                <div class="d-flex align-items-center gap-1 mb-1 p-1 bg-white rounded border">
                  <input type="text" class="form-control form-control-sm font-monospace" style="flex: 1.2; font-size: 11px;" placeholder="cl\xE9" value="${this.escapeHtml(i.key||"")}" oninput="canvas.updateCustomTypeFieldProp('${s.id}', ${r}, 'key', this.value)">
                  <select class="form-select form-select-sm" style="width: 125px; font-size: 11px;" onchange="canvas.updateCustomTypeFieldType('${s.id}', ${r}, this.value)">
                    <optgroup label="Primitifs">
                      <option value="string" ${o==="string"?"selected":""}>Texte (str)</option>
                      <option value="number" ${o==="number"?"selected":""}>Nombre (float)</option>
                      <option value="integer" ${o==="integer"||o==="int"?"selected":""}>Entier (int)</option>
                      <option value="boolean" ${o==="boolean"||o==="bool"?"selected":""}>Bool\xE9en</option>
                      <option value="array" ${o==="array"?"selected":""}>Tableau []</option>
                      <option value="object" ${o==="object"?"selected":""}>Objet {}</option>
                      <option value="any" ${o==="any"?"selected":""}>Tous (any)</option>
                    </optgroup>
                    <optgroup label="Formats">
                      <option value="email" ${o==="email"?"selected":""}>Email</option>
                      <option value="date" ${o==="date"||o==="datetime"?"selected":""}>Date</option>
                      <option value="uuid" ${o==="uuid"?"selected":""}>UUID</option>
                    </optgroup>
                    ${a.length>0?`
                    <optgroup label="Types Imbriqu\xE9s">
                      ${a.map(h=>{const u=l&&d===h.name||o===h.name;return`<option value="custom:${this.escapeHtml(h.name)}" ${u?"selected":""}>\u{1F4E6} ${this.escapeHtml(h.name)}</option>`}).join("")}
                    </optgroup>
                    `:""}
                  </select>
                  <input type="text" class="form-control form-control-sm font-monospace" style="flex: 1.0; font-size: 11px;" placeholder="d\xE9faut..." value="${this.escapeHtml(i.default!==void 0&&i.default!==null?String(i.default):"")}" oninput="canvas.updateCustomTypeFieldProp('${s.id}', ${r}, 'default', this.value)">
                  <div style="width: 45px;" class="text-center form-check form-switch m-0 d-flex justify-content-center">
                    <input class="form-check-input" type="checkbox" ${i.required?"checked":""} onchange="canvas.updateCustomTypeFieldProp('${s.id}', ${r}, 'required', this.checked)">
                  </div>
                  <button type="button" class="btn btn-outline-danger btn-sm p-1" style="width: 26px; height: 28px;" onclick="canvas.removeCustomTypeField('${s.id}', ${r})">
                    <img src="/static_base_icons?name=close&fill=%23dc3545&size=12" style="vertical-align:-2px">
                  </button>
                </div>
              `}).join("")}
          `}
        </div>
      </div>
    `}createNewCustomType(){const t="type_"+Math.random().toString(36).substr(2,8),e=(this.customTypes||[]).length+1,s={id:t,name:`CustomType${e}`,label:`Type Personnalis\xE9 ${e}`,description:"",fields:[{key:"id",type:"string",required:!0,default:""},{key:"name",type:"string",required:!0,default:""}]};Array.isArray(this.customTypes)||(this.customTypes=[]),this.customTypes.push(s),this.selectedCustomTypeId=t,this.updateSerializedInputs(),this.renderCustomTypesModal()}selectCustomType(t){this.selectedCustomTypeId=t,this.renderCustomTypesModal()}deleteCustomType(t){confirm("Voulez-vous vraiment supprimer ce type personnalis\xE9 ?")&&(this.customTypes=this.customTypes.filter(e=>e.id!==t),this.selectedCustomTypeId=this.customTypes.length>0?this.customTypes[0].id:null,this.updateSerializedInputs(),this.renderCustomTypesModal(),this.selectedNodeId&&this.renderInspector())}updateCustomTypeProp(t,e,s){const n=this.customTypes.find(i=>i.id===t);if(!n)return;n[e]=s,this.updateSerializedInputs();const a=document.querySelector("#customTypesListContainer button.active");if(a&&e==="name"){const i=a.querySelector(".fw-bold");i&&(i.innerText=`\u{1F4E6} ${s||"Sans nom"}`)}}addCustomTypeField(t){const e=this.customTypes.find(s=>s.id===t);e&&(Array.isArray(e.fields)||(e.fields=[]),e.fields.push({key:"",type:"string",required:!0,default:""}),this.updateSerializedInputs(),this.renderCustomTypesModal())}updateCustomTypeFieldProp(t,e,s,n){const a=this.customTypes.find(i=>i.id===t);!a||!Array.isArray(a.fields)||!a.fields[e]||(a.fields[e][s]=n,this.updateSerializedInputs())}updateCustomTypeFieldType(t,e,s){const n=this.customTypes.find(i=>i.id===t);if(!n||!Array.isArray(n.fields)||!n.fields[e])return;const a=n.fields[e];if(s.startsWith("custom:")){const i=s.split(":",2)[1];a.type="custom",a.custom_type=i,a.custom_type_ref=i}else a.type=s,delete a.custom_type,delete a.custom_type_ref;this.updateSerializedInputs(),this.renderCustomTypesModal()}removeCustomTypeField(t,e){const s=this.customTypes.find(n=>n.id===t);!s||!Array.isArray(s.fields)||(s.fields.splice(e,1),this.updateSerializedInputs(),this.renderCustomTypesModal())}saveCustomTypesFromModal(){this.updateSerializedInputs(),this.selectedNodeId&&this.renderInspector()}}
//# sourceMappingURL=workflow_canvas.js.map
