"""RBT-06 SC#4 / RBT-09 D-07 — operator free-text never reaches an HTML-injection sink.

Operator-entered identity + score values cross from the console into two untrusted-text →
broadcast/preview DOM surfaces:

  1. The CEF browser-source overlay lower-third (``overlay-render.js renderIdentity`` builds the
     competitor from ``cane``/``conduttore``).
  2. The entry-form identity preview echo (``score-entry.js`` identity block).

The mitigation is two-layered and proven at TWO levels (D-07a grep + D-07b DOM render):

  * **D-07a (source grep, both served JS files):** neither ``overlay-render.js`` nor
    ``score-entry.js`` contains an ``innerHTML`` sink — every operator value reaches the DOM
    via ``textContent`` / ``createTextNode`` / ``createElementNS`` only.
  * **D-07b (node fake-DOM render):** a crafted ``<script>x</script>`` payload, driven through
    ``renderIdentity`` (overlay lower-third) AND the form preview echo, lands as a single INERT
    text node — ``textContent === payload`` with NO child *element* parsed (``childElementCount
    === 0`` / ``children.length === 0``).

Plus the original Jinja-sink regression (static branding autoescaped on GET /overlay).

Flask test_client + node only — no heavy import (RBT-07 crash-isolation stays green). The node
DOM assertions skip cleanly when node is absent; the grep assertions always run.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

import pytest

from segugio.ui.app import create_app

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "src",
    "segugio",
    "ui",
    "static",
)
_OVERLAY_JS_PATH = os.path.join(_STATIC_DIR, "overlay-render.js")
_SCORE_ENTRY_JS_PATH = os.path.join(_STATIC_DIR, "score-entry.js")

_NODE = shutil.which("node")
_requires_node = pytest.mark.skipif(_NODE is None, reason="node not available for DOM render test")


def _read_file_js() -> str:
    with open(_OVERLAY_JS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def _read_score_entry_js() -> str:
    with open(_SCORE_ENTRY_JS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


# --- D-07a: no innerHTML sink in EITHER served JS file ------------------------ #


def test_no_innerhtml_sink():
    """SC#4 (T-14-xss / T-18-01/02) — operator values never reach an innerHTML sink.

    Extended for RBT-09 to read BOTH served renderer files: the broadcast renderer
    (``overlay-render.js``) AND the entry-form component (``score-entry.js``). Every
    operator value must write via ``textContent`` and there must be NO ``.innerHTML``
    sink (any whitespace variant) in either file.
    """
    for label, js in (
        ("overlay-render.js", _read_file_js()),
        ("score-entry.js", _read_score_entry_js()),
    ):
        assert "textContent" in js, f"{label} must write values via textContent"
        for variant in ("innerHTML =", "innerHTML=", "innerHTML  ="):
            assert variant not in js, f"forbidden HTML-injection sink in {label}: {variant!r}"
        assert ".innerHTML" not in js, f"forbidden .innerHTML sink in {label}"


# --- D-07b: a crafted <script> renders as one inert text node (node fake-DOM) - #


@_requires_node
def test_render_identity_script_payload_inert():
    """D-07b (overlay lower-third) — ``renderIdentity`` renders a crafted ``<script>`` inert.

    Drive the served ``renderIdentity`` under a minimal fake DOM with a ``createTextNode`` stub
    that tracks node type. A ``<script>x</script>`` in ``cane`` must land as a single text node:
    ``textContent === payload`` and ``childElementCount === 0`` (no parsed ``<script>`` element).
    """
    js = _read_file_js()
    payload = "<script>x</script>"
    driver = (
        js
        + "\nconst _m = module.exports;\n"
        + "const PAYLOAD = " + json.dumps(payload) + ";\n"
        + r"""
function makeEl(tag) {
  const node = {
    tagName: (tag || '').toUpperCase(),
    nodeType: 1,
    children: [],
    _text: '',
    className: '',
    _attrs: {},
    appendChild(c) { this.children.push(c); return c; },
    removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); return c; },
    getAttribute(k) { return (k in this._attrs) ? this._attrs[k] : null; },
    setAttribute(k, v) { this._attrs[k] = String(v); },
    querySelector() { return null; },
  };
  Object.defineProperty(node, 'firstChild', { get() { return this.children[0] || null; } });
  Object.defineProperty(node, 'textContent', {
    get() { return this.children.length === 0 ? this._text : this.children.map(c => c.textContent).join(''); },
    set(v) { this.children = []; this._text = String(v); },
  });
  Object.defineProperty(node, 'childElementCount', {
    get() { return this.children.filter(c => c.nodeType === 1).length; },
  });
  return node;
}
// createTextNode yields a TEXT node (nodeType 3); createElement yields an ELEMENT (nodeType 1).
global.document = {
  createElement: (t) => makeEl(t),
  createTextNode: (t) => ({ nodeType: 3, textContent: String(t) }),
};
const identityEl = makeEl('div');
identityEl.setAttribute('data-event', '');   // empty event → the competitor-only branch
_m.renderIdentity(identityEl, { cane: PAYLOAD, conduttore: "" });
process.stdout.write(JSON.stringify({
  textContent: identityEl.textContent,
  childElementCount: identityEl.childElementCount,
}));
"""
    )
    out = json.loads(_run_node(driver))
    assert out["textContent"] == payload, "the crafted value must render as inert text, verbatim"
    assert out["childElementCount"] == 0, "no <script> element may be parsed — one text node only"


@_requires_node
def test_form_preview_script_payload_inert():
    """D-07b (entry-form preview) — the identity echo renders a crafted ``<script>`` inert.

    Mount the served ``score-entry.js`` under the shared fake DOM, type a crafted
    ``<script>x</script>`` into the ``cane`` identity input, dispatch ``input``, and assert the
    preview echo holds it as inert text: ``textContent === payload`` and ``children.length === 0``.
    """
    js = _read_score_entry_js()
    cfg = _disc_cfg()
    payload = "<script>x</script>"
    driver = (
        _FAKE_DOM
        + js
        + r"""
