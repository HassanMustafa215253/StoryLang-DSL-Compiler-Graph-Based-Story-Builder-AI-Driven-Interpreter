#!/usr/bin/env python3
"""
StoryLang Path Graph Visualizer

Generates an interactive HTML graph of story scene paths.

Usage:
  python story_graph.py my_story.story
  python story_graph.py my_story.story -o output.html
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple

from engine.lexer import Lexer, LexerError
from engine.parser import Parser, ParseError
from engine.ast_nodes import ChoiceNode, IfNode


# ---------------------------------------------------------------------------
# Graph data extraction
# ---------------------------------------------------------------------------

def collect_graph_data(story_path: Path) -> dict:
    source = story_path.read_text(encoding="utf-8")
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()

    scene_names: List[str] = [s.name for s in program.scenes]
    defined: Set[str] = set(scene_names)

    outgoing: Dict[str, int] = {name: 0 for name in scene_names}
    edges: List[dict] = []

    def process_statements(scene_name: str, statements):
      for stmt in statements:
        if isinstance(stmt, ChoiceNode):
          outgoing[scene_name] += 1
          edges.append({
            "id": f"{scene_name}__choice__{stmt.target}__{stmt.line}",
            "from": scene_name,
            "to": stmt.target,
            "label": stmt.label,
            "type": "choice",
          })
        elif isinstance(stmt, IfNode):
          if stmt.then_target:
            outgoing[scene_name] += 1
            edges.append({
              "id": f"{scene_name}__if_true__{stmt.then_target}__{stmt.line}",
              "from": scene_name,
              "to": stmt.then_target,
              "label": "if true",
              "type": "if_true",
            })
          if stmt.else_target:
            outgoing[scene_name] += 1
            edges.append({
              "id": f"{scene_name}__if_false__{stmt.else_target}__{stmt.line}",
              "from": scene_name,
              "to": stmt.else_target,
              "label": "if false",
              "type": "if_false",
            })

          process_statements(scene_name, stmt.then_block)
          process_statements(scene_name, stmt.else_block)

    for scene in program.scenes:
      process_statements(scene.name, scene.statements)

    # Undefined targets get their own "broken" nodes so broken links are visible
    referenced: Set[str] = {e["to"] for e in edges}
    undefined: List[str] = sorted(referenced - defined)

    start = scene_names[0] if scene_names else None
    nodes: List[dict] = []

    for name in scene_names:
        out = outgoing.get(name, 0)
        if name == start:
            node_type = "start"
        elif out == 0:
            node_type = "terminal"
        elif out >= 2:
            node_type = "branch"
        else:
            node_type = "normal"

        # Count statement types for tooltip
        scene_obj = next(s for s in program.scenes if s.name == name)
        stmt_summary = {}
        for stmt in scene_obj.statements:
            t = type(stmt).__name__.replace("Node", "")
            stmt_summary[t] = stmt_summary.get(t, 0) + 1

        nodes.append({
            "id": name,
            "label": name,
            "type": node_type,
            "outgoing": out,
            "statements": stmt_summary,
        })

    for name in undefined:
        nodes.append({
            "id": name,
            "label": name,
            "type": "undefined",
            "outgoing": 0,
            "statements": {},
        })

    return {
        "title": story_path.name,
        "nodes": nodes,
        "edges": edges,
        "scene_count": len(scene_names),
        "edge_count": len(edges),
        "undefined_count": len(undefined),
    }


# ---------------------------------------------------------------------------
# HTML generation  –  NO .format() anywhere near JS code
# ---------------------------------------------------------------------------

def build_html(data: dict) -> str:
    # Safely serialize graph data as JS variable assignments
    data_script = (
        "const GRAPH_DATA = " + json.dumps(data, indent=2) + ";\n"
    )

    # Build HTML by plain concatenation – zero risk of brace collisions
    parts = []
    parts.append("""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>StoryLang Graph &mdash; """ + data["title"] + """</title>
  <script src="https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&family=Crimson+Text:wght@400;600;700&family=IM+Fell+English:ital@0;1&display=swap" rel="stylesheet"/>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:        #1d140e;
      --surface:   #2f2117;
      --surface2:  #4a3628;
      --surface3:  #5a4330;
      --border:    rgba(199, 156, 96, 0.18);
      --border2:   rgba(227, 188, 126, 0.34);
      --text:      #f3e6cc;
      --muted:     #c7b08a;
      --accent:    #d9a441;
      --accent2:   #efd29a;
      --green:     #6f8d58;
      --amber:     #d8a24e;
      --red:       #b96844;
      --rose:      #8a5f47;
      --paper:     #e2cfa8;
      --paper-dark:#d1b786;
      --ink:       #20150f;
      --font-head: 'Cinzel', serif;
      --font-body: 'Crimson Text', serif;
      --font-accent: 'IM Fell English', serif;
    }

    html, body {
      width: 100%; height: 100%; overflow: hidden;
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-body);
    }

    /* ── Layout ── */
    #app {
      display: grid;
      grid-template-rows: 56px 1fr;
      grid-template-columns: 1fr 280px;
      height: 100vh;
    }

    /* ── Topbar ── */
    #topbar {
      grid-column: 1 / -1;
      display: flex;
      align-items: center;
      gap: 20px;
      padding: 0 20px;
      background:
        linear-gradient(180deg, rgba(255,241,211,0.06), transparent 36%),
        linear-gradient(90deg, rgba(34,23,16,0.25), rgba(102,74,44,0.12), rgba(34,23,16,0.25)),
        var(--surface);
      border-bottom: 1px solid var(--border2);
      box-shadow: 0 10px 28px rgba(14, 8, 5, 0.28);
      position: relative;
      z-index: 10;
    }

    #topbar::after {
      content: '';
      position: absolute;
      left: 18px;
      right: 18px;
      bottom: 6px;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(239,210,154,0.75), transparent);
      opacity: 0.65;
      pointer-events: none;
    }

    #topbar .logo {
      font-family: var(--font-head);
      font-size: 19px;
      font-weight: 700;
      letter-spacing: 0.08em;
      background: linear-gradient(90deg, var(--paper), var(--accent2), var(--accent));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      white-space: nowrap;
      text-transform: uppercase;
    }

    #topbar .file-badge {
      font-size: 13px;
      color: var(--muted);
      background: rgba(28, 18, 12, 0.52);
      border: 1px solid var(--border2);
      border-radius: 999px;
      padding: 4px 12px;
      font-style: italic;
    }

    .stat-chips {
      display: flex;
      gap: 8px;
      margin-left: auto;
    }

    .chip {
      font-size: 12px;
      font-family: var(--font-body);
      padding: 4px 12px;
      border-radius: 20px;
      border: 1px solid var(--border2);
      background: rgba(25, 16, 11, 0.42);
      color: var(--muted);
      white-space: nowrap;
    }

    .chip span {
      color: var(--accent);
      font-weight: 700;
    }

    /* ── Controls bar ── */
    #controls {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 0 12px;
      border-left: 1px solid var(--border);
    }

    .btn {
      font-family: var(--font-head);
      font-size: 10px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 7px 13px;
      border-radius: 999px;
      border: 1px solid var(--border2);
      background: linear-gradient(180deg, rgba(255,239,204,0.08), rgba(33,21,14,0.12)), var(--surface2);
      color: var(--text);
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s, color 0.15s, transform 0.15s;
      white-space: nowrap;
    }

    .btn:hover {
      background: linear-gradient(180deg, rgba(255,239,204,0.14), rgba(33,21,14,0.08)), var(--surface3);
      border-color: var(--accent);
      color: var(--accent);
      transform: translateY(-1px);
    }

    /* ── Graph canvas ── */
    #graph-wrap {
      position: relative;
      overflow: hidden;
      background:
        radial-gradient(circle at 22% 18%, rgba(242, 205, 138, 0.18) 0%, transparent 28%),
        radial-gradient(circle at 78% 22%, rgba(116, 80, 45, 0.22) 0%, transparent 30%),
        radial-gradient(circle at 50% 78%, rgba(60, 38, 24, 0.22) 0%, transparent 36%),
        linear-gradient(180deg, rgba(255,242,205,0.05), transparent 22%),
        linear-gradient(135deg, #24170f 0%, #1c130d 45%, #140d09 100%);
    }

    #graph-wrap::after {
      content: '';
      position: absolute;
      inset: 0;
      pointer-events: none;
      background:
        radial-gradient(circle at 50% 50%, transparent 55%, rgba(10, 6, 4, 0.28) 100%),
        linear-gradient(0deg, rgba(0,0,0,0.1), rgba(255,232,190,0.03));
      z-index: 0;
    }

    #network {
      width: 100%;
      height: 100%;
      position: relative;
      z-index: 1;
    }

    /* parchment grain */
    #graph-wrap::before {
      content: '';
      position: absolute;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(245, 226, 188, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(94, 63, 35, 0.025) 1px, transparent 1px),
        radial-gradient(circle at 10% 20%, rgba(255, 235, 197, 0.08) 0 1px, transparent 1.5px),
        radial-gradient(circle at 75% 60%, rgba(255, 235, 197, 0.06) 0 1px, transparent 1.5px);
      background-size: 46px 46px, 46px 46px, 18px 18px, 22px 22px;
      mix-blend-mode: screen;
      z-index: 0;
    }

    /* ── Sidebar ── */
    #sidebar {
      background:
        linear-gradient(180deg, rgba(255,241,211,0.05), transparent 18%),
        linear-gradient(180deg, #2d2118 0%, #241912 100%);
      border-left: 1px solid var(--border2);
      box-shadow: inset 8px 0 18px rgba(14, 8, 5, 0.22);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    #sidebar-header {
      padding: 14px 16px 10px;
      border-bottom: 1px solid var(--border);
      font-family: var(--font-head);
      font-size: 14px;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    /* Legend */
    #legend {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .legend-row {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 13px;
      color: var(--muted);
    }

    .legend-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      flex-shrink: 0;
      box-shadow: 0 0 0 1px rgba(38, 24, 15, 0.35);
    }

    .legend-line {
      width: 24px;
      height: 2px;
      flex-shrink: 0;
      border-radius: 1px;
    }

    /* Detail panel */
    #detail {
      flex: 1;
      overflow-y: auto;
      padding: 14px 16px;
    }

    #detail::-webkit-scrollbar { width: 4px; }
    #detail::-webkit-scrollbar-track { background: transparent; }
    #detail::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

    .detail-empty {
      color: var(--muted);
      font-size: 15px;
      line-height: 1.6;
      margin-top: 8px;
      font-style: italic;
      font-family: var(--font-accent);
    }

    .detail-name {
      font-family: var(--font-head);
      font-size: 20px;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 10px;
      word-break: break-all;
    }

    .detail-badge {
      display: inline-block;
      font-size: 11px;
      padding: 4px 9px;
      border-radius: 999px;
      margin-bottom: 12px;
      font-weight: 600;
      font-family: var(--font-head);
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }

    .detail-section {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
      margin: 12px 0 6px;
      font-family: var(--font-head);
    }

    .detail-row {
      font-size: 15px;
      color: var(--text);
      margin-bottom: 4px;
      display: flex;
      justify-content: space-between;
      gap: 12px;
    }

    .detail-row .key { color: var(--muted); }
    .detail-row .val { color: var(--accent); }

    .edge-item {
      font-size: 14px;
      padding: 7px 10px;
      border-radius: 10px;
      background: rgba(88, 63, 44, 0.38);
      border: 1px solid var(--border);
      margin-bottom: 5px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .edge-arrow { color: var(--accent); }
    .edge-label {
      color: var(--muted);
      font-size: 13px;
      margin-left: auto;
      font-style: italic;
      font-family: var(--font-accent);
    }

    /* ── Tooltip ── */
    #tooltip {
      position: fixed;
      pointer-events: none;
      z-index: 9999;
      background: linear-gradient(180deg, rgba(255,244,221,0.08), rgba(63,44,31,0.95)), var(--surface2);
      border: 1px solid var(--border2);
      border-radius: 10px;
      padding: 10px 13px;
      font-size: 13px;
      color: var(--text);
      line-height: 1.6;
      max-width: 230px;
      box-shadow: 0 14px 28px rgba(0,0,0,0.38);
      display: none;
      font-family: var(--font-body);
    }

    /* ── Undefined warning ── */
    #warn-banner {
      position: absolute;
      bottom: 12px;
      left: 12px;
      background: rgba(101, 49, 31, 0.8);
      border: 1px solid rgba(185, 104, 68, 0.55);
      border-radius: 10px;
      padding: 8px 13px;
      font-size: 13px;
      color: var(--red);
      z-index: 5;
      display: none;
      font-family: var(--font-body);
      box-shadow: 0 10px 18px rgba(12, 7, 5, 0.32);
    }
  </style>
