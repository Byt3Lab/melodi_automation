/**
 * MELODI Automation Engine - n8n-Style Interactive Workflow Graph Canvas
 * Moteur de rendu et d'édition de graphe de nœuds (DAG multi-ports, bezier curves, inspecteur).
 */

class WorkflowCanvas {
  constructor(options = {}) {
    this.wrapper = document.getElementById(options.wrapperId || 'workflowCanvasWrapper');
    this.viewport = document.getElementById(options.viewportId || 'workflowCanvasViewport');
    this.svg = document.getElementById(options.svgId || 'workflowConnectionsSvg');
    this.tempWire = document.getElementById(options.tempWireId || 'connectionTempWire');

    this.availableNodes = options.availableNodes || [];
    this.nodesMap = new Map();
    this.availableNodes.forEach(n => this.nodesMap.set(n.id, n));

    // Données du workflow
    this.workflow = options.workflow || {};
    this.nodes = Array.isArray(this.workflow.nodes) ? JSON.parse(JSON.stringify(this.workflow.nodes)) : [];
    this.connections = Array.isArray(this.workflow.connections) ? JSON.parse(JSON.stringify(this.workflow.connections)) : [];
    this.customTypes = Array.isArray(this.workflow.custom_types) ? JSON.parse(JSON.stringify(this.workflow.custom_types)) : [];
    this.selectedCustomTypeId = null;

    // État actif
    this.selectedNodeId = null;
    this.connectingFrom = null; // { nodeId, portId, isOutput, x, y }
    this.draggedNode = null; // { nodeId, startX, startY, origX, origY }
    this.isPanning = false;
    this.panStart = { x: 0, y: 0 };
    this.panOffset = { x: 60, y: 60 };
    this.zoom = 1.0;

    // État de l'Interpréteur temps réel & Simulation
    this.simulationResult = null;
    this.simulationInitialPayload = null;
    this._customFieldModes = {};
    this.debugIoViewMode = 'structured';
    this.currentDebugSubtab = 'node_io';
    this.debugVarCategory = 'all';

    // Initialisation
    this.init();
  }

  init() {
    this.normalizeWorkflowData();
    this.renderNodes();
    this.renderConnections();
    this.setupCanvasInteractions();
    this.updateSerializedInputs();
    this.applyTransform();
    this.setupDebugConsole();
  }

  // -------------------------------------------------------------
  // 1. Normalisation des données du workflow
  // -------------------------------------------------------------
  normalizeWorkflowData() {
    // Si aucun nœud n'existe (nouveau workflow), initialiser avec un trigger par défaut
    if (this.nodes.length === 0) {
      this.nodes.push({
        id: 'node_trigger_1',
        type: this.workflow.trigger_type === 'webhook' ? 'core.trigger_webhook' : 'core.trigger_event',
        name: this.workflow.trigger_type === 'webhook' ? 'Déclencheur Webhook' : 'Déclencheur Événement',
        x: 100,
        y: 200,
        configuration: {
          trigger_module: this.workflow.trigger_module || 'commerce',
          trigger_event: this.workflow.trigger_event || 'order.created',
          webhook_token: this.workflow.webhook_token || '',
        },
      });
      return;
    }

    // Auto-positionnement si x/y absents (anciens workflows 1.0)
    let currentX = 100;
    this.nodes.forEach((n, idx) => {
      if (typeof n.x !== 'number') n.x = currentX;
      if (typeof n.y !== 'number') n.y = 200 + (idx % 2 === 0 ? 0 : 40);
      currentX += 300;

    });

    // Normalisation des connexions
    this.connections.forEach(c => {
      if (!c.source_output) c.source_output = 'main';
      if (!c.target_input) c.target_input = 'main';
    });
  }

  // -------------------------------------------------------------
  // 2. Rendu des Nœuds sur le Canvas
  // -------------------------------------------------------------
  renderNodes() {
    // Nettoyer les éléments nœuds existants
    const existing = this.viewport.querySelectorAll('.graph-node');
    existing.forEach(el => el.remove());

    this.nodes.forEach(nodeData => {
      const el = this.createNodeElement(nodeData);
      this.viewport.appendChild(el);
    });
  }

  createNodeElement(nodeData) {
    const def = this.nodesMap.get(nodeData.type) || {
      name: nodeData.name || nodeData.type,
      category: 'generic',
      icon: 'fas fa-cube',
      color: '#4f46e5',
      inputs: [{ id: 'main', label: 'Entrée' }],
      outputs: [{ id: 'main', label: 'Sortie' }],
    };

    const el = document.createElement('div');
    el.className = 'graph-node';
    el.id = `nodeEl_${nodeData.id}`;
    el.style.left = `${nodeData.x}px`;
    el.style.top = `${nodeData.y}px`;

    if (this.selectedNodeId === nodeData.id) {
      el.classList.add('is-selected');
    }

    // Bande de couleur de catégorie
    const color = def.color || '#4f46e5';
    const iconHtml = this.renderNodeIcon(def.icon, 16);

    // Rendu HTML du nœud
    el.innerHTML = `
      <div class="graph-node-strip" style="background-color: ${color};"></div>
      <div class="graph-node-header">
        <div class="graph-node-icon" style="background-color: ${color};">
          ${iconHtml}
        </div>
        <div class="graph-node-title-wrap">
          <h6 class="graph-node-title" title="${this.escapeHtml(nodeData.name || def.name)}">${this.escapeHtml(nodeData.name || def.name)}</h6>
          <span class="graph-node-subtitle">${this.escapeHtml(def.name)}</span>
        </div>
      </div>
      <div class="node-ports-container">
        <div class="node-inputs"></div>
        <div class="node-outputs"></div>
      </div>
    `;

    // Ajout des ports d'entrée
    const inputsContainer = el.querySelector('.node-inputs');
    const inputs = def.inputs || [];
    inputs.forEach(port => {
      const portEl = document.createElement('div');
      portEl.className = 'node-port node-input-port';
      portEl.dataset.nodeId = nodeData.id;
      portEl.dataset.portId = port.id;
      portEl.dataset.direction = 'input';
      portEl.innerHTML = `<span class="node-port-label">${this.escapeHtml(port.label)}</span>`;
      inputsContainer.appendChild(portEl);
    });

    // Ajout des ports de sortie
    const outputsContainer = el.querySelector('.node-outputs');
    const outputs = def.outputs || [];
    outputs.forEach(port => {
      const portEl = document.createElement('div');
      portEl.className = 'node-port node-output-port';
      portEl.dataset.nodeId = nodeData.id;
      portEl.dataset.portId = port.id;
      portEl.dataset.direction = 'output';
      if (port.color) portEl.style.borderColor = port.color;
      portEl.innerHTML = `<span class="node-port-label" style="color: ${port.color || ''}">${this.escapeHtml(port.label)}</span>`;
      outputsContainer.appendChild(portEl);
    });

    // Événements du nœud (clic, sélection, déplacement)
    el.addEventListener('mousedown', (e) => {
      // Ignorer si le clic provient d'un port
      if (e.target.closest('.node-port')) return;
      e.stopPropagation();
      this.selectNode(nodeData.id);
      this.startDraggingNode(nodeData.id, e);
    });

    // Badge de simulation en direct
    if (this.simulationResult?.nodes_trace?.[nodeData.id]) {
      const trace = this.simulationResult.nodes_trace[nodeData.id];
      const badge = document.createElement('div');
      if (trace.status === 'success') {
        badge.className = 'node-sim-badge is-success';
        badge.title = 'Exécuté avec succès';
        badge.innerHTML = '<img src="/static_base_icons?name=check&fill=white&size=10">';
      } else if (trace.status === 'error') {
        badge.className = 'node-sim-badge is-error';
        badge.title = `Erreur : ${trace.error || 'Échec'}`;
        badge.innerHTML = '<img src="/static_base_icons?name=close&fill=white&size=10">';
      } else {
        badge.className = 'node-sim-badge is-skipped';
        badge.title = 'Branche non empruntée';
        badge.innerHTML = '<span style="font-weight:bold;line-height:1;">-</span>';
      }
      el.appendChild(badge);
    }

    return el;
  }

  // -------------------------------------------------------------
  // 3. Rendu des Connexions SVG (Bézier Curves)
  // -------------------------------------------------------------
  renderConnections() {
    // Supprimer les lignes existantes sauf le fil temporaire
    const paths = this.svg.querySelectorAll('.connection-path');
    paths.forEach(p => p.remove());

    this.connections.forEach((conn, index) => {
      const srcPort = this.getPortCoordinates(conn.source_node, conn.source_output || 'main', 'output');
      const tgtPort = this.getPortCoordinates(conn.target_node, conn.target_input || 'main', 'input');

      if (!srcPort || !tgtPort) return;

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', this.calculateBezierPath(srcPort.x, srcPort.y, tgtPort.x, tgtPort.y));
      path.setAttribute('class', 'connection-path');
      path.dataset.index = index;
      path.setAttribute('title', `Liaison: ${conn.source_node} (${conn.source_output}) -> ${conn.target_node}. Clic pour supprimer.`);

      // Couleur conditionnelle pour les branches true / false / error
      if (conn.source_output === 'true') {
        path.style.stroke = '#10b981';
      } else if (conn.source_output === 'false' || conn.source_output === 'error') {
        path.style.stroke = '#ef4444';
      }

      // Clic pour supprimer la liaison
      path.addEventListener('click', (e) => {
        e.stopPropagation();
        if (confirm("Supprimer cette liaison entre les nœuds ?")) {
          this.removeConnection(index);
        }
      });

      this.svg.appendChild(path);
    });
  }

  getPortCoordinates(nodeId, portId, direction) {
    const nodeEl = document.getElementById(`nodeEl_${nodeId}`);
    if (!nodeEl) return null;

    const selector = direction === 'output' 
      ? `.node-output-port[data-port-id="${portId}"]`
      : `.node-input-port[data-port-id="${portId}"]`;

    let portEl = nodeEl.querySelector(selector);
    if (!portEl) {
      // Fallback sur le premier port disponible
      portEl = nodeEl.querySelector(direction === 'output' ? '.node-output-port' : '.node-input-port');
    }
    if (!portEl) return null;

    const nodeData = this.nodes.find(n => n.id === nodeId);
    if (!nodeData) return null;

    const portRect = portEl.getBoundingClientRect();
    const nodeRect = nodeEl.getBoundingClientRect();

    // Coordonnées relatives dans l'espace du canvas
    const x = nodeData.x + (portRect.left - nodeRect.left) + (portRect.width / 2);
    const y = nodeData.y + (portRect.top - nodeRect.top) + (portRect.height / 2);

    return { x, y };
  }

  calculateBezierPath(x1, y1, x2, y2) {
    const dx = Math.abs(x2 - x1) * 0.55;
    const curvature = Math.max(dx, 40);
    return `M ${x1} ${y1} C ${x1 + curvature} ${y1}, ${x2 - curvature} ${y2}, ${x2} ${y2}`;
  }

  // -------------------------------------------------------------
  // 4. Interactions Souris : Drag des Nœuds & Tracé des Fils
  // -------------------------------------------------------------
  setupCanvasInteractions() {
    // 1. Début de création de liaison depuis un port
    this.viewport.addEventListener('mousedown', (e) => {
      const portEl = e.target.closest('.node-port');
      if (portEl && portEl.dataset.direction === 'output') {
        e.stopPropagation();
        e.preventDefault();
        const nodeId = portEl.dataset.nodeId;
        const portId = portEl.dataset.portId;
        const coords = this.getPortCoordinates(nodeId, portId, 'output');
        if (coords) {
          this.connectingFrom = { nodeId, portId, x: coords.x, y: coords.y };
        }
        return;
      }

      // 2. Clic sur le fond du canvas -> début de panoramique (pan)
      if (e.target === this.wrapper || e.target === this.viewport || e.target === this.svg) {
        this.selectNode(null);
        this.isPanning = true;
        this.panStart = { x: e.clientX - this.panOffset.x, y: e.clientY - this.panOffset.y };
        this.viewport.classList.add('is-panning');
      }
    });

    // Déplacement de la souris (drag de nœud, tracé de fil, panoramique)
    window.addEventListener('mousemove', (e) => {
      // Cas A: Déplacement d'un nœud
      if (this.draggedNode) {
        const dx = (e.clientX - this.draggedNode.startX) / this.zoom;
        const dy = (e.clientY - this.draggedNode.startY) / this.zoom;
        const node = this.nodes.find(n => n.id === this.draggedNode.nodeId);
        if (node) {
          node.x = Math.max(20, Math.round(this.draggedNode.origX + dx));
          node.y = Math.max(20, Math.round(this.draggedNode.origY + dy));
          const el = document.getElementById(`nodeEl_${node.id}`);
          if (el) {
            el.style.left = `${node.x}px`;
            el.style.top = `${node.y}px`;
          }
          this.renderConnections();
        }
        return;
      }

      // Cas B: Tracé du fil en cours
      if (this.connectingFrom) {
        const wrapperRect = this.wrapper.getBoundingClientRect();
        const mouseCanvasX = (e.clientX - wrapperRect.left - this.panOffset.x) / this.zoom;
        const mouseCanvasY = (e.clientY - wrapperRect.top - this.panOffset.y) / this.zoom;

        if (this.tempWire) {
          this.tempWire.setAttribute('d', this.calculateBezierPath(
            this.connectingFrom.x, this.connectingFrom.y,
            mouseCanvasX, mouseCanvasY
          ));
          this.tempWire.style.display = 'block';
        }
        return;
      }

      // Cas C: Panoramique du canvas
      if (this.isPanning) {
        this.panOffset.x = e.clientX - this.panStart.x;
        this.panOffset.y = e.clientY - this.panStart.y;
        this.applyTransform();
      }
    });

    // Relâchement de la souris
    window.addEventListener('mouseup', (e) => {
      if (this.draggedNode) {
        this.draggedNode = null;
        this.updateSerializedInputs();
      }

      if (this.isPanning) {
        this.isPanning = false;
        this.viewport.classList.remove('is-panning');
      }

      if (this.connectingFrom) {
        if (this.tempWire) this.tempWire.style.display = 'none';

        // Vérifier si le drop a lieu sur un port d'entrée valide
        const portEl = document.elementFromPoint(e.clientX, e.clientY)?.closest('.node-port');
        if (portEl && portEl.dataset.direction === 'input') {
          const targetNodeId = portEl.dataset.nodeId;
          const targetPortId = portEl.dataset.portId;

          if (targetNodeId !== this.connectingFrom.nodeId) {
            this.addConnection(
              this.connectingFrom.nodeId,
              this.connectingFrom.portId,
              targetNodeId,
              targetPortId
            );
          }
        }
        this.connectingFrom = null;
      }
    });
  }