const api = module.exports;
const cfg = """ + cfg + r""";
const root = document.createElement('div');
api.mount(root, cfg);
const cane = root.querySelectorAll('[data-field="cane"]')[0];
cane.value = """ + json.dumps(payload) + r""";
cane.dispatch('input');
const echo = root.querySelector('.identity-echo');
process.stdout.write(JSON.stringify({
  found: !!cane && !!echo,
  textContent: echo ? echo.textContent : null,
  childrenLength: echo ? echo.children.length : -1,
}));
"""
    )
    out = json.loads(_run_node(driver))
    assert out["found"] is True, "the cane input and the identity echo must both exist"
    assert out["textContent"] == payload, "the preview echo must hold the crafted value as inert text"
    assert out["childrenLength"] == 0, "no element may be parsed from the crafted value — text only"


# --- Jinja branding sink regression (unchanged) ------------------------------- #


def test_overlay_jinja_autoescapes_branding():
    """SC#4 (T-14-xss) — a crafted event_name renders ESCAPED on GET /overlay, never raw.

    ``event_name`` is injected into the ``#identity`` div via Jinja (``{{ event_name }}``),
    autoescape ON. A crafted ``<script>x</script>`` must be served as ``&lt;script&gt;`` and
    must NOT appear raw — proving the branding sink cannot inject markup into the broadcast.
    """
    tmp = tempfile.mkdtemp()
    payload = "<script>x</script>"
    app = create_app(tmp, cam_ids=["cam_wide"], overlay_cfg={"event_name": payload})
    resp = app.test_client().get("/overlay")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # The raw <script> must NOT survive into the served overlay HTML.
    assert payload not in html, "raw <script> reached the overlay — Jinja autoescape is OFF (T-14-xss)"
    # The escaped form proves autoescape ran at the identity sink.
    assert "&lt;script&gt;x&lt;/script&gt;" in html, "event_name was not Jinja-autoescaped"


# ============================================================================ #
# node helpers + fake-DOM harness (copy-adapted from tests/test_ui_score_entry.py) #
# ============================================================================ #


def _run_node(driver_src: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, encoding="utf-8") as fh:
        fh.write(driver_src)
        path = fh.name
    try:
        proc = subprocess.run([_NODE, path], capture_output=True, timeout=30)
        stderr = proc.stderr.decode("utf-8", errors="replace")
        assert proc.returncode == 0, f"node failed: {stderr}"
        return proc.stdout.decode("utf-8")
    finally:
        os.unlink(path)


def _disc_cfg() -> str:
    """The cfg blob a disc_tf host receives, as a JSON literal source string."""
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    html = app.test_client().get("/score-entry").get_data(as_text=True)
    blob = html.split('id="score-cfg">', 1)[1].split("</script>", 1)[0]
    cfg = json.loads(blob)
    cfg["disciplines"] = ["disc_tf"]  # single active discipline — identity block is universal
    return json.dumps(cfg)


# A self-contained fake DOM + globals, prepended to the served module per driver. Copy-adapted
# verbatim from tests/test_ui_score_entry.py — the load-bearing piece is the textContent getter
# (concatenates child text nodes) so a crafted value's inertness is observable.
_FAKE_DOM = r"""
'use strict';
function FakeClassList(node){ this._set=new Set(); this._node=node; }
FakeClassList.prototype.add=function(){ for(const c of arguments) this._set.add(c); this._sync(); };
FakeClassList.prototype.remove=function(){ for(const c of arguments) this._set.delete(c); this._sync(); };
FakeClassList.prototype.toggle=function(c,force){
  const want = (force===undefined) ? !this._set.has(c) : !!force;
  if(want) this._set.add(c); else this._set.delete(c); this._sync(); return want;
};
FakeClassList.prototype.contains=function(c){ return this._set.has(c); };
FakeClassList.prototype._sync=function(){ this._node._className=Array.from(this._set).join(' '); };