</head>
<body>
<div id="app">

  <div id="topbar">
    <div class="logo">Story Chronicle</div>
    <div class="file-badge">""" + data["title"] + """</div>
    <div class="stat-chips">
      <div class="chip">Scenes <span>""" + str(data["scene_count"]) + """</span></div>
      <div class="chip">Paths <span>""" + str(data["edge_count"]) + """</span></div>
    </div>
    <div id="controls">
      <button class="btn" onclick="network.fit({animation:true})">Fit</button>
      <button class="btn" onclick="togglePhysics()">Physics</button>
      <button class="btn" onclick="network.setOptions({layout:{hierarchical:{enabled:!hierarchical,direction:'UD',sortMethod:'directed'}}});hierarchical=!hierarchical">Hierarchy</button>
    </div>
  </div>

  <div id="graph-wrap">
    <div id="network"></div>
    <div id="warn-banner"></div>
  </div>

  <div id="sidebar">
    <div id="sidebar-header">Chronicle</div>

    <div id="legend">
      <div class="legend-row"><div class="legend-dot" style="background:#d8b06a"></div>Opening scene</div>
      <div class="legend-row"><div class="legend-dot" style="background:#b88245"></div>Journey's end</div>
      <div class="legend-row"><div class="legend-dot" style="background:#8b6a3b"></div>Forking fate (&ge;2 exits)</div>
      <div class="legend-row"><div class="legend-dot" style="background:#6c4d35;border:1px solid #d9a441"></div>Story scene</div>
      <div class="legend-row"><div class="legend-dot" style="background:#7f3f2d"></div>Lost realm</div>
      <hr style="border:none;border-top:1px solid var(--border);margin:2px 0"/>
      <div class="legend-row"><div class="legend-line" style="background:#d9a441"></div>Choice transition</div>
      <div class="legend-row"><div class="legend-line" style="background:#6f8d58;border-top:2px dashed #6f8d58;background:none"></div>IF transition</div>
      <div class="legend-row"><div class="legend-line" style="background:#b96844;border-top:2px dashed #b96844;background:none"></div>ELSE transition</div>
    </div>

    <div id="detail">
      <div class="detail-empty">Choose a scene or path to open its chronicle here.</div>
    </div>
  </div>