  startDraggingNode(nodeId, e) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    this.draggedNode = {
      nodeId,
      startX: e.clientX,
      startY: e.clientY,
      origX: node.x,
      origY: node.y,
    };
  }

  applyTransform() {
    this.viewport.style.transform = `translate(${this.panOffset.x}px, ${this.panOffset.y}px) scale(${this.zoom})`;
  }

  zoomIn() {
    this.zoom = Math.min(2.0, this.zoom + 0.15);
    this.applyTransform();
  }

  zoomOut() {
    this.zoom = Math.max(0.4, this.zoom - 0.15);
    this.applyTransform();
  }

  resetZoom() {
    this.zoom = 1.0;
    this.panOffset = { x: 60, y: 60 };
    this.applyTransform();
  }

  // -------------------------------------------------------------
  // 5. Gestion des Liaisons (Connections)
  // -------------------------------------------------------------
  addConnection(sourceNode, sourceOutput, targetNode, targetInput) {
    // Éviter les doublons
    const exists = this.connections.some(c => 
      c.source_node === sourceNode &&
      c.source_output === sourceOutput &&
      c.target_node === targetNode &&
      c.target_input === targetInput
    );
    if (exists) return;

    this.connections.push({
      source_node: sourceNode,
      source_output: sourceOutput,
      target_node: targetNode,
      target_input: targetInput,
    });

    this.renderConnections();
    this.updateSerializedInputs();
  }

  removeConnection(index) {
    this.connections.splice(index, 1);
    this.renderConnections();
    this.updateSerializedInputs();
  }

  // -------------------------------------------------------------
  // 6. Gestion des Nœuds (Ajout, Sélection, Suppression)
  // -------------------------------------------------------------
  addNode(nodeType, x = null, y = null) {
    const def = this.nodesMap.get(nodeType);
    if (!def) return;

    const id = 'node_' + Math.random().toString(36).substr(2, 8);
    const newX = x !== null ? x : (150 + (this.nodes.length * 40));
    const newY = y !== null ? y : (180 + (this.nodes.length * 30));

    const newNode = {
      id: id,
      type: nodeType,
      name: def.name,
      x: newX,
      y: newY,
      configuration: {},
    };

    // Valeurs par défaut du schéma
    const schema = def.schema || {};
    Object.keys(schema).forEach(k => {
      if (schema[k].default !== undefined) {
        newNode.configuration[k] = JSON.parse(JSON.stringify(schema[k].default));
      }
    });

    this.nodes.push(newNode);
    this.renderNodes();
    this.selectNode(id);
    this.updateSerializedInputs();
  }

  deleteNode(nodeId) {
    if (!confirm("Voulez-vous vraiment supprimer ce nœud ?")) return;

    this.nodes = this.nodes.filter(n => n.id !== nodeId);
    this.connections = this.connections.filter(c => c.source_node !== nodeId && c.target_node !== nodeId);

    if (this.selectedNodeId === nodeId) {
      this.selectNode(null);
    }

    this.renderNodes();
    this.renderConnections();
    this.updateSerializedInputs();
  }

  selectNode(nodeId) {
    this.selectedNodeId = nodeId;

    document.querySelectorAll('.graph-node').forEach(el => {
      el.classList.toggle('is-selected', el.id === `nodeEl_${nodeId}`);
    });

    this.renderInspector();
    if (nodeId) {
      this.inspectNodeInConsole(nodeId);
    }
  }

  // -------------------------------------------------------------
  // 7. Inspecteur de Nœud Réactif & Conditionnel (Slide-over Drawer)
  // -------------------------------------------------------------
  evaluateDisplayCondition(rule, config) {
    if (!rule || typeof rule !== 'object') return true;

    // Conditions composées AND / OR
    if (Array.isArray(rule.and)) {
      return rule.and.every(subRule => this.evaluateDisplayCondition(subRule, config));
    }
    if (Array.isArray(rule.or)) {
      return rule.or.some(subRule => this.evaluateDisplayCondition(subRule, config));
    }

    const fieldName = rule.field;
    if (!fieldName) return true;

    const op = String(rule.operator || '==').toLowerCase();
    const expected = rule.value;
    const actual = config ? config[fieldName] : undefined;

    switch (op) {
      case '==':
      case '===':
      case 'equals':
        return String(actual) === String(expected);
      case '!=':
      case '!==':
      case 'not_equals':
        return String(actual) !== String(expected);
      case 'in':
        if (Array.isArray(expected)) {
          return expected.map(String).includes(String(actual));
        }
        return false;
      case 'not_in':
        if (Array.isArray(expected)) {
          return !expected.map(String).includes(String(actual));
        }
        return true;
      case '>':
        return Number(actual) > Number(expected);
      case '>=':
        return Number(actual) >= Number(expected);
      case '<':
        return Number(actual) < Number(expected);
      case '<=':
        return Number(actual) <= Number(expected);
      case 'empty':
      case 'is_empty':
        return actual === undefined || actual === null || actual === '' || (Array.isArray(actual) && actual.length === 0);
      case 'not_empty':
      case 'is_not_empty':
        return actual !== undefined && actual !== null && actual !== '' && (!Array.isArray(actual) || actual.length > 0);
      case 'truthy':
        return Boolean(actual);
      case 'falsy':
        return !Boolean(actual);
      default:
        return String(actual) === String(expected);
    }
  }

  toggleSection(sectionKey) {
    if (!this._collapsedSections) this._collapsedSections = {};
    this._collapsedSections[sectionKey] = !this._collapsedSections[sectionKey];
    const secEl = document.getElementById(`inspectorSection_${sectionKey}`);
    if (secEl) {
      secEl.classList.toggle('is-collapsed', Boolean(this._collapsedSections[sectionKey]));
    }
  }

  updateFieldsVisibility(nodeId) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;

    const def = this.nodesMap.get(node.type) || { schema: {} };
    const schema = def.schema || {};
    const config = node.configuration || {};

    const sectionVisibility = {};

    Object.keys(schema).forEach(key => {
      const field = schema[key];
      const fieldContainer = document.getElementById(`fieldGroup_${node.id}_${key}`);
      if (!fieldContainer) return;

      const isVisible = this.evaluateDisplayCondition(field.display_if, config);
      if (isVisible) {
        fieldContainer.classList.remove('d-none');
      } else {
        fieldContainer.classList.add('d-none');
      }

      const secId = field.section || 'default';
      if (!sectionVisibility[secId]) sectionVisibility[secId] = 0;
      if (isVisible) sectionVisibility[secId]++;
    });

    // Masquage automatique des sections vides
    Object.keys(sectionVisibility).forEach(secId => {
      const secEl = document.getElementById(`inspectorSection_${secId}`);
      if (secEl) {
        if (sectionVisibility[secId] === 0) {
          secEl.classList.add('d-none');
        } else {
          secEl.classList.remove('d-none');
        }
      }
    });
  }

  renderInspector() {
    const drawer = document.getElementById('nodeInspectorDrawer');
    const body = document.getElementById('nodeInspectorBody');
    const titleEl = document.getElementById('inspectorNodeTitle');
    const subtitleEl = document.getElementById('inspectorNodeSubtitle');
    const iconContainer = document.getElementById('inspectorNodeIcon');

    if (!drawer || !body) return;

    if (!this.selectedNodeId) {
      drawer.classList.remove('is-open');
      return;
    }

    const node = this.nodes.find(n => n.id === this.selectedNodeId);
    if (!node) {
      drawer.classList.remove('is-open');
      return;
    }

    const def = this.nodesMap.get(node.type) || { name: node.type, schema: {}, sections: [] };
    if (titleEl) titleEl.innerText = node.name || def.name;
    if (subtitleEl) subtitleEl.innerText = `${def.name} · ID: ${node.id}`;
    if (iconContainer) {
      iconContainer.innerHTML = this.renderNodeIcon(def.icon, 16);
      iconContainer.style.backgroundColor = def.color || '#4f46e5';
    }

    let html = `
      <div class="mb-3">
        <label class="form-label small fw-semibold">Nom d'affichage</label>
        <input type="text" class="form-control form-control-sm" value="${this.escapeHtml(node.name || '')}" oninput="canvas.updateNodeProp('${node.id}', 'name', this.value)">
      </div>
      <hr class="my-3">
    `;

    const schema = def.schema || {};
    const config = node.configuration || {};
    const sectionsDef = Array.isArray(def.sections) && def.sections.length > 0 ? def.sections : null;

    if (Object.keys(schema).length === 0) {
      html += `<div class="p-3 bg-light rounded text-muted small text-center">Aucun paramètre requis pour ce nœud.</div>`;
    } else {
      // Regroupement des champs par section
      const sectionsMap = new Map();
      if (sectionsDef) {
        sectionsDef.forEach(s => sectionsMap.set(s.id, { id: s.id, label: s.label, icon: s.icon, fields: [] }));
      }
      sectionsMap.set('default', { id: 'default', label: 'Paramètres du Nœud', icon: 'sliders-h', fields: [] });

      Object.keys(schema).forEach(key => {
        const field = schema[key];
        const secId = field.section && sectionsMap.has(field.section) ? field.section : 'default';
        sectionsMap.get(secId).fields.push({ key, field });
      });

      // Construction du markup des champs par section
      sectionsMap.forEach((sec, secId) => {
        if (sec.fields.length === 0) return;

        const isCollapsed = Boolean(this._collapsedSections && this._collapsedSections[secId]);
        const secCollapsedClass = isCollapsed ? 'is-collapsed' : '';
        const secIcon = sec.icon ? this.renderNodeIcon(sec.icon, 13) : '<img src="/static_base_icons?name=layers&size=13" style="vertical-align:-2px">';

        html += `
          <div class="inspector-section mb-3 ${secCollapsedClass}" id="inspectorSection_${secId}">
            <div class="inspector-section-header" onclick="canvas.toggleSection('${secId}')">
              <div class="d-flex align-items-center gap-2">
                <span class="inspector-section-icon">${secIcon}</span>
                <span class="inspector-section-title">${this.escapeHtml(sec.label)}</span>
              </div>
              <img src="/static_base_icons?name=expand_more&size=14" class="inspector-section-chevron">
            </div>
            <div class="inspector-section-body">
        `;

        sec.fields.forEach(({ key, field }) => {
          const val = config[key] !== undefined ? config[key] : (field.default !== undefined ? field.default : '');
          const label = field.label || key;
          const desc = field.description ? `<small class="text-muted d-block mt-1">${this.escapeHtml(field.description)}</small>` : '';
          const isVisible = this.evaluateDisplayCondition(field.display_if, config);
          const hiddenClass = isVisible ? '' : 'd-none';

          html += `<div class="schema-field-group mb-3 ${hiddenClass}" id="fieldGroup_${node.id}_${key}" data-field-key="${this.escapeHtml(key)}">`;
          html += `<label class="form-label small fw-semibold">${this.escapeHtml(label)}</label>`;

          if (field.type === 'custom' || field.type === 'custum') {
            html += this.renderCustomField(node, key, field, val);
          } else if (field.type === 'payload_schema') {
            html += this.renderPayloadSchemaField(node, key, field, val);
          } else if (field.type === 'test_payload') {
            html += this.renderTestPayloadField(node, key, field, val);
          } else if (field.type === 'select') {
            html += `<select class="form-select form-select-sm" onchange="canvas.updateNodeConfig('${node.id}', '${key}', this.value); canvas.updateFieldsVisibility('${node.id}');">`;
            (field.options || []).forEach(opt => {
              const sel = String(opt.value) === String(val) ? 'selected' : '';
              html += `<option value="${this.escapeHtml(opt.value)}" ${sel}>${this.escapeHtml(opt.label)}</option>`;
            });
            html += `</select>`;
          } else if (field.type === 'textarea') {
            const inputId = `input_${node.id}_${key}`;
            html += `
              <div class="position-relative">
                <textarea id="${inputId}" class="form-control form-control-sm font-monospace" rows="3" oninput="canvas.updateNodeConfig('${node.id}', '${key}', this.value); canvas.updateFieldsVisibility('${node.id}');">${this.escapeHtml(val)}</textarea>
                <button type="button" class="btn btn-variable-picker position-absolute" style="top: 6px; right: 6px; z-index: 5;" onclick="canvas.openVariablePicker(this, '${inputId}')" title="Insérer une variable {chemin}">{}</button>
              </div>
            `;
          } else if (field.type === 'boolean') {
            const checked = Boolean(val) ? 'checked' : '';
            html += `
              <div class="form-check form-switch mt-1">
                <input class="form-check-input" type="checkbox" id="cfg_${node.id}_${key}" ${checked} onchange="canvas.updateNodeConfig('${node.id}', '${key}', this.checked); canvas.updateFieldsVisibility('${node.id}');">
                <label class="form-check-label small" for="cfg_${node.id}_${key}">Actif</label>
              </div>
            `;
          } else if (field.type === 'json') {
            const jsonStr = typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val || '{}');
            html += `<textarea class="form-control form-control-sm font-monospace" rows="4" placeholder="{}" onchange="try { canvas.updateNodeConfig('${node.id}', '${key}', JSON.parse(this.value)); canvas.updateFieldsVisibility('${node.id}'); } catch(e) { alert('Format JSON invalide'); }">${this.escapeHtml(jsonStr)}</textarea>`;
          } else {
            const inputId = `input_${node.id}_${key}`;
            html += `
              <div class="input-group input-group-sm">
                <input type="${field.type === 'number' ? 'number' : 'text'}" id="${inputId}" class="form-control" value="${this.escapeHtml(val)}" oninput="canvas.updateNodeConfig('${node.id}', '${key}', this.value); canvas.updateFieldsVisibility('${node.id}');">
                <button type="button" class="btn btn-variable-picker" onclick="canvas.openVariablePicker(this, '${inputId}')" title="Insérer une variable {chemin}">{}</button>
              </div>
            `;
          }

          html += desc;
          html += `</div>`;
        });

        html += `
            </div>
          </div>
        `;
      });
    }

    // Bloc de test unitaire d'étape
    html += `
      <hr class="my-3">
      <div class="card bg-light border-0 p-3 rounded-3">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <h6 class="fw-bold small mb-0 d-flex align-items-center gap-1">
            <img src="/static_base_icons?name=play_arrow&size=14" style="vertical-align:-2px"> Tester ce Nœud en Isolation
          </h6>
          <span class="badge bg-secondary-subtle text-secondary" style="font-size: 10px;">Test Unitaire</span>
        </div>
        <p class="x-small text-muted mb-2">
          Exécute <strong>uniquement ce nœud</strong> avec sa configuration actuelle et le payload simulé ci-dessous. Permet de vérifier les transformations, calculs et embranchements sans exécuter l'ensemble du workflow.
        </p>
        <div class="mb-2">
          <label class="form-label x-small fw-semibold text-muted mb-1">Données d'entrée simulées (JSON) :</label>
          <textarea id="nodeTestSimulatedInput" class="form-control font-monospace x-small" rows="3" placeholder='{"amount": 1500, "status": "paid"}'>{"amount": 1500, "status": "paid", "customer": {"id": "c1", "name": "Alice"}}</textarea>
        </div>
        <button type="button" class="btn btn-outline-primary btn-sm w-100 d-flex align-items-center justify-content-center gap-1" onclick="canvas.testCurrentNode('${node.id}')">
          <img src="/static_base_icons?name=science&size=14" style="vertical-align:-2px"> Lancer le test du nœud
        </button>
        <div id="nodeTestResultContainer" class="mt-2 d-none">
          <div class="x-small fw-semibold text-muted">Résultat d'exécution :</div>
          <pre id="nodeTestResultOutput" class="bg-dark text-white p-2 rounded mt-1 font-monospace x-small" style="max-height: 180px; overflow-y: auto;"></pre>
        </div>
      </div>
    `;

    body.innerHTML = html;
    drawer.classList.add('is-open');
    this.updateFieldsVisibility(node.id);
  }

  updateNodeProp(nodeId, prop, value) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    node[prop] = value;
    const titleEl = document.querySelector(`#nodeEl_${nodeId} .graph-node-title`);
    if (titleEl) titleEl.innerText = value;
    this.updateSerializedInputs();
  }

  updateNodeConfig(nodeId, key, value) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    if (!node.configuration) node.configuration = {};
    node.configuration[key] = value;
    this.updateSerializedInputs();
  }

  renderNodeIcon(iconName, size = 16) {
    if (!iconName) {
      return `<img src="/static_base_icons?name=data_object&fill=white&size=${size}" style="width:${size}px; height:${size}px; vertical-align:middle;">`;
    }
    if (iconName.startsWith('/') || iconName.startsWith('http://') || iconName.startsWith('https://')) {
      return `<img src="${this.escapeHtml(iconName)}" style="width:${size}px; height:${size}px; object-fit:contain; vertical-align:middle;">`;
    }
    if (iconName.startsWith('fa-') || iconName.startsWith('fas ') || iconName.startsWith('far ') || iconName.startsWith('fab ')) {
      return `<i class="${this.escapeHtml(iconName)}"></i>`;
    }
    return `<img src="/static_base_icons?name=${encodeURIComponent(iconName)}&fill=white&size=${size}" alt="${this.escapeHtml(iconName)}" style="width:${size}px; height:${size}px; vertical-align:middle;">`;
  }

  async testCurrentNode(nodeId) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;

    const resContainer = document.getElementById('nodeTestResultContainer');
    const resOutput = document.getElementById('nodeTestResultOutput');
    const simInputEl = document.getElementById('nodeTestSimulatedInput');
    if (!resContainer || !resOutput) return;

    let inputData = { test: true };
    if (simInputEl && simInputEl.value.trim()) {
      try {
        inputData = JSON.parse(simInputEl.value.trim());
      } catch (err) {
        resContainer.classList.remove('d-none');
        resOutput.innerHTML = `<span class="text-danger">Erreur de syntaxe JSON dans les données d'entrée : ${this.escapeHtml(err.message)}</span>`;
        return;
      }
    }

    resContainer.classList.remove('d-none');
    resOutput.innerHTML = `<span class="text-warning"><img src="/static_base_icons?name=sync&size=12" class="me-1" style="vertical-align:-2px"> Exécution du nœud en cours...</span>`;

    try {
      const resp = await fetch('/api/melodi_automation/nodes/test-step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: node.id,
          node_type: node.type,
          configuration: node.configuration || {},
          input_data: inputData,
        }),
      });
      const data = await resp.json();
      if (resp.ok && data.status === 'success') {
        let varsHtml = '';
        if (Array.isArray(data.output_variables) && data.output_variables.length > 0) {
          varsHtml = `
            <div class="mb-2 p-2 bg-secondary-subtle rounded border">
              <div class="x-small fw-bold text-dark mb-1 d-flex align-items-center gap-1">
                <img src="/static_base_icons?name=tag&size=12" style="vertical-align:-2px"> Variables extraites de la sortie :
              </div>
              <div class="d-flex flex-wrap gap-1">
                ${data.output_variables.map(v => {
                  const typeCls = `type-${(v.type || 'other').toLowerCase()}`;
                  return `<span class="badge bg-white text-dark border p-1" style="font-size:10px;">
                    <span class="n8n-type-badge ${typeCls} me-1">${this.escapeHtml(v.type)}</span>
                    <code>{${this.escapeHtml(v.path)}}</code>
                  </span>`;
                }).join('')}
              </div>
            </div>
          `;
        }
        resOutput.innerHTML = `
          ${varsHtml}
          <div class="x-small text-success mb-1">✓ Exécuté en ${data.duration_ms || 0}ms (Port activé: ${(data.active_ports || ['main']).join(', ')})</div>
          <pre class="bg-dark text-white p-2 rounded mb-0 font-monospace x-small" style="max-height: 180px; overflow-y: auto;">${this.escapeHtml(JSON.stringify(data.output_data, null, 2))}</pre>
        `;
      } else {
        resOutput.innerHTML = `<span class="text-danger">✗ Erreur : ${this.escapeHtml(data.error || data.message || 'Échec')}</span>`;
      }
    } catch (e) {
      resOutput.innerHTML = `<span class="text-danger">✗ Erreur réseau : ${this.escapeHtml(e.message)}</span>`;
    }
  }

  // -------------------------------------------------------------
  // 8. Synchronisation des Formulaires Cachés
  // -------------------------------------------------------------
  updateSerializedInputs() {
    const nodesInput = document.getElementById('nodesJsonInput');
    const connsInput = document.getElementById('connectionsJsonInput');
    const typesInput = document.getElementById('customTypesJsonInput');
    if (nodesInput) nodesInput.value = JSON.stringify(this.nodes);
    if (connsInput) connsInput.value = JSON.stringify(this.connections);
    if (typesInput) typesInput.value = JSON.stringify(this.customTypes || []);

    const countBadge = document.getElementById('customTypesCountBadge');
    if (countBadge) {
      countBadge.innerText = String((this.customTypes || []).length);
    }
  }

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // -------------------------------------------------------------
  // 9. Gestion du Type de Schéma 'custom' (Visuel & Code JSON)
  // -------------------------------------------------------------
  renderCustomField(node, key, field, val) {
    const fieldKey = `${node.id}_${key}`;
    const mode = this._customFieldModes[fieldKey] || 'visual';

    // Normalisation en liste d'objets { key, value, type }
    let rows = [];
    if (Array.isArray(val)) {
      rows = val.map(item => {
        if (typeof item === 'object' && item !== null) {
          if ('key' in item) {
            return {
              key: item.key || '',
              value: item.value !== undefined ? item.value : '',
              type: item.type || 'string',
            };
          } else {
            const firstK = Object.keys(item)[0] || '';
            return { key: firstK, value: item[firstK] !== undefined ? item[firstK] : '', type: 'string' };
          }
        }
        return { key: String(item), value: '', type: 'string' };
      });
    } else if (typeof val === 'object' && val !== null) {
      if ('key' in val && 'value' in val) {
        rows = [{ key: val.key || '', value: val.value !== undefined ? val.value : '', type: val.type || 'string' }];
      } else {
        rows = Object.entries(val).map(([k, v]) => ({
          key: k,
          value: typeof v === 'object' ? JSON.stringify(v) : v,
          type: typeof v === 'number' ? 'number' : (typeof v === 'boolean' ? 'boolean' : (typeof v === 'object' ? 'json' : 'string')),
        }));
      }
    } else if (typeof val === 'string' && val.trim()) {
      try {
        const parsed = JSON.parse(val);
        return this.renderCustomField(node, key, field, parsed);
      } catch (e) {
        rows = [{ key: 'var1', value: val, type: 'string' }];
      }
    }

    if (rows.length === 0) {
      rows = [{ key: '', value: '', type: 'string' }];
    }

    if (!node.configuration[key] || (mode === 'visual' && !Array.isArray(node.configuration[key]))) {
      node.configuration[key] = rows;
    }

    let outHtml = `
      <div class="custom-field-container mb-3" data-field-key="${this.escapeHtml(key)}">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <label class="form-label small fw-semibold mb-0">${this.escapeHtml(field.label || key)}</label>
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-secondary py-0 px-2 ${mode === 'visual' ? 'active' : ''}" onclick="canvas.switchCustomFieldMode('${node.id}', '${key}', 'visual')">Visuel</button>
            <button type="button" class="btn btn-outline-secondary py-0 px-2 ${mode === 'code' ? 'active' : ''}" onclick="canvas.switchCustomFieldMode('${node.id}', '${key}', 'code')">Code JSON</button>
          </div>
        </div>
        ${field.description ? `<small class="text-muted d-block mb-2">${this.escapeHtml(field.description)}</small>` : ''}
    `;

    if (mode === 'visual') {
      outHtml += `
        <div class="custom-var-table">
          <div class="custom-var-table-header d-flex gap-1 mb-1 px-1 text-muted x-small fw-semibold">
            <div style="flex: 1.2;">Nom variable (clé)</div>
            <div style="width: 85px;">Type</div>
            <div style="flex: 1.8;">Valeur / Expression</div>
            <div style="width: 32px;"></div>
          </div>
          <div class="custom-var-rows-container">
      `;

      rows.forEach((r, idx) => {
        const valInputId = `customVal_${node.id}_${key}_${idx}`;
        outHtml += `
          <div class="custom-var-row d-flex align-items-center gap-1 mb-1">
            <input type="text" class="form-control form-control-sm font-monospace" style="flex: 1.2; font-size: 11px;" placeholder="clé" value="${this.escapeHtml(r.key)}" oninput="canvas.updateCustomFieldRow('${node.id}', '${key}', ${idx}, 'key', this.value)">
            <select class="form-select form-select-sm" style="width: 85px; font-size: 11px;" onchange="canvas.updateCustomFieldRow('${node.id}', '${key}', ${idx}, 'type', this.value)">
              <option value="string" ${r.type === 'string' ? 'selected' : ''}>Texte</option>
              <option value="number" ${r.type === 'number' ? 'selected' : ''}>Nombre</option>
              <option value="boolean" ${r.type === 'boolean' ? 'selected' : ''}>Booléen</option>
              <option value="json" ${r.type === 'json' ? 'selected' : ''}>JSON</option>
              <option value="expression" ${r.type === 'expression' ? 'selected' : ''}>Expr.</option>
            </select>
            <div class="input-group input-group-sm" style="flex: 1.8;">
              <input type="text" id="${valInputId}" class="form-control font-monospace" style="font-size: 11px;" placeholder="valeur ou {var}" value="${this.escapeHtml(String(r.value !== undefined ? r.value : ''))}" oninput="canvas.updateCustomFieldRow('${node.id}', '${key}', ${idx}, 'value', this.value)">
              <button type="button" class="btn btn-variable-picker" onclick="canvas.openVariablePicker(this, '${valInputId}')" title="Insérer une variable {chemin}">{}</button>
            </div>
            <button type="button" class="btn btn-outline-danger btn-sm p-1" style="width: 32px; height: 31px;" onclick="canvas.removeCustomFieldRow('${node.id}', '${key}', ${idx})" title="Supprimer">
              <img src="/static_base_icons?name=delete&fill=%23dc3545&size=14" style="vertical-align:-2px">
            </button>
          </div>
        `;
      });

      outHtml += `
          </div>
          <button type="button" class="btn btn-outline-primary btn-sm mt-2 w-100 d-flex align-items-center justify-content-center gap-1" onclick="canvas.addCustomFieldRow('${node.id}', '${key}')">
            <img src="/static_base_icons?name=add&size=14" style="vertical-align:-2px"> Ajouter une variable
          </button>
        </div>
      `;
    } else {
      const jsonStr = typeof node.configuration[key] === 'string'
        ? node.configuration[key]
        : JSON.stringify(node.configuration[key] || rows, null, 2);

      outHtml += `
        <div class="custom-code-container">
          <textarea class="form-control font-monospace custom-code-area" rows="7" style="font-size: 11px;" oninput="canvas.updateCustomFieldFromCode('${node.id}', '${key}', this.value)">${this.escapeHtml(jsonStr)}</textarea>
          <div id="customCodeFeedback_${node.id}_${key}" class="text-muted x-small mt-1">JSON synchronisé avec le mode visuel.</div>
        </div>
      `;
    }

    outHtml += `</div>`;
    return outHtml;
  }

  switchCustomFieldMode(nodeId, key, mode) {
    this._customFieldModes[`${nodeId}_${key}`] = mode;
    this.renderInspector();
  }

  addCustomFieldRow(nodeId, key) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    if (!Array.isArray(node.configuration[key])) {
      node.configuration[key] = [];
    }
    node.configuration[key].push({ key: '', value: '', type: 'string' });
    this.updateSerializedInputs();
    this.renderInspector();
  }

  updateCustomFieldRow(nodeId, key, index, prop, value) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node || !Array.isArray(node.configuration[key])) return;
    if (!node.configuration[key][index]) {
      node.configuration[key][index] = { key: '', value: '', type: 'string' };
    }
    node.configuration[key][index][prop] = value;
    this.updateSerializedInputs();
  }

  removeCustomFieldRow(nodeId, key, index) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node || !Array.isArray(node.configuration[key])) return;
    node.configuration[key].splice(index, 1);
    this.updateSerializedInputs();
    this.renderInspector();
  }

  updateCustomFieldFromCode(nodeId, key, codeStr) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    const feedbackEl = document.getElementById(`customCodeFeedback_${nodeId}_${key}`);
    try {
      const parsed = JSON.parse(codeStr);
      node.configuration[key] = parsed;
      this.updateSerializedInputs();
      if (feedbackEl) {
        feedbackEl.className = 'text-success x-small mt-1';
        feedbackEl.innerText = '✓ JSON valide et synchronisé.';
      }
    } catch (e) {
      if (feedbackEl) {
        feedbackEl.className = 'text-danger x-small mt-1';
        feedbackEl.innerText = '✗ Syntaxe JSON invalide : ' + e.message;
      }
    }
  }

  // -------------------------------------------------------------
  // 9b. Gestion du Type de Schéma 'payload_schema' (Déclencheurs)
  // -------------------------------------------------------------
  renderPayloadSchemaField(node, key, field, val) {
    const fieldKey = `${node.id}_${key}`;
    const mode = this._customFieldModes[fieldKey] || 'visual';
    const isStrict = node.configuration?.validation_mode === 'strict';

    // Normalisation en liste d'objets { key, type, required, default, description, custom_type, custom_type_ref, item_type }
    let rows = [];
    if (Array.isArray(val)) {
      rows = val.map(item => {
        if (typeof item === 'object' && item !== null) {
          return {
            key: item.key || item.name || '',
            type: item.type || 'string',
            required: item.required !== undefined ? Boolean(item.required) : true,
            default: item.default !== undefined && item.default !== null ? item.default : '',
            description: item.description || '',
            custom_type: item.custom_type || item.custom_type_ref || '',
            custom_type_ref: item.custom_type_ref || item.custom_type || '',
            item_type: item.item_type || '',
          };
        }
        return { key: String(item), type: 'string', required: true, default: '', description: '', custom_type: '', custom_type_ref: '', item_type: '' };
      });
    } else if (typeof val === 'object' && val !== null) {
      rows = Object.entries(val).map(([k, v]) => {
        if (typeof v === 'object' && v !== null) {
          return {
            key: k,
            type: v.type || 'string',
            required: v.required !== undefined ? Boolean(v.required) : true,
            default: v.default !== undefined && v.default !== null ? v.default : '',
            description: v.description || '',
            custom_type: v.custom_type || v.custom_type_ref || '',
            custom_type_ref: v.custom_type_ref || v.custom_type || '',
            item_type: v.item_type || '',
          };
        }
        return { key: k, type: String(v || 'string'), required: true, default: '', description: '', custom_type: '', custom_type_ref: '', item_type: '' };
      });
    }

    if (rows.length === 0) {
      rows = [{ key: '', type: 'string', required: true, default: '', description: '', custom_type: '', custom_type_ref: '', item_type: '' }];
    }

    if (!node.configuration[key] || (mode === 'visual' && !Array.isArray(node.configuration[key]))) {
      node.configuration[key] = rows;
    }

    let outHtml = `
      <div class="payload-schema-container mb-3" data-field-key="${this.escapeHtml(key)}">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <label class="form-label small fw-semibold mb-0">
            <img src="/static_base_icons?name=category&size=14" style="vertical-align:-2px" class="me-1"> ${this.escapeHtml(field.label || key)}
          </label>
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-secondary py-0 px-2 ${mode === 'visual' ? 'active' : ''}" onclick="canvas.switchPayloadSchemaMode('${node.id}', '${key}', 'visual')">Visuel</button>
            <button type="button" class="btn btn-outline-secondary py-0 px-2 ${mode === 'code' ? 'active' : ''}" onclick="canvas.switchPayloadSchemaMode('${node.id}', '${key}', 'code')">Code JSON</button>
          </div>
        </div>
        ${field.description ? `<small class="text-muted d-block mb-2">${this.escapeHtml(field.description)}</small>` : ''}
    `;

    if (!isStrict) {
      outHtml += `
        <div class="alert alert-light border py-1 px-2 mb-2 x-small text-muted d-flex align-items-center gap-1">
          <img src="/static_base_icons?name=info&size=14" style="vertical-align:-2px">
          <span>Mode <strong>Permissif</strong> actif : les valeurs par défaut sont injectées et la validation stricte s'active si vous sélectionnez <strong>Structure stricte</strong>.</span>
        </div>
      `;
    }

    if (mode === 'visual') {
      const customTypesList = this.customTypes || [];

      outHtml += `
        <div class="payload-schema-table">
          <div class="d-flex gap-1 mb-1 px-1 text-muted x-small fw-semibold">
            <div style="flex: 1.2;">Champ (clé)</div>
            <div style="width: 125px;">Type attendu</div>
            <div style="flex: 1.0;">Valeur par défaut</div>
            <div style="width: 50px;" class="text-center">Requis</div>
            <div style="width: 28px;"></div>
          </div>
          <div class="payload-schema-rows-container">
      `;

      rows.forEach((r, idx) => {
        const currentType = String(r.type || 'string');
        const customTypeRef = String(r.custom_type || r.custom_type_ref || (currentType.startsWith('custom:') ? currentType.split(':')[1] : (currentType !== 'custom' ? currentType : '')));
        const isCustomType = currentType === 'custom' || currentType.startsWith('custom:') || customTypesList.some(ct => ct.name === currentType || ct.name === customTypeRef);
        const resolvedTypeName = isCustomType ? (customTypeRef || (customTypesList.find(ct => ct.name === currentType)?.name || '')) : currentType;
        const matchedCustomType = customTypesList.find(ct => ct.name === resolvedTypeName);

        outHtml += `
          <div class="mb-1 p-1 bg-white rounded border">
            <div class="d-flex align-items-center gap-1">
              <input type="text" class="form-control form-control-sm font-monospace" style="flex: 1.2; font-size: 11px;" placeholder="ex: order_id" value="${this.escapeHtml(r.key)}" oninput="canvas.updatePayloadSchemaRow('${node.id}', '${key}', ${idx}, 'key', this.value)">
              <select class="form-select form-select-sm" style="width: 125px; font-size: 11px;" onchange="canvas.onPayloadSchemaTypeChanged('${node.id}', '${key}', ${idx}, this.value)">
                <optgroup label="Types Primitifs">
                  <option value="string" ${!isCustomType && currentType === 'string' ? 'selected' : ''}>Texte (str)</option>
                  <option value="number" ${!isCustomType && currentType === 'number' ? 'selected' : ''}>Nombre (float)</option>
                  <option value="integer" ${!isCustomType && (currentType === 'integer' || currentType === 'int') ? 'selected' : ''}>Entier (int)</option>
                  <option value="boolean" ${!isCustomType && (currentType === 'boolean' || currentType === 'bool') ? 'selected' : ''}>Booléen</option>
                  <option value="array" ${!isCustomType && currentType === 'array' ? 'selected' : ''}>Tableau []</option>
                  <option value="object" ${!isCustomType && currentType === 'object' ? 'selected' : ''}>Objet {}</option>
                  <option value="any" ${!isCustomType && currentType === 'any' ? 'selected' : ''}>Tous (any)</option>
                </optgroup>
                <optgroup label="Formats Spécifiques">
                  <option value="email" ${!isCustomType && currentType === 'email' ? 'selected' : ''}>Email</option>
                  <option value="date" ${!isCustomType && (currentType === 'date' || currentType === 'datetime') ? 'selected' : ''}>Date / Heure</option>
                  <option value="uuid" ${!isCustomType && currentType === 'uuid' ? 'selected' : ''}>UUID</option>
                </optgroup>
                ${customTypesList.length > 0 ? `
                <optgroup label="Types Personnalisés (Structs)">
                  ${customTypesList.map(ct => {
                    const isSel = isCustomType && (resolvedTypeName === ct.name || customTypeRef === ct.name || currentType === ct.name);
                    return `<option value="custom:${this.escapeHtml(ct.name)}" ${isSel ? 'selected' : ''}>📦 ${this.escapeHtml(ct.name)}</option>`;
                  }).join('')}
                </optgroup>
                ` : ''}
              </select>
              <input type="text" class="form-control form-control-sm font-monospace" style="flex: 1.0; font-size: 11px;" placeholder="Défaut (opt.)" value="${this.escapeHtml(r.default !== undefined && r.default !== null ? String(r.default) : '')}" oninput="canvas.updatePayloadSchemaRow('${node.id}', '${key}', ${idx}, 'default', this.value)" title="Valeur injectée automatiquement si omise">
              <div style="width: 50px;" class="text-center form-check form-switch m-0 d-flex justify-content-center">
                <input class="form-check-input" type="checkbox" ${r.required ? 'checked' : ''} onchange="canvas.updatePayloadSchemaRow('${node.id}', '${key}', ${idx}, 'required', this.checked)" title="Champ obligatoire">
              </div>
              <button type="button" class="btn btn-outline-danger btn-sm p-1" style="width: 28px; height: 30px;" onclick="canvas.removePayloadSchemaRow('${node.id}', '${key}', ${idx})" title="Supprimer ce champ">
                <img src="/static_base_icons?name=delete&fill=%23dc3545&size=14" style="vertical-align:-2px">
              </button>
            </div>
            ${matchedCustomType ? `
            <div class="mt-1 pt-1 border-top d-flex align-items-center justify-content-between x-small text-muted" style="font-size: 10px;">
              <span>
                <img src="/static_base_icons?name=layers&size=12" class="me-1" style="vertical-align:-2px">
                Structure <strong>${this.escapeHtml(matchedCustomType.name)}</strong> : ${(matchedCustomType.fields || []).map(f => `<code class="text-dark">${this.escapeHtml(f.key)}:${this.escapeHtml(f.type)}</code>`).join(', ') || 'aucun champ'}
              </span>
              <button type="button" class="btn btn-link btn-sm p-0 text-decoration-none x-small" onclick="canvas.openCustomTypesModal('${this.escapeHtml(matchedCustomType.id)}')">Modifier</button>
            </div>
            ` : ''}
          </div>
        `;
      });

      outHtml += `
          </div>
          <div class="d-flex gap-2 mt-2">
            <button type="button" class="btn btn-outline-primary btn-sm flex-grow-1" onclick="canvas.addPayloadSchemaRow('${node.id}', '${key}')">
              <img src="/static_base_icons?name=add&size=13" class="me-1" style="vertical-align:-2px"> Ajouter un champ
            </button>
            <button type="button" class="btn btn-outline-secondary btn-sm" onclick="canvas.openCustomTypesModal()" title="Créer ou gérer les structures réutilisables">
              <img src="/static_base_icons?name=category&size=13" class="me-1" style="vertical-align:-2px"> Gérer les Types
            </button>
            <button type="button" class="btn btn-outline-secondary btn-sm" onclick="canvas.inferPayloadSchema('${node.id}', '${key}')" title="Déduire les types automatiquement depuis le payload de test">
              <img src="/static_base_icons?name=auto_fix_high&size=13" class="me-1" style="vertical-align:-2px"> Déduire
            </button>
          </div>
        </div>
      `;
    } else {
      const jsonStr = typeof node.configuration[key] === 'string'
        ? node.configuration[key]
        : JSON.stringify(node.configuration[key] || rows, null, 2);

      outHtml += `
        <div class="payload-schema-code-container">
          <textarea class="form-control font-monospace custom-code-area" rows="7" style="font-size: 11px;" oninput="canvas.updatePayloadSchemaFromCode('${node.id}', '${key}', this.value)">${this.escapeHtml(jsonStr)}</textarea>
          <div id="payloadSchemaCodeFeedback_${node.id}_${key}" class="text-muted x-small mt-1">JSON synchronisé avec le mode visuel (champs 'key', 'type', 'required', 'default').</div>
        </div>
      `;
    }

    outHtml += `</div>`;
    return outHtml;
  }

  switchPayloadSchemaMode(nodeId, key, mode) {
    this._customFieldModes[`${nodeId}_${key}`] = mode;
    this.renderInspector();
  }

  addPayloadSchemaRow(nodeId, key) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    if (!Array.isArray(node.configuration[key])) {
      node.configuration[key] = [];
    }
    node.configuration[key].push({ key: '', type: 'string', required: true, default: '', description: '' });
    this.updateSerializedInputs();
    this.renderInspector();
  }

  onPayloadSchemaTypeChanged(nodeId, key, index, selectedType) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node || !Array.isArray(node.configuration[key])) return;
    if (!node.configuration[key][index]) {
      node.configuration[key][index] = { key: '', type: 'string', required: true, default: '', description: '' };
    }
    const row = node.configuration[key][index];
    if (selectedType.startsWith('custom:')) {
      const typeName = selectedType.split(':', 2)[1];
      row.type = 'custom';
      row.custom_type = typeName;
      row.custom_type_ref = typeName;
    } else {
      row.type = selectedType;
      delete row.custom_type;
      delete row.custom_type_ref;
    }
    this.updateSerializedInputs();
    this.renderInspector();
  }

  updatePayloadSchemaRow(nodeId, key, index, prop, value) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node || !Array.isArray(node.configuration[key])) return;
    if (!node.configuration[key][index]) {
      node.configuration[key][index] = { key: '', type: 'string', required: true, default: '', description: '' };
    }
    node.configuration[key][index][prop] = value;
    this.updateSerializedInputs();
  }

  removePayloadSchemaRow(nodeId, key, index) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node || !Array.isArray(node.configuration[key])) return;
    node.configuration[key].splice(index, 1);
    this.updateSerializedInputs();
    this.renderInspector();
  }

  updatePayloadSchemaFromCode(nodeId, key, codeStr) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    const feedbackEl = document.getElementById(`payloadSchemaCodeFeedback_${nodeId}_${key}`);
    try {
      const parsed = JSON.parse(codeStr);
      node.configuration[key] = parsed;
      this.updateSerializedInputs();
      if (feedbackEl) {
        feedbackEl.className = 'text-success x-small mt-1';
        feedbackEl.innerText = '✓ JSON valide et synchronisé.';
      }
    } catch (e) {
      if (feedbackEl) {
        feedbackEl.className = 'text-danger x-small mt-1';
        feedbackEl.innerText = '✗ Syntaxe JSON invalide : ' + e.message;
      }
    }
  }

  inferPayloadSchema(nodeId, key) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    const sample = this.getEffectiveTestPayload();
    if (!sample || Object.keys(sample).length === 0) {
      alert("Aucun payload de test disponible pour déduire le schéma. Renseignez un payload de test ci-dessous ou ouvrez le modal de payload.");
      return;
    }
    const rows = [];
    const extract = (obj, prefix = '') => {
      if (typeof obj === 'object' && obj !== null) {
        if (Array.isArray(obj)) {
          rows.push({ key: prefix, type: 'array', required: true, default: '' });
        } else {
          Object.entries(obj).forEach(([k, v]) => {
            const p = prefix ? `${prefix}.${k}` : k;
            if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
              rows.push({ key: p, type: 'object', required: true, default: '' });
              extract(v, p);
            } else if (Array.isArray(v)) {
              rows.push({ key: p, type: 'array', required: true, default: '' });
            } else if (typeof v === 'number') {
              rows.push({ key: p, type: 'number', required: true, default: String(v) });
            } else if (typeof v === 'boolean') {
              rows.push({ key: p, type: 'boolean', required: true, default: String(v) });
            } else {
              rows.push({ key: p, type: 'string', required: true, default: String(v || '') });
            }
          });
        }
      }
    };
    extract(sample);
    if (rows.length > 0) {
      node.configuration[key] = rows;
      this.updateSerializedInputs();
      this.renderInspector();
    }
  }

  // -------------------------------------------------------------
  // 9c. Gestion du Payload de Test Dédié (Simulation & Builder)
  // -------------------------------------------------------------
  renderTestPayloadField(node, key, field, val) {
    let jsonStr = '';
    if (typeof val === 'object' && val !== null) {
      jsonStr = JSON.stringify(val, null, 2);
    } else if (typeof val === 'string' && val.trim()) {
      jsonStr = val;
    } else {
      jsonStr = '{}';
    }

    return `
      <div class="test-payload-box mb-3 border rounded p-2 bg-light">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <label class="form-label small fw-semibold mb-0 text-primary d-flex align-items-center gap-1">
            <img src="/static_base_icons?name=science&size=14" style="vertical-align:-2px"> ${this.escapeHtml(field.label || 'Payload de test')}
          </label>
          <span class="badge bg-warning-subtle text-dark border x-small">Build uniquement</span>
        </div>
        <small class="text-muted d-block mb-2" style="font-size: 11px;">
          <img src="/static_base_icons?name=shield&size=13" class="me-1" style="vertical-align:-2px">
          Données simulées pour tester le workflow dans le Builder. <strong>Strictement ignoré en production</strong>.
        </small>
        <textarea id="testPayloadInput_${node.id}" class="form-control font-monospace" rows="6" style="font-size: 11px;" oninput="canvas.updateTestPayloadFromInspector('${node.id}', '${key}', this.value)">${this.escapeHtml(jsonStr)}</textarea>
        <div id="testPayloadFeedback_${node.id}" class="text-muted x-small mt-1">Payload de simulation synchronisé.</div>
        <div class="d-flex gap-2 mt-2">
          <button type="button" class="btn btn-outline-primary btn-sm flex-grow-1 d-flex align-items-center justify-content-center gap-1" style="font-size: 11px;" onclick="canvas.generateAndFillTestPayload('${node.id}', '${key}')" title="Générer un payload de test depuis les clés et valeurs par défaut du schéma">
            <img src="/static_base_icons?name=auto_fix_high&size=12" style="vertical-align:-2px"> Générer depuis le schéma
          </button>
          <button type="button" class="btn btn-primary btn-sm d-flex align-items-center justify-content-center gap-1" style="font-size: 11px;" onclick="canvas.runSimulationWithNodeTestPayload('${node.id}', '${key}')" title="Simuler immédiatement le graphe avec ce payload">
            <img src="/static_base_icons?name=play_arrow&fill=white&size=12" style="vertical-align:-2px"> Simuler
          </button>
        </div>
      </div>
    `;
  }

  updateTestPayloadFromInspector(nodeId, key, codeStr) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    const feedbackEl = document.getElementById(`testPayloadFeedback_${nodeId}`);
    try {
      const parsed = JSON.parse(codeStr || '{}');
      if (!node.configuration) node.configuration = {};
      node.configuration[key] = parsed;
      this.simulationInitialPayload = parsed;
      this.updateSerializedInputs();
      if (feedbackEl) {
        feedbackEl.className = 'text-success x-small mt-1';
        feedbackEl.innerText = '✓ Payload de test valide et mémorisé.';
      }
    } catch (e) {
      if (feedbackEl) {
        feedbackEl.className = 'text-danger x-small mt-1';
        feedbackEl.innerText = '✗ Syntaxe JSON invalide : ' + e.message;
      }
    }
  }

  generateAndFillTestPayload(nodeId, key) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    const schemaDef = node.configuration?.payload_schema || [];
    const generated = this.generateTestPayloadFromSchema(schemaDef);
    if (!node.configuration) node.configuration = {};
    node.configuration[key] = generated;
    this.simulationInitialPayload = generated;
    this.updateSerializedInputs();
    this.renderInspector();
  }

  runSimulationWithNodeTestPayload(nodeId, key) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (node && node.configuration && node.configuration[key]) {
      let tp = node.configuration[key];
      if (typeof tp === 'string') {
        try { tp = JSON.parse(tp); } catch (e) { tp = {}; }
      }
      this.simulationInitialPayload = tp;
    }
    this.runGraphSimulation();
  }

  generateTestPayloadFromSchema(schemaRows) {
    const result = {};
    if (!schemaRows) return result;

    let rows = [];
    if (Array.isArray(schemaRows)) {
      rows = schemaRows;
    } else if (typeof schemaRows === 'object') {
      rows = Object.entries(schemaRows).map(([k, v]) => ({
        key: k,
        ...(typeof v === 'object' && v !== null ? v : { type: String(v) })
      }));
    }

    const setNested = (obj, path, val) => {
      const parts = path.split('.');
      let curr = obj;
      for (let i = 0; i < parts.length - 1; i++) {
        const p = parts[i];
        if (!curr[p] || typeof curr[p] !== 'object' || Array.isArray(curr[p])) {
          curr[p] = {};
        }
        curr = curr[p];
      }
      curr[parts[parts.length - 1]] = val;
    };

    const customTypesList = this.customTypes || [];
    const customTypesMap = new Map();
    customTypesList.forEach(ct => {
      if (ct.name) {
        customTypesMap.set(ct.name, ct);
        customTypesMap.set(ct.name.toLowerCase(), ct);
      }
    });

    const generateSingleValue = (typeStr, defaultStr, customRef, keyName, depth = 0) => {
      if (depth > 5) return {}; // protection récursion
      const t = (typeStr || 'string').toLowerCase().trim();
      const customName = customRef || (t.startsWith('custom:') ? t.split(':')[1] : (t === 'custom' ? customRef : t));
      const matchedCt = customTypesMap.get(customName) || customTypesMap.get(customName?.toLowerCase());

      if (matchedCt) {
        const nestedObj = {};
        (matchedCt.fields || []).forEach(f => {
          nestedObj[f.key] = generateSingleValue(f.type, f.default, f.custom_type || f.custom_type_ref, f.key, depth + 1);
        });
        return nestedObj;
      }

      if (defaultStr !== undefined && defaultStr !== null && String(defaultStr).trim() !== '') {
        const s = String(defaultStr).trim();
        if (t === 'number' || t === 'float') return Number(s) || 0;
        if (t === 'integer' || t === 'int') return parseInt(s, 10) || 0;
        if (t === 'boolean' || t === 'bool') return ['true', '1', 'yes', 'oui'].includes(s.toLowerCase());
        if (t === 'array') { try { return JSON.parse(s); } catch(e) { return []; } }
        if (t === 'object') { try { return JSON.parse(s); } catch(e) { return {}; } }
        return s;
      }

      if (t === 'number' || t === 'float') return 42;
      if (t === 'integer' || t === 'int') return 10;
      if (t === 'boolean' || t === 'bool') return true;
      if (t === 'array') return [];
      if (t === 'object') return {};
      if (t === 'email') return `contact@${keyName || 'example'}.com`;
      if (t === 'date' || t === 'datetime') return new Date().toISOString().split('T')[0];
      if (t === 'uuid') return 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
      if (t === 'any') return 'exemple';
      return `valeur_${keyName.split('.').pop()}`;
    };

    rows.forEach(r => {
      const key = (r.key || r.name || '').trim();
      if (!key) return;

      const rawType = r.type || 'string';
      const customRef = r.custom_type || r.custom_type_ref;
      const val = generateSingleValue(rawType, r.default, customRef, key, 0);

      setNested(result, key, val);
    });

    return result;
  }

  getEffectiveTestPayload() {
    if (this.simulationInitialPayload && Object.keys(this.simulationInitialPayload).length > 0) {
      return this.simulationInitialPayload;
    }
    const triggerNode = this.nodes.find(n => n.type && (n.type.includes('trigger') || n.type.startsWith('core.trigger')));
    if (triggerNode && triggerNode.configuration) {
      if (triggerNode.configuration.test_payload) {
        let tp = triggerNode.configuration.test_payload;
        if (typeof tp === 'string') {
          try { tp = JSON.parse(tp); } catch (e) { tp = null; }
        }
        if (tp && typeof tp === 'object' && Object.keys(tp).length > 0) return tp;
      }
      if (Array.isArray(triggerNode.configuration.payload_schema) && triggerNode.configuration.payload_schema.length > 0) {
        const fromSchema = this.generateTestPayloadFromSchema(triggerNode.configuration.payload_schema);
        if (Object.keys(fromSchema).length > 0) return fromSchema;
      }
    }
    return {};
  }

  // -------------------------------------------------------------
  // 10. Popover d'Autocomplétion & Variable Picker ({})
  // -------------------------------------------------------------
  openVariablePicker(anchorEl, targetInputId) {
    this.closeVariablePicker();

    const vars = this.getAvailableVariables();
    const popover = document.createElement('div');
    popover.id = 'activeVariablePickerPopover';
    popover.className = 'variable-picker-popover';

    popover.innerHTML = `
      <div class="variable-picker-header">
        <div class="input-group input-group-sm mb-1">
          <span class="input-group-text bg-white"><img src="/static_base_icons?name=search&size=11" style="vertical-align:-2px"></span>
          <input type="text" id="varPickerSearchInput" class="form-control form-control-sm" placeholder="Rechercher une variable..." autofocus>
        </div>
        <div class="variable-picker-categories" id="varPickerCategories">
          <button type="button" class="variable-picker-cat-btn is-active" data-cat="all">Tous</button>
          <button type="button" class="variable-picker-cat-btn" data-cat="node_io">Nœud E/S</button>
          <button type="button" class="variable-picker-cat-btn" data-cat="payload">Payload</button>
          <button type="button" class="variable-picker-cat-btn" data-cat="steps">Étapes</button>
          <button type="button" class="variable-picker-cat-btn" data-cat="context">Contexte</button>
        </div>
      </div>
      <div class="variable-picker-list" id="varPickerList"></div>
    `;

    document.body.appendChild(popover);

    let activeCat = 'all';

    const renderList = (filter = '') => {
      const listEl = popover.querySelector('#varPickerList');
      if (!listEl) return;
      const q = filter.toLowerCase().trim();
      const filtered = vars.filter(v => {
        const matchesQ = !q || v.path.toLowerCase().includes(q) || (v.name && v.name.toLowerCase().includes(q)) || (v.source && v.source.toLowerCase().includes(q)) || (v.node_name && v.node_name.toLowerCase().includes(q));
        const matchesCat = activeCat === 'all' || v.category === activeCat;
        return matchesQ && matchesCat;
      });

      if (filtered.length === 0) {
        listEl.innerHTML = `<div class="p-3 text-center text-muted x-small">Aucune variable correspondante.</div>`;
        return;
      }

      listEl.innerHTML = filtered.map(v => {
        const sourceLabel = v.node_name ? `${v.node_name} (${v.source || ''})` : (v.source || '');
        const typeCls = `type-${(v.type || 'other').toLowerCase()}`;
        return `
          <div class="variable-picker-item" data-path="${this.escapeHtml(v.path)}">
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 68%;">
              <span class="variable-picker-path">{${this.escapeHtml(v.path)}}</span>
              <span class="n8n-type-badge ${typeCls} ms-1">${this.escapeHtml(v.type || 'var')}</span>
              ${sourceLabel ? `<small class="text-muted ms-1" style="font-size: 10px;">(${this.escapeHtml(sourceLabel)})</small>` : ''}
            </div>
            <span class="variable-picker-preview" title="${this.escapeHtml(String(v.preview ?? ''))}">${this.escapeHtml(String(v.preview ?? ''))}</span>
          </div>
        `;
      }).join('');

      listEl.querySelectorAll('.variable-picker-item').forEach(itemEl => {
        itemEl.addEventListener('click', () => {
          const path = itemEl.dataset.path;
          this.insertVariableIntoInput(targetInputId, path);
          this.closeVariablePicker();
        });
      });
    };

    renderList();

    const searchInput = popover.querySelector('#varPickerSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => renderList(e.target.value));
      setTimeout(() => searchInput.focus(), 50);
    }

    // Gestion du clic sur les filtres de catégories
    popover.querySelectorAll('.variable-picker-cat-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        popover.querySelectorAll('.variable-picker-cat-btn').forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        activeCat = btn.dataset.cat;
        renderList(searchInput ? searchInput.value : '');
      });
    });

    const rect = anchorEl.getBoundingClientRect();
    let left = rect.left - 260;
    if (left < 10) left = rect.left;
    let top = rect.bottom + 4;
    if (top + 280 > window.innerHeight) {
      top = rect.top - 290;
    }
    popover.style.left = `${Math.max(10, Math.round(left))}px`;
    popover.style.top = `${Math.max(10, Math.round(top))}px`;

    const outsideListener = (e) => {
      if (!popover.contains(e.target) && e.target !== anchorEl && !anchorEl.contains(e.target)) {
        this.closeVariablePicker();
        document.removeEventListener('mousedown', outsideListener);
      }
    };
    setTimeout(() => {
      document.addEventListener('mousedown', outsideListener);
    }, 10);
  }

  closeVariablePicker() {
    const existing = document.getElementById('activeVariablePickerPopover');
    if (existing) existing.remove();
  }

  insertVariableIntoInput(targetInputId, varPath) {
    const input = document.getElementById(targetInputId);
    if (!input) return;
    const token = `{${varPath}}`;
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const val = input.value || '';
    if (start !== undefined && end !== undefined) {
      input.value = val.substring(0, start) + token + val.substring(end);
      input.selectionStart = input.selectionEnd = start + token.length;
    } else {
      input.value = val + token;
    }
    input.focus();
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  // -------------------------------------------------------------
  // 11. Console de Débogage & Interpréteur Temps Réel
  // -------------------------------------------------------------
  setupDebugConsole() {
    const consoleEl = document.getElementById('canvasDebugConsole');
    if (!consoleEl) return;
    this.renderDebugVariablesTable();
  }

  toggleDebugConsole(forceOpen = null) {
    const consoleEl = document.getElementById('canvasDebugConsole');
    const toggleIcon = document.getElementById('debugConsoleToggleIcon');
    if (!consoleEl) return;

    if (forceOpen === true) {
      consoleEl.classList.remove('is-collapsed');
    } else if (forceOpen === false) {
      consoleEl.classList.add('is-collapsed');
    } else {
      consoleEl.classList.toggle('is-collapsed');
    }

    const isCollapsed = consoleEl.classList.contains('is-collapsed');
    if (toggleIcon) {
      if (toggleIcon.tagName === 'IMG') {
        toggleIcon.src = isCollapsed ? '/static_base_icons?name=expand_less&size=16' : '/static_base_icons?name=expand_more&size=16';
      } else {
        toggleIcon.className = isCollapsed ? 'fas fa-chevron-up' : 'fas fa-chevron-down';
      }
    }
  }

  switchDebugTab(tabName) {
    document.querySelectorAll('.canvas-debug-tab-btn').forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.tab === tabName);
    });
    document.querySelectorAll('.canvas-debug-tab-pane').forEach(pane => {
      pane.classList.remove('is-active');
    });

    const targetPane = document.getElementById(`debugPane_${tabName}`);
    if (targetPane) targetPane.classList.add('is-active');

    this.toggleDebugConsole(true);
  }

  async runGraphSimulation() {
    this.toggleDebugConsole(true);
    this.switchDebugTab('stream');

    const streamEl = document.getElementById('debugStreamOutput');
    if (streamEl) {
      streamEl.innerHTML = `
        <div class="debug-stream-line is-info">[${new Date().toLocaleTimeString()}] Démarrage de la simulation du graphe en mémoire...</div>
        <div class="debug-stream-line is-info">Nœuds : ${this.nodes.length} | Liaisons : ${this.connections.length}</div>
      `;
    }

    try {
      const resp = await fetch('/api/melodi_automation/workflows/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: this.nodes,
          connections: this.connections,
          initial_payload: this.getEffectiveTestPayload(),
          custom_types: this.customTypes || [],
        }),
      });

      const res = await resp.json();
      if (!resp.ok || res.status === 'error') {
        throw new Error(res.message || "Échec de la simulation");
      }

      this.simulationResult = res;

      if (streamEl) {
        let streamHtml = `<div class="debug-stream-line is-info">[${new Date().toLocaleTimeString()}] Simulation terminée avec succès (${res.duration_ms}ms)</div>`;
        if (Array.isArray(res.timeline)) {
          res.timeline.forEach((item, idx) => {
            const isOk = item.status === 'success';
            const icon = isOk ? '✓' : '✗';
            const colorClass = isOk ? 'is-success' : 'is-error';
            streamHtml += `
              <div class="debug-stream-line ${colorClass}">
                ${idx + 1}. [${item.duration_ms}ms] ${icon} ${this.escapeHtml(item.node_name)} (${item.node_type})
                ${item.error ? `<br>&nbsp;&nbsp;&nbsp;↳ Erreur : ${this.escapeHtml(item.error)}` : ''}
                ${item.active_ports ? `<br>&nbsp;&nbsp;&nbsp;↳ Ports activés : [${item.active_ports.join(', ')}]` : ''}
              </div>
            `;
          });
        }
        if (res.error) {
          streamHtml += `<div class="debug-stream-line is-error">Arrêt sur erreur : ${this.escapeHtml(res.error)}</div>`;
        } else {
          streamHtml += `<div class="debug-stream-line is-success">Fin du parcours du graphe : flux complété.</div>`;
        }
        streamEl.innerHTML = streamHtml;
        streamEl.scrollTop = streamEl.scrollHeight;
      }

      this.renderSimulationBadges();
      this.renderDebugVariablesTable();

      if (this.selectedNodeId) {
        this.inspectNodeInConsole(this.selectedNodeId);
      }
    } catch (e) {
      if (streamEl) {
        streamEl.innerHTML += `<div class="debug-stream-line is-error">[Erreur Réseau / Moteur] ${this.escapeHtml(e.message)}</div>`;
      }
    }
  }

  toggleDebugIoView(mode) {
    this.debugIoViewMode = mode;
    const btnStruct = document.getElementById('btnDebugViewStructured');
    const btnJson = document.getElementById('btnDebugViewJson');
    const gridStruct = document.getElementById('debugIoGridStructured');
    const gridJson = document.getElementById('debugIoGridJson');
    if (btnStruct) btnStruct.classList.toggle('active', mode === 'structured');
    if (btnJson) btnJson.classList.toggle('active', mode === 'json');
    if (gridStruct) gridStruct.classList.toggle('d-none', mode !== 'structured');
    if (gridJson) gridJson.classList.toggle('d-none', mode !== 'json');
  }

  switchDebugSubtab(subtabName) {
    this.currentDebugSubtab = subtabName;
    document.querySelectorAll('.debug-subnav-btn').forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.subtab === subtabName);
    });
    document.querySelectorAll('.debug-subpane').forEach(pane => {
      pane.classList.remove('is-active');
    });
    const target = document.getElementById(`debugSubpane_${subtabName}`);
    if (target) target.classList.add('is-active');
  }

  setDebugVariableCategory(cat) {
    this.debugVarCategory = cat;
    document.querySelectorAll('#debugVarCategoryPills .debug-category-pill').forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.cat === cat);
    });
    const filterInput = document.getElementById('debugVarFilterInput');
    this.renderDebugVariablesTable(filterInput ? filterInput.value : '');
  }

  renderVariablesCardList(containerEl, varsList, emptyMsg = "Aucune variable disponible.") {
    if (!containerEl) return;
    if (!Array.isArray(varsList) || varsList.length === 0) {
      containerEl.innerHTML = `<div class="text-center text-muted x-small py-3">${this.escapeHtml(emptyMsg)}</div>`;
      return;
    }
    containerEl.innerHTML = varsList.map(v => {
      const typeCls = `type-${(v.type || 'other').toLowerCase()}`;
      return `
      <div class="debug-var-card">
        <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 60%;">
          <span class="debug-var-path">{${this.escapeHtml(v.path)}}</span>
          <span class="n8n-type-badge ${typeCls} ms-1">${this.escapeHtml(v.type || 'var')}</span>
          ${v.source ? `<small class="text-muted ms-1" style="font-size: 10px;">(${this.escapeHtml(v.source)})</small>` : ''}
        </div>
        <div class="d-flex align-items-center gap-2">
          <span class="debug-var-val" title="${this.escapeHtml(String(v.preview ?? ''))}">${this.escapeHtml(String(v.preview ?? ''))}</span>
          <button type="button" class="debug-copy-btn" onclick="navigator.clipboard.writeText('{${this.escapeHtml(v.path)}}'); alert('Copié : {${this.escapeHtml(v.path)}}');" title="Copier la référence">
            <img src="/static_base_icons?name=content_copy&size=11" style="vertical-align:-1px">
          </button>
        </div>
      </div>
    `;
    }).join('');
  }

  inspectNodeInConsole(nodeId) {
    const inputPre = document.getElementById('debugIoInputPre');
    const outputPre = document.getElementById('debugIoOutputPre');
    const inputTree = document.getElementById('debugIoInputVarsTree');
    const outputTree = document.getElementById('debugIoOutputVarsTree');
    const targetNodeLabel = document.getElementById('debugIoSelectedNodeName');
    const statusBadge = document.getElementById('debugIoStatusBadge');

    const payloadTree = document.getElementById('debugPayloadVarsTree');
    const payloadPre = document.getElementById('debugPayloadRawPre');
    const stepsAccordion = document.getElementById('debugStepsAccordion');
    const stepsCountBadge = document.getElementById('debugStepsCountBadge');
    const contextTree = document.getElementById('debugContextVarsTree');
    const contextPre = document.getElementById('debugContextRawPre');

    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) {
      if (targetNodeLabel) targetNodeLabel.innerText = 'Aucun nœud sélectionné';
      if (statusBadge) statusBadge.innerHTML = '';
      if (inputPre) inputPre.innerText = 'Sélectionnez un nœud sur le canvas pour visualiser ses entrées.';
      if (outputPre) outputPre.innerText = 'Sélectionnez un nœud sur le canvas pour visualiser ses sorties.';
      if (inputTree) inputTree.innerHTML = '<div class="text-center text-muted x-small py-3">Sélectionnez un nœud.</div>';
      if (outputTree) outputTree.innerHTML = '<div class="text-center text-muted x-small py-3">Sélectionnez un nœud.</div>';
      return;
    }

    if (targetNodeLabel) {
      targetNodeLabel.innerText = `${node.name || node.type} (${node.id})`;
    }

    const trace = this.simulationResult && this.simulationResult.nodes_trace ? this.simulationResult.nodes_trace[nodeId] : null;

    // Mise à jour du badge de statut
    if (statusBadge) {
      if (!trace) {
        statusBadge.innerHTML = '<span class="badge bg-warning-subtle text-warning border">Non simulé</span>';
      } else if (trace.status === 'success') {
        if (trace.active_ports && trace.active_ports.includes('error')) {
          statusBadge.innerHTML = `<span class="badge bg-danger-subtle text-danger border"><img src="/static_base_icons?name=warning&size=11" class="me-1" style="vertical-align:-1px">Dérouté vers Port Erreur (${trace.duration_ms}ms)</span>`;
        } else {
          statusBadge.innerHTML = `<span class="badge bg-success-subtle text-success border"><img src="/static_base_icons?name=check&size=11" class="me-1" style="vertical-align:-1px">Succès (${trace.duration_ms}ms)</span>`;
        }
      } else if (trace.status === 'error') {
        statusBadge.innerHTML = `<span class="badge bg-danger-subtle text-danger border"><img src="/static_base_icons?name=close&size=11" class="me-1" style="vertical-align:-1px">Erreur (${trace.duration_ms}ms)</span>`;
      } else {
        statusBadge.innerHTML = '<span class="badge bg-secondary-subtle text-secondary border">- Non exécuté</span>';
      }
    }

    // 1. Volet E/S Nœud Actuel (Input / Output)
    if (!trace) {
      const configJson = JSON.stringify(node.configuration || {}, null, 2);
      if (inputPre) inputPre.innerText = `Configuration actuelle du nœud :\n${configJson}\n\n(Lancez une simulation pour voir les données réelles reçues en entrée).`;
      if (outputPre) outputPre.innerText = `En attente de simulation.\nCliquez sur "Simuler le Graphe" dans la console pour exécuter ce nœud et inspecter ses sorties.`;
      if (inputTree) inputTree.innerHTML = '<div class="text-center text-muted x-small py-3">Lancez une simulation pour voir les entrées reçues.</div>';
      if (outputTree) outputTree.innerHTML = '<div class="text-center text-muted x-small py-3">Lancez une simulation pour voir les sorties produites.</div>';
    } else {
      if (inputPre) inputPre.innerText = JSON.stringify(trace.input_data || {}, null, 2);
      if (outputPre) {
        outputPre.innerText = trace.error ? `Erreur lors de l'exécution :\n${trace.error}` : JSON.stringify(trace.output_data !== undefined ? trace.output_data : {}, null, 2);
      }
      this.renderVariablesCardList(inputTree, trace.input_variables, "Aucune variable d'entrée pour ce nœud.");
      this.renderVariablesCardList(outputTree, trace.output_variables, "Aucune variable produite en sortie.");
    }

    // 2. Volet Payload Déclencheur
    const payloadData = (trace && trace.payload) || this.getEffectiveTestPayload();
    if (payloadPre) payloadPre.innerText = JSON.stringify(payloadData, null, 2);
    if (payloadTree) {
      const payloadVars = [];
      const extractPayload = (obj, prefix) => {
        if (typeof obj === 'object' && obj !== null) {
          if (Array.isArray(obj)) {
            payloadVars.push({ path: `payload.${prefix}`, name: prefix, type: 'array', preview: `[${obj.length} éléments]`, source: 'Payload Déclencheur' });
          } else {
            Object.entries(obj).forEach(([k, v]) => {
              const p = prefix ? `${prefix}.${k}` : k;
              if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
                extractPayload(v, p);
              } else {
                payloadVars.push({
                  path: `payload.${p}`,
                  name: k,
                  type: Array.isArray(v) ? 'array' : typeof v,
                  preview: Array.isArray(v) ? `[${v.length} éléments]` : String(v),
                  source: 'Payload Déclencheur'
                });
              }
            });
          }
        }
      };
      extractPayload(payloadData, '');
      this.renderVariablesCardList(payloadTree, payloadVars, "Aucun payload déclencheur disponible.");
    }

    // 3. Volet Étapes Précédentes (Steps)
    const precedingMap = (trace && trace.preceding_steps) || {};
    const stepKeys = Object.keys(precedingMap);
    if (stepsCountBadge) stepsCountBadge.innerText = String(stepKeys.length);

    if (stepsAccordion) {
      if (stepKeys.length === 0) {
        stepsAccordion.innerHTML = '<div class="text-center text-muted x-small py-3">Aucune étape précédente enregistrée avant ce nœud.</div>';
      } else {
        stepsAccordion.innerHTML = stepKeys.map(sId => {
          const s = precedingMap[sId];
          const outData = s.output;
          const outJson = JSON.stringify(outData, null, 2);

          const sVars = [];
          const extractStepVars = (obj, prefix) => {
            if (typeof obj === 'object' && obj !== null) {
              if (!Array.isArray(obj)) {
                Object.entries(obj).forEach(([k, v]) => {
                  const p = prefix ? `${prefix}.${k}` : k;
                  if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
                    extractStepVars(v, p);
                  } else {
                    sVars.push({
                      path: `steps.${sId}.${p}`,
                      name: k,
                      type: Array.isArray(v) ? 'array' : typeof v,
                      preview: Array.isArray(v) ? `[${v.length} éléments]` : String(v),
                      source: s.name,
                    });
                  }
                });
              }
            }
          };
          extractStepVars(outData, '');

          return `
            <div class="debug-step-item">
              <div class="debug-step-header" onclick="this.nextElementSibling.classList.toggle('d-none')">
                <div class="d-flex align-items-center gap-2">
                  <img src="/static_base_icons?name=layers&size=13" style="vertical-align:-2px">
                  <span class="fw-bold">${this.escapeHtml(s.name)}</span>
                  <code class="text-muted" style="font-size:10px;">(steps.${this.escapeHtml(sId)})</code>
                  <span class="badge bg-light text-dark border" style="font-size:9px;">${this.escapeHtml(s.type)}</span>
                </div>
                <div class="d-flex align-items-center gap-2">
                  <small class="text-muted" style="font-size:10px;">${sVars.length} variable(s)</small>
                  <img src="/static_base_icons?name=expand_more&size=12" style="vertical-align:-2px">
                </div>
              </div>
              <div class="debug-step-body d-none">
                <div class="d-flex align-items-center justify-content-between mb-2">
                  <span class="x-small text-muted fw-bold">Variables produites par cette étape :</span>
                  <button type="button" class="btn btn-link p-0 text-decoration-none x-small" onclick="navigator.clipboard.writeText('${this.escapeHtml(outJson).replace(/'/g, "\\'")}'); alert('Sortie copiée');">Copier JSON</button>
                </div>
                <div class="debug-var-tree mb-2">
                  ${sVars.length > 0 ? sVars.map(sv => {
                    const typeCls = `type-${(sv.type || 'other').toLowerCase()}`;
                    return `
                    <div class="debug-var-card">
                      <div>
                        <span class="debug-var-path">{${this.escapeHtml(sv.path)}}</span>
                        <span class="n8n-type-badge ${typeCls} ms-1">${this.escapeHtml(sv.type)}</span>
                      </div>
                      <div class="d-flex align-items-center gap-2">
                        <span class="debug-var-val" title="${this.escapeHtml(String(sv.preview))}">${this.escapeHtml(String(sv.preview))}</span>
                        <button type="button" class="debug-copy-btn" onclick="navigator.clipboard.writeText('{${this.escapeHtml(sv.path)}}'); alert('Copié : {${this.escapeHtml(sv.path)}}');" title="Copier">
                          <img src="/static_base_icons?name=content_copy&size=11" style="vertical-align:-1px">
                        </button>
                      </div>
                    </div>
                  `;
                  }).join('') : '<div class="text-muted x-small py-1">Sortie non structurée ou vide.</div>'}
                </div>
                <pre class="debug-io-pre mt-1" style="max-height: 80px;">${this.escapeHtml(outJson)}</pre>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // 4. Volet Contexte Global
    const ctxData = (trace && trace.context_snapshot) || {};
    if (contextPre) contextPre.innerText = JSON.stringify(ctxData, null, 2);
    if (contextTree) {
      const ctxVars = [
        { path: 'context.timestamp', name: 'timestamp', type: 'number', preview: String(Date.now()), source: 'Système' },
        { path: 'context.execution_id', name: 'execution_id', type: 'string', preview: 'sim_dry_run', source: 'Système' },
      ];
      if (ctxData.variables && typeof ctxData.variables === 'object') {
        Object.entries(ctxData.variables).forEach(([vk, vv]) => {
          ctxVars.push({
            path: `context.variables.${vk}`,
            name: vk,
            type: typeof vv,
            preview: String(vv),
            source: 'Variables Contexte',
          });
        });
      }
      this.renderVariablesCardList(contextTree, ctxVars, "Aucune variable de contexte disponible.");
    }
  }

  renderSimulationBadges() {
    if (!this.simulationResult || !this.simulationResult.nodes_trace) return;
    this.nodes.forEach(n => {
      const el = document.getElementById(`nodeEl_${n.id}`);
      if (!el) return;
      let badge = el.querySelector('.node-sim-badge');
      const trace = this.simulationResult.nodes_trace[n.id];
      if (trace) {
        if (!badge) {
          badge = document.createElement('div');
          el.appendChild(badge);
        }
        if (trace.status === 'success') {
          if (trace.active_ports && trace.active_ports.includes('error')) {
            badge.className = 'node-sim-badge is-error';
            badge.title = `Dérouté vers Port Erreur (${trace.duration_ms}ms)`;
            badge.innerHTML = '<img src="/static_base_icons?name=warning&fill=white&size=10">';
          } else {
            badge.className = 'node-sim-badge is-success';
            badge.title = `Exécuté avec succès (${trace.duration_ms}ms)`;
            badge.innerHTML = '<img src="/static_base_icons?name=check&fill=white&size=10">';
          }
        } else if (trace.status === 'error') {
          badge.className = 'node-sim-badge is-error';
          badge.title = `Erreur : ${trace.error || 'Échec'}`;
          badge.innerHTML = '<img src="/static_base_icons?name=close&fill=white&size=10">';
        } else {
          badge.className = 'node-sim-badge is-skipped';
          badge.title = 'Branche ignorée';
          badge.innerHTML = '<span style="font-weight:bold;line-height:1;">-</span>';
        }
      } else if (badge) {
        badge.className = 'node-sim-badge is-skipped';
        badge.title = 'Non atteint lors de la simulation';
        badge.innerHTML = '<span style="font-weight:bold;line-height:1;">-</span>';
      }
    });
  }

  getAvailableVariables() {
    const list = [];
    const seen = new Set();

    // 1. Si on a un nœud sélectionné et une trace pour ce nœud, injecter ses input_variables et output_variables
    if (this.selectedNodeId && this.simulationResult && this.simulationResult.nodes_trace) {
      const trace = this.simulationResult.nodes_trace[this.selectedNodeId];
      if (trace) {
        if (Array.isArray(trace.input_variables)) {
          trace.input_variables.forEach(v => {
            if (!seen.has(v.path)) {
              seen.add(v.path);
              list.push({ ...v, category: 'node_io' });
            }
          });
        }
        if (Array.isArray(trace.output_variables)) {
          trace.output_variables.forEach(v => {
            if (!seen.has(v.path)) {
              seen.add(v.path);
              list.push({ ...v, category: 'steps' });
            }
          });
        }
      }
    }

    // 2. Si la simulation a retourné available_variables, les ajouter
    if (this.simulationResult && Array.isArray(this.simulationResult.available_variables) && this.simulationResult.available_variables.length > 0) {
      this.simulationResult.available_variables.forEach(v => {
        if (!seen.has(v.path)) {
          seen.add(v.path);
          list.push(v);
        }
      });
      return list;
    }

    // 3. Extraction statique si simulation non disponible
    const extract = (obj, prefix, source, category = 'payload') => {
      if (typeof obj === 'object' && obj !== null) {
        if (Array.isArray(obj)) {
          if (!seen.has(prefix)) {
            seen.add(prefix);
            list.push({ path: prefix, name: prefix.split('.').pop(), type: 'array', preview: `[${obj.length} éléments]`, source, category });
          }
          if (obj.length > 0 && typeof obj[0] === 'object') {
            extract(obj[0], `${prefix}[0]`, source, category);
          }
        } else {
          Object.entries(obj).forEach(([k, v]) => {
            const p = prefix ? `${prefix}.${k}` : k;
            if (typeof v === 'object' && v !== null) {
              extract(v, p, source, category);
            } else {
              if (!seen.has(p)) {
                seen.add(p);
                list.push({ path: p, name: k, type: typeof v, preview: String(v), source, category });
              }
            }
          });
        }
      }
    };

    const effPayload = this.getEffectiveTestPayload();
    if (effPayload && Object.keys(effPayload).length > 0) {
      extract(effPayload, 'payload', 'Déclencheur', 'payload');
      extract(effPayload, '', 'Déclencheur', 'payload');
    }

    this.nodes.forEach(n => {
      const stepPath = `steps.${n.id}`;
      if (!seen.has(stepPath)) {
        seen.add(stepPath);
        list.push({ path: stepPath, name: n.name || n.id, type: 'object', preview: `{Données ${n.name || n.type}}`, source: n.name || n.id, category: 'steps', node_id: n.id, node_name: n.name });
      }
      if (n.type === 'core.set_fields' && Array.isArray(n.configuration?.fields)) {
        n.configuration.fields.forEach(f => {
          if (f.key) {
            const directP = f.key;
            const stepP = `steps.${n.id}.${f.key}`;
            if (!seen.has(directP)) {
              seen.add(directP);
              list.push({ path: directP, name: f.key, type: f.type || 'string', preview: f.value || '', source: n.name || 'Set Fields', category: 'steps', node_id: n.id, node_name: n.name });
            }
            if (!seen.has(stepP)) {
              seen.add(stepP);
              list.push({ path: stepP, name: f.key, type: f.type || 'string', preview: f.value || '', source: n.name || 'Set Fields', category: 'steps', node_id: n.id, node_name: n.name });
            }
          }
        });
      }
    });

    list.push({ path: 'context.timestamp', name: 'timestamp', type: 'number', preview: String(Date.now()), source: 'Contexte Global', category: 'context' });

    return list;
  }

  renderDebugVariablesTable(filter = '') {
    const tbody = document.getElementById('debugVariablesTableBody');
    if (!tbody) return;

    const vars = this.getAvailableVariables();
    const q = filter.toLowerCase().trim();
    const cat = this.debugVarCategory || 'all';

    const filtered = vars.filter(v => {
      const matchesQ = !q || v.path.toLowerCase().includes(q) || (v.name && v.name.toLowerCase().includes(q)) || (v.source && v.source.toLowerCase().includes(q)) || (v.node_name && v.node_name.toLowerCase().includes(q));
      const matchesCat = cat === 'all' || v.category === cat;
      return matchesQ && matchesCat;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-3">Aucune variable trouvée.</td></tr>`;
      return;
    }

    const getCatBadge = (c) => {
      if (c === 'node_io') return '<span class="badge bg-success-subtle text-success border me-1" style="font-size:9px;">Nœud E/S</span>';
      if (c === 'payload') return '<span class="badge bg-warning-subtle text-warning border me-1" style="font-size:9px;">Payload</span>';
      if (c === 'steps') return '<span class="badge bg-primary-subtle text-primary border me-1" style="font-size:9px;">Step</span>';
      if (c === 'context') return '<span class="badge bg-info-subtle text-info border me-1" style="font-size:9px;">Contexte</span>';
      return '<span class="badge bg-secondary-subtle text-secondary border me-1" style="font-size:9px;">Autre</span>';
    };

    tbody.innerHTML = filtered.map(v => {
      const sourceLabel = v.node_name ? `${v.node_name} (${v.source || ''})` : (v.source || '');
      return `
        <tr>
          <td>
            <div class="d-flex align-items-center">
              ${getCatBadge(v.category)}
              <code class="fw-bold">{${this.escapeHtml(v.path)}}</code>
            </div>
          </td>
          <td><span class="badge bg-light text-dark border">${this.escapeHtml(v.type || 'any')}</span></td>
          <td class="text-muted"><small>${this.escapeHtml(sourceLabel)}</small></td>
          <td><span class="text-truncate d-inline-block font-monospace" style="max-width: 250px;">${this.escapeHtml(String(v.preview ?? ''))}</span></td>
          <td class="text-end">
            <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2" style="font-size: 10px;" onclick="navigator.clipboard.writeText('{${this.escapeHtml(v.path)}}'); alert('Copié : {${this.escapeHtml(v.path)}}');" title="Copier la variable">
              Copier
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  filterDebugVariables(query) {
    this.renderDebugVariablesTable(query);
  }

  saveSimulationPayloadFromModal() {
    const textarea = document.getElementById('simulationModalPayloadTextarea');
    if (!textarea) return;
    try {
      const parsed = JSON.parse(textarea.value || '{}');
      this.simulationInitialPayload = parsed;
      // Synchroniser également sur le déclencheur
      const triggerNode = this.nodes.find(n => n.type && (n.type.includes('trigger') || n.type.startsWith('core.trigger')));
      if (triggerNode) {
        if (!triggerNode.configuration) triggerNode.configuration = {};
        triggerNode.configuration.test_payload = parsed;
        this.updateSerializedInputs();
        if (this.selectedNodeId === triggerNode.id) {
          this.renderInspector();
        }
      }
      this.runGraphSimulation();
      const modalEl = document.getElementById('simulationPayloadModal');
      if (modalEl && typeof bootstrap !== 'undefined') {
        bootstrap.Modal.getOrCreateInstance(modalEl).hide();
      }
    } catch (e) {
      alert("Erreur de format JSON dans le payload : " + e.message);
    }
  }

  fillSimulationModalFromTriggerSchema() {
    const triggerNode = this.nodes.find(n => n.type && (n.type.includes('trigger') || n.type.startsWith('core.trigger')));
    const schemaDef = triggerNode?.configuration?.payload_schema || [];
    const generated = this.generateTestPayloadFromSchema(schemaDef);
    const textarea = document.getElementById('simulationModalPayloadTextarea');
    if (textarea) {
      textarea.value = JSON.stringify(generated, null, 2);
    }
  }

  prepareSimulationModal() {
    const textarea = document.getElementById('simulationModalPayloadTextarea');
    if (!textarea) return;
    const currentPayload = this.getEffectiveTestPayload();
    textarea.value = JSON.stringify(currentPayload, null, 2);
  }

  // -------------------------------------------------------------
  // 12. Gestionnaire Visuel de Types Personnalisés (Structs)
  // -------------------------------------------------------------
  openCustomTypesModal(typeIdToSelect = null) {
    if (!Array.isArray(this.customTypes)) {
      this.customTypes = [];
    }
    if (typeIdToSelect) {
      this.selectedCustomTypeId = typeIdToSelect;
    } else if (this.customTypes.length > 0 && !this.selectedCustomTypeId) {
      this.selectedCustomTypeId = this.customTypes[0].id;
    }
    this.renderCustomTypesModal();
    const modalEl = document.getElementById('customTypesModal');
    if (modalEl) {
      if (!modalEl._hasSaveOnCloseBound) {
        modalEl.addEventListener('hidden.bs.modal', () => {
          this.saveCustomTypesFromModal();
        });
        modalEl._hasSaveOnCloseBound = true;
      }
      if (typeof bootstrap !== 'undefined') {
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
      }
    }
  }

  renderCustomTypesModal() {
    const listContainer = document.getElementById('customTypesListContainer');
    const editorContainer = document.getElementById('customTypeEditorContainer');
    if (!listContainer || !editorContainer) return;

    // A. Rendu de la barre latérale des types
    if (this.customTypes.length === 0) {
      listContainer.innerHTML = `
        <div class="p-3 text-center text-muted x-small">
          Aucun type personnalisé.<br>Cliquez sur "+ Nouveau" pour démarrer.
        </div>
      `;
    } else {
      listContainer.innerHTML = this.customTypes.map(ct => {
        const isSel = ct.id === this.selectedCustomTypeId;
        const fieldsCount = Array.isArray(ct.fields) ? ct.fields.length : 0;
        return `
          <button type="button" class="list-group-item list-group-item-action py-2 px-3 d-flex align-items-center justify-content-between ${isSel ? 'active' : ''}" onclick="canvas.selectCustomType('${this.escapeHtml(ct.id)}')">
            <div class="overflow-hidden me-2">
              <div class="fw-bold x-small text-truncate">📦 ${this.escapeHtml(ct.name || 'Sans nom')}</div>
              <small class="${isSel ? 'text-white-50' : 'text-muted'}" style="font-size: 10px;">${this.escapeHtml(ct.label || ct.name || '')} &bull; ${fieldsCount} champ(s)</small>
            </div>
            <span class="badge ${isSel ? 'bg-light text-dark' : 'bg-secondary-subtle text-secondary'}" style="font-size: 9px;">Struct</span>
          </button>
        `;
      }).join('');
    }

    // B. Rendu de l'éditeur pour le type sélectionné
    const activeType = this.customTypes.find(ct => ct.id === this.selectedCustomTypeId);
    if (!activeType) {
      editorContainer.innerHTML = `
        <div class="text-center text-muted py-5">
          <img src="/static_base_icons?name=category&size=36" class="mb-2 opacity-50">
          <p class="small mb-0">Sélectionnez un type dans la liste de gauche ou cliquez sur <strong>+ Nouveau</strong>.</p>
        </div>
      `;
      return;
    }

    const fields = Array.isArray(activeType.fields) ? activeType.fields : [];
    const otherTypes = this.customTypes.filter(ct => ct.id !== activeType.id);

    editorContainer.innerHTML = `
      <div class="custom-type-editor">
        <div class="d-flex align-items-center justify-content-between mb-3 pb-2 border-bottom">
          <h6 class="fw-bold text-dark mb-0 d-flex align-items-center gap-1">
            <img src="/static_base_icons?name=view_in_ar&size=16" style="vertical-align:-2px"> Structure : <code>${this.escapeHtml(activeType.name)}</code>
          </h6>
          <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2 d-flex align-items-center gap-1" style="font-size: 11px;" onclick="canvas.deleteCustomType('${this.escapeHtml(activeType.id)}')">
            <img src="/static_base_icons?name=delete&fill=%23dc3545&size=12" style="vertical-align:-2px"> Supprimer ce type
          </button>
        </div>

        <div class="row g-2 mb-3">
          <div class="col-md-6">
            <label class="form-label x-small fw-semibold text-muted mb-1">Nom technique du type (ex: Address, Customer) *</label>
            <input type="text" class="form-control form-control-sm font-monospace" placeholder="NomSansEspace" value="${this.escapeHtml(activeType.name || '')}" oninput="canvas.updateCustomTypeProp('${activeType.id}', 'name', this.value)">
          </div>
          <div class="col-md-6">
            <label class="form-label x-small fw-semibold text-muted mb-1">Libellé d'affichage (ex: Adresse Postale)</label>
            <input type="text" class="form-control form-control-sm" placeholder="Nom lisible..." value="${this.escapeHtml(activeType.label || '')}" oninput="canvas.updateCustomTypeProp('${activeType.id}', 'label', this.value)">
          </div>
          <div class="col-12">
            <label class="form-label x-small fw-semibold text-muted mb-1">Description (optionnelle)</label>
            <input type="text" class="form-control form-control-sm" placeholder="Description de la structure de données..." value="${this.escapeHtml(activeType.description || '')}" oninput="canvas.updateCustomTypeProp('${activeType.id}', 'description', this.value)">
          </div>
        </div>

        <div class="mb-2 d-flex align-items-center justify-content-between">
          <label class="form-label x-small fw-bold text-uppercase text-muted mb-0">Champs internes de la structure (${fields.length})</label>
          <button type="button" class="btn btn-outline-primary btn-sm py-0 px-2 d-flex align-items-center gap-1" style="font-size: 11px;" onclick="canvas.addCustomTypeField('${activeType.id}')">
            <img src="/static_base_icons?name=add&size=12" style="vertical-align:-2px"> Ajouter un champ
          </button>
        </div>

        <div class="custom-type-fields-table border rounded p-2 bg-light mb-3" style="max-height: 250px; overflow-y: auto;">
          ${fields.length === 0 ? `
            <div class="text-center text-muted x-small py-3">Aucun champ défini dans cette structure. Cliquez sur "+ Ajouter un champ".</div>
          ` : `
            <div class="d-flex gap-1 mb-1 px-1 text-muted x-small fw-semibold" style="font-size: 10px;">
              <div style="flex: 1.2;">Nom du champ (clé)</div>
              <div style="width: 125px;">Type de données</div>
              <div style="flex: 1.0;">Valeur par défaut</div>
              <div style="width: 45px;" class="text-center">Requis</div>
              <div style="width: 26px;"></div>
            </div>
            ${fields.map((f, fIdx) => {
              const fType = String(f.type || 'string');
              const fCustomRef = String(f.custom_type || f.custom_type_ref || (fType.startsWith('custom:') ? fType.split(':')[1] : ''));
              const isCust = fType === 'custom' || fType.startsWith('custom:') || otherTypes.some(ot => ot.name === fType);
              const resolvedType = isCust ? (fCustomRef || fType) : fType;

              return `
                <div class="d-flex align-items-center gap-1 mb-1 p-1 bg-white rounded border">
                  <input type="text" class="form-control form-control-sm font-monospace" style="flex: 1.2; font-size: 11px;" placeholder="clé" value="${this.escapeHtml(f.key || '')}" oninput="canvas.updateCustomTypeFieldProp('${activeType.id}', ${fIdx}, 'key', this.value)">
                  <select class="form-select form-select-sm" style="width: 125px; font-size: 11px;" onchange="canvas.updateCustomTypeFieldType('${activeType.id}', ${fIdx}, this.value)">
                    <optgroup label="Primitifs">
                      <option value="string" ${fType === 'string' ? 'selected' : ''}>Texte (str)</option>
                      <option value="number" ${fType === 'number' ? 'selected' : ''}>Nombre (float)</option>
                      <option value="integer" ${fType === 'integer' || fType === 'int' ? 'selected' : ''}>Entier (int)</option>
                      <option value="boolean" ${fType === 'boolean' || fType === 'bool' ? 'selected' : ''}>Booléen</option>
                      <option value="array" ${fType === 'array' ? 'selected' : ''}>Tableau []</option>
                      <option value="object" ${fType === 'object' ? 'selected' : ''}>Objet {}</option>
                      <option value="any" ${fType === 'any' ? 'selected' : ''}>Tous (any)</option>
                    </optgroup>
                    <optgroup label="Formats">
                      <option value="email" ${fType === 'email' ? 'selected' : ''}>Email</option>
                      <option value="date" ${fType === 'date' || fType === 'datetime' ? 'selected' : ''}>Date</option>
                      <option value="uuid" ${fType === 'uuid' ? 'selected' : ''}>UUID</option>
                    </optgroup>
                    ${otherTypes.length > 0 ? `
                    <optgroup label="Types Imbriqués">
                      ${otherTypes.map(ot => {
                        const isSel = (isCust && resolvedType === ot.name) || fType === ot.name;
                        return `<option value="custom:${this.escapeHtml(ot.name)}" ${isSel ? 'selected' : ''}>📦 ${this.escapeHtml(ot.name)}</option>`;
                      }).join('')}
                    </optgroup>
                    ` : ''}
                  </select>
                  <input type="text" class="form-control form-control-sm font-monospace" style="flex: 1.0; font-size: 11px;" placeholder="défaut..." value="${this.escapeHtml(f.default !== undefined && f.default !== null ? String(f.default) : '')}" oninput="canvas.updateCustomTypeFieldProp('${activeType.id}', ${fIdx}, 'default', this.value)">
                  <div style="width: 45px;" class="text-center form-check form-switch m-0 d-flex justify-content-center">
                    <input class="form-check-input" type="checkbox" ${f.required ? 'checked' : ''} onchange="canvas.updateCustomTypeFieldProp('${activeType.id}', ${fIdx}, 'required', this.checked)">
                  </div>
                  <button type="button" class="btn btn-outline-danger btn-sm p-1" style="width: 26px; height: 28px;" onclick="canvas.removeCustomTypeField('${activeType.id}', ${fIdx})">
                    <img src="/static_base_icons?name=close&fill=%23dc3545&size=12" style="vertical-align:-2px">
                  </button>
                </div>
              `;
            }).join('')}
          `}
        </div>
      </div>
    `;
  }

  createNewCustomType() {
    const id = 'type_' + Math.random().toString(36).substr(2, 8);
    const count = (this.customTypes || []).length + 1;
    const newType = {
      id: id,
      name: `CustomType${count}`,
      label: `Type Personnalisé ${count}`,
      description: '',
      fields: [
        { key: 'id', type: 'string', required: true, default: '' },
        { key: 'name', type: 'string', required: true, default: '' },
      ],
    };
    if (!Array.isArray(this.customTypes)) this.customTypes = [];
    this.customTypes.push(newType);
    this.selectedCustomTypeId = id;
    this.updateSerializedInputs();
    this.renderCustomTypesModal();
  }

  selectCustomType(typeId) {
    this.selectedCustomTypeId = typeId;
    this.renderCustomTypesModal();
  }

  deleteCustomType(typeId) {
    if (!confirm("Voulez-vous vraiment supprimer ce type personnalisé ?")) return;
    this.customTypes = this.customTypes.filter(ct => ct.id !== typeId);
    this.selectedCustomTypeId = this.customTypes.length > 0 ? this.customTypes[0].id : null;
    this.updateSerializedInputs();
    this.renderCustomTypesModal();
    if (this.selectedNodeId) this.renderInspector();
  }

  updateCustomTypeProp(typeId, prop, value) {
    const ct = this.customTypes.find(item => item.id === typeId);
    if (!ct) return;
    ct[prop] = value;
    this.updateSerializedInputs();
    // Rafraîchir seulement le titre dans la barre latérale pour ne pas perdre le focus de l'input
    const btn = document.querySelector(`#customTypesListContainer button.active`);
    if (btn && prop === 'name') {
      const titleEl = btn.querySelector('.fw-bold');
      if (titleEl) titleEl.innerText = `📦 ${value || 'Sans nom'}`;
    }
  }

  addCustomTypeField(typeId) {
    const ct = this.customTypes.find(item => item.id === typeId);
    if (!ct) return;
    if (!Array.isArray(ct.fields)) ct.fields = [];
    ct.fields.push({ key: '', type: 'string', required: true, default: '' });
    this.updateSerializedInputs();
    this.renderCustomTypesModal();
  }

  updateCustomTypeFieldProp(typeId, index, prop, value) {
    const ct = this.customTypes.find(item => item.id === typeId);
    if (!ct || !Array.isArray(ct.fields) || !ct.fields[index]) return;
    ct.fields[index][prop] = value;
    this.updateSerializedInputs();
  }

  updateCustomTypeFieldType(typeId, index, selectedType) {
    const ct = this.customTypes.find(item => item.id === typeId);
    if (!ct || !Array.isArray(ct.fields) || !ct.fields[index]) return;
    const f = ct.fields[index];
    if (selectedType.startsWith('custom:')) {
      const typeName = selectedType.split(':', 2)[1];
      f.type = 'custom';
      f.custom_type = typeName;
      f.custom_type_ref = typeName;
    } else {
      f.type = selectedType;
      delete f.custom_type;
      delete f.custom_type_ref;
    }
    this.updateSerializedInputs();
    this.renderCustomTypesModal();
  }

  removeCustomTypeField(typeId, index) {
    const ct = this.customTypes.find(item => item.id === typeId);
    if (!ct || !Array.isArray(ct.fields)) return;
    ct.fields.splice(index, 1);
    this.updateSerializedInputs();
    this.renderCustomTypesModal();
  }

  saveCustomTypesFromModal() {
    this.updateSerializedInputs();
    if (this.selectedNodeId) {
      this.renderInspector();
    }
  }
}