function FakeNode(tag, ns){
  this.tagName=(tag||'').toUpperCase(); this.ns=ns||null;
  this.children=[]; this.parentNode=null; this.attrs={};
  this._listeners={}; this._text=''; this._className='';
  this.classList=new FakeClassList(this);
  this.value=''; this.checked=false; this.type=''; this.id='';
}
Object.defineProperty(FakeNode.prototype,'firstChild',{get:function(){return this.children[0]||null;}});
Object.defineProperty(FakeNode.prototype,'className',{
  get:function(){return this._className;},
  set:function(v){ this._className=v; this.classList._set=new Set(String(v).split(/\s+/).filter(Boolean)); }
});
Object.defineProperty(FakeNode.prototype,'textContent',{
  get:function(){
    if(this.children.length===0) return this._text;
    return this.children.map(c=>c.textContent).join('');
  },
  set:function(v){ this.children=[]; this._text=String(v); }
});
FakeNode.prototype.appendChild=function(c){ c.parentNode=this; this.children.push(c); return c; };
FakeNode.prototype.removeChild=function(c){
  const i=this.children.indexOf(c); if(i>=0) this.children.splice(i,1); c.parentNode=null; return c;
};
FakeNode.prototype.setAttribute=function(k,v){
  this.attrs[k]=String(v);
  if(k==='id') this.id=String(v);
  if(k==='type') this.type=String(v);
  if(k==='class') this.className=String(v);
  if(k==='value') this.value=String(v);
};
FakeNode.prototype.getAttribute=function(k){ return (k in this.attrs)?this.attrs[k]:null; };
FakeNode.prototype.addEventListener=function(ev,fn){ (this._listeners[ev]=this._listeners[ev]||[]).push(fn); };
FakeNode.prototype.dispatch=function(ev,obj){
  (this._listeners[ev]||[]).forEach(fn=>fn(obj||{target:this,preventDefault:function(){}}));
};
function _walk(node,acc){ acc.push(node); node.children.forEach(c=>_walk(c,acc)); return acc; }
function _matchSel(node,sel){
  if(sel.charAt(0)==='.') return node.classList.contains(sel.slice(1));
  const m=sel.match(/^\[([^=\]]+)(?:=["']?([^"'\]]*)["']?)?\]$/);
  if(m){ const a=node.getAttribute(m[1]); return m[2]===undefined ? a!==null : a===m[2]; }
  return node.tagName===sel.toUpperCase();
}
function _matchCompound(node,compound){
  const parts=compound.match(/\.[^.\[\]\s]+|\[[^\]]+\]|[a-zA-Z]+/g)||[compound];
  return parts.every(p=>_matchSel(node,p));
}
function _hasAncestor(node,compound){
  let p=node.parentNode;
  while(p){ if(_matchCompound(p,compound)) return true; p=p.parentNode; }
  return false;
}
FakeNode.prototype.querySelectorAll=function(sel){
  const self=this;
  const compounds=sel.trim().split(/\s+/);
  const target=compounds[compounds.length-1];
  const ancestors=compounds.slice(0,-1);
  return _walk(this,[]).filter(function(n){
    if(n===self) return false;
    if(!_matchCompound(n,target)) return false;
    return ancestors.every(a=>_hasAncestor(n,a));
  });
};
FakeNode.prototype.querySelector=function(sel){ return this.querySelectorAll(sel)[0]||null; };

const _byId={};
const document={
  createElement:function(t){ return new FakeNode(t,null); },
  createElementNS:function(ns,t){ return new FakeNode(t,ns); },
  getElementById:function(id){ return _byId[id]||null; },
  _register:function(node){ if(node.id) _byId[node.id]=node; }
};
const _origSet=FakeNode.prototype.setAttribute;
FakeNode.prototype.setAttribute=function(k,v){ _origSet.call(this,k,v); if(k==='id') document._register(this); };

const _store={};
const localStorage={
  getItem:function(k){ return (k in _store)?_store[k]:null; },
  setItem:function(k,v){ _store[k]=String(v); },
  removeItem:function(k){ delete _store[k]; }
};

let _fetchResp={ok:true,status:204,json:function(){return Promise.resolve({});}};
function _setFetchResp(r){ _fetchResp=r; }
let _fetchCalls=0;
function fetch(){ _fetchCalls++; return Promise.resolve(_fetchResp); }

const _timers=[];
function setTimeout(fn,ms){ const id=_timers.length; _timers.push({fn:fn,ms:ms,cleared:false}); return id; }
function clearTimeout(id){ if(_timers[id]) _timers[id].cleared=true; }
function _fireTimers(){ _timers.forEach(t=>{ if(!t.cleared) t.fn(); }); }

const window={};
// `module` / `module.exports` are provided by node's CJS wrapper — do not redeclare.
"""