</div>

<div id="tooltip"></div>

<script>
""")

    parts.append(data_script)

    parts.append("""
// ── Node & edge styling ──────────────────────────────────────────────────

const NODE_COLORS = {
  start:     { background: '#d8b06a', border: '#f2ddb0', highlight: { background: '#e6c27d', border: '#f7e6bf' }, hover: { background: '#e6c27d', border: '#f7e6bf' } },
  terminal:  { background: '#b88245', border: '#e4c28d', highlight: { background: '#c69050', border: '#edd2a7' }, hover: { background: '#c69050', border: '#edd2a7' } },
  branch:    { background: '#8b6a3b', border: '#dabb7f', highlight: { background: '#9c7845', border: '#e7ca90' }, hover: { background: '#9c7845', border: '#e7ca90' } },
  normal:    { background: '#6c4d35', border: '#d9a441', highlight: { background: '#7b593d', border: '#efbf66' }, hover: { background: '#7b593d', border: '#efbf66' } },
  undefined: { background: '#7f3f2d', border: '#d89270', highlight: { background: '#96503a', border: '#e0a285' }, hover: { background: '#96503a', border: '#e0a285' } },
};

const EDGE_STYLES = {
  choice:   { color: '#d9a441', dashes: false, label: 'Choice transition' },
  if_true:  { color: '#6f8d58', dashes: [6, 4], label: 'IF transition' },
  if_false: { color: '#b96844', dashes: [6, 4], label: 'ELSE transition' },
};

const NODE_LABELS = {
  start: 'opening scene',
  terminal: "journey's end",
  branch: 'forking fate',
  normal: 'story scene',
  undefined: 'lost realm',
};

function buildVisNodes() {
  return GRAPH_DATA.nodes.map(n => {
    const col = NODE_COLORS[n.type] || NODE_COLORS.normal;
    const stmts = Object.entries(n.statements || {})
      .map(([k,v]) => v + ' ' + k).join(', ') || 'empty';
    const shape = n.type === 'start' ? 'diamond' : n.type === 'branch' ? 'hexagon' : 'dot';
    return {
      id: n.id,
      label: n.label,
      title: '<b>' + n.label + '</b><br/>Kind: ' + (NODE_LABELS[n.type] || n.type) + '<br/>Paths onward: ' + n.outgoing + '<br/>Contains: ' + stmts,
      color: col,
      shape,
      font: { color: '#f6ead3', size: 18, face: 'Cinzel', strokeWidth: 2, strokeColor: '#1d140e' },
      size: n.type === 'start' ? 24 : n.type === 'branch' ? 21 : 18,
      borderWidth: n.type === 'undefined' ? 2.4 : 2,
      shadow: { enabled: true, color: 'rgba(10, 6, 4, 0.45)', size: 18, x: 0, y: 6 },
    };
  });
}

function buildVisEdges() {
  return GRAPH_DATA.edges.map(e => {
    const style = EDGE_STYLES[e.type] || EDGE_STYLES.choice;
    return {
      id: e.id,
      from: e.from,
      to: e.to,
      label: e.label,
      dashes: style.dashes,
      color: { color: style.color, highlight: '#f3e6cc', hover: '#f3e6cc', opacity: 0.9 },
      font: { color: '#d8c29a', size: 14, face: 'Crimson Text', strokeWidth: 4, strokeColor: '#1d140e', align: 'middle', ital: { color: '#d8c29a' } },
      width: 2.4,
      hoverWidth: 3,
      selectionWidth: 3,
      arrows: { to: { enabled: true, type: 'arrow', scaleFactor: 0.95 } },
      smooth: { enabled: true, type: 'dynamic', roundness: 0.4 },
    };
  });
}

// ── Build network ─────────────────────────────────────────────────────────

const container = document.getElementById('network');
const visNodes = new vis.DataSet(buildVisNodes());
const visEdges = new vis.DataSet(buildVisEdges());

let physicsOn = true;
let hierarchical = false;

const network = new vis.Network(container, { nodes: visNodes, edges: visEdges }, {
  autoResize: true,
  physics: {
    enabled: true,
    solver: 'forceAtlas2Based',
    forceAtlas2Based: {
      gravitationalConstant: -80,
      springLength: 160,
      springConstant: 0.05,
      damping: 0.5,
    },
    stabilization: { iterations: 250 },
  },
  interaction: {
    hover: true,
    multiselect: false,
    navigationButtons: false,
    keyboard: true,
    tooltipDelay: 0,
  },
  layout: { improvedLayout: true },
});

network.once('stabilizationIterationsDone', () => {
  network.fit({ animation: { duration: 800, easingFunction: 'easeInOutQuad' } });
});

// ── Toggle helpers ────────────────────────────────────────────────────────

function togglePhysics() {
  physicsOn = !physicsOn;
  network.setOptions({ physics: { enabled: physicsOn } });
}

// ── Sidebar detail panel ──────────────────────────────────────────────────

const detail = document.getElementById('detail');

function renderNodeDetail(nodeId) {
  const n = GRAPH_DATA.nodes.find(x => x.id === nodeId);
  if (!n) return;

  const badgeColors = {
    start:     'background:#4f3518;color:#f2ddb0;border:1px solid #d8b06a',
    terminal:  'background:#5a3517;color:#f0d1a2;border:1px solid #b88245',
    branch:    'background:#49331c;color:#ebd39b;border:1px solid #8b6a3b',
    normal:    'background:#3b291c;color:#e8cb90;border:1px solid #d9a441',
    undefined: 'background:#4a2217;color:#edb096;border:1px solid #b96844',
  };
  const badgeStyle = badgeColors[n.type] || badgeColors.normal;

  const outEdges = GRAPH_DATA.edges.filter(e => e.from === nodeId);
  const inEdges  = GRAPH_DATA.edges.filter(e => e.to   === nodeId);

  let html = '';
  html += '<div class="detail-name">' + escHtml(n.label) + '</div>';
  html += '<span class="detail-badge" style="' + badgeStyle + '">' + escHtml(NODE_LABELS[n.type] || n.type) + '</span>';

  html += '<div class="detail-section">Chronicle</div>';
  html += '<div class="detail-row"><span class="key">Paths onward</span><span class="val">' + n.outgoing + '</span></div>';
  html += '<div class="detail-row"><span class="key">Paths arriving</span><span class="val">' + inEdges.length + '</span></div>';

  if (Object.keys(n.statements).length) {
    html += '<div class="detail-section">Script</div>';
    for (const [k, v] of Object.entries(n.statements)) {
      html += '<div class="detail-row"><span class="key">' + escHtml(k) + '</span><span class="val">' + v + '</span></div>';
    }
  }

  if (outEdges.length) {
    html += '<div class="detail-section">Roads onward</div>';
    outEdges.forEach(e => {
      const typeColor = e.type === 'if_true' ? '#6f8d58' : e.type === 'if_false' ? '#b96844' : '#d9a441';
      html += '<div class="edge-item">';
      html += '<span class="edge-arrow" style="color:' + typeColor + '">&#x2192;</span>';
      html += '<span>' + escHtml(e.to) + '</span>';
      html += '<span class="edge-label">' + escHtml(e.label) + '</span>';
      html += '</div>';
    });
  }

  if (inEdges.length) {
    html += '<div class="detail-section">Roads arriving</div>';
    inEdges.forEach(e => {
      html += '<div class="edge-item">';
      html += '<span class="edge-arrow" style="color:#c7b08a">&#x2190;</span>';
      html += '<span>' + escHtml(e.from) + '</span>';
      html += '<span class="edge-label">' + escHtml(e.label) + '</span>';
      html += '</div>';
    });
  }

  detail.innerHTML = html;
}

function renderEdgeDetail(edgeId) {
  const e = GRAPH_DATA.edges.find(x => x.id === edgeId);
  if (!e) return;
  const style = EDGE_STYLES[e.type] || EDGE_STYLES.choice;
  const typeColor = style.color;
  let html = '';
  html += '<div class="detail-name" style="font-size:15px">' + escHtml(e.from) + ' &#x2192; ' + escHtml(e.to) + '</div>';
  html += '<span class="detail-badge" style="background:#3b291c;color:' + typeColor + ';border:1px solid ' + typeColor + '">' + escHtml(style.label) + '</span>';
  html += '<div class="detail-section">Path</div>';
  html += '<div class="detail-row"><span class="key">Marking</span><span class="val">' + escHtml(e.label) + '</span></div>';
  html += '<div class="detail-row"><span class="key">From scene</span><span class="val">' + escHtml(e.from) + '</span></div>';
  html += '<div class="detail-row"><span class="key">To scene</span><span class="val">' + escHtml(e.to) + '</span></div>';
  detail.innerHTML = html;
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

network.on('click', params => {
  if (params.nodes.length) {
    renderNodeDetail(params.nodes[0]);
  } else if (params.edges.length) {
    renderEdgeDetail(params.edges[0]);
  } else {
    detail.innerHTML = '<div class="detail-empty">Choose a scene or path to open its chronicle here.</div>';
  }
});

// ── Undefined warning banner ──────────────────────────────────────────────

const undef = GRAPH_DATA.nodes.filter(n => n.type === 'undefined');
if (undef.length) {
  const banner = document.getElementById('warn-banner');
  banner.style.display = 'block';
  banner.textContent = undef.length + ' lost realm' + (undef.length > 1 ? 's' : '') + ': ' + undef.map(n => n.id).join(', ');
}
</script>
</body>
</html>
""")

    return "".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate interactive StoryLang path graph HTML.")
    p.add_argument("story_file", help="Path to .story file")
    p.add_argument("-o", "--output", default=None, help="Output HTML path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    story_path = Path(args.story_file)

    if not story_path.exists():
        print(f"Error: file not found: {story_path}")
        return 1

    output = Path(args.output) if args.output else Path(f"{story_path.stem}_graph.html")

    try:
        data = collect_graph_data(story_path)
        html = build_html(data)
        output.write_text(html, encoding="utf-8")
    except (LexerError, ParseError) as exc:
        print(f"Parse error: {exc}")
        return 1
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"Unexpected error: {exc}")
        return 1

    print(f"Graph generated: {output.resolve()}")
    print(f"  {data['scene_count']} scenes, {data['edge_count']} transitions")
    if data["undefined_count"]:
        print(f"  WARNING: {data['undefined_count']} undefined target scene(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
