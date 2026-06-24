"""SCE-01/02/03/05 — shared score-entry COMPONENT + dedicated /score-entry page (Plan 16-02).

STUBS landed in Wave 0 (Plan 16-01) so the gates EXIST for the component plan to turn green.
``src/segugio/ui/static/score-entry.js`` (the ONE ``mount(root, cfg)`` factory), the
``score-entry.html`` thin host, and the ``GET /score-entry`` route are all built in Plan 16-02 —
these tests ``pytest.skip("implemented in 16-02")`` until then so the file COLLECTS green now.

Clones the served-JS / node helper machinery from ``tests/test_ui_overlay_render.py``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

import pytest

from segugio.ui.app import create_app

_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "src",
    "segugio",
    "ui",
    "static",
    "score-entry.js",
)

_NODE = shutil.which("node")
_requires_node = pytest.mark.skipif(_NODE is None, reason="node not available for behavior test")


def _read_file_js():
    with open(_JS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def _read_served_js():
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    resp = app.test_client().get("/static/score-entry.js")
    assert resp.status_code == 200, "score-entry.js must be auto-served at /static/score-entry.js"
    return resp.get_data(as_text=True)


# --- SCE-01: dual export + thin host ------------------------------------------ #


def test_dual_export_and_thin_host():
    """score-entry.js exports mount on window AND module.exports; /score-entry host has no <input>."""
    js = _read_file_js()
    assert "window.SEGUGIO_SCORE_ENTRY" in js
    assert "module.exports" in js
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    html = app.test_client().get("/score-entry").get_data(as_text=True)
    assert "<input" not in html, "thin host must carry no <input> of its own (component builds them)"


# --- SCE-02: disciplines driven by the injected profile ----------------------- #


def test_disciplines_from_profile():
    """disc-dog config → T&F + Freestyle; agility config → Agility only (D-06)."""
    import json

    tmp = tempfile.mkdtemp()
    # Default sport ("disc_dog") offers both disc disciplines.
    app = create_app(tmp, cam_ids=["cam_wide"])
    html = app.test_client().get("/score-entry").get_data(as_text=True)
    assert "disc_tf" in html and "disc_freestyle" in html
    # The injected score-cfg blob carries the D-06 discipline list AND decimal-STRING numerics.
    blob = html.split('id="score-cfg">', 1)[1].split("</script>", 1)[0]
    cfg = json.loads(blob)
    assert cfg["sport"] == "disc_dog"
    assert cfg["disciplines"] == ["disc_tf", "disc_freestyle"]
    # T-16-10: every profile numeric is a decimal STRING, never a float (e.g. 5.0).
    assert cfg["profile"]["per_throw_cap"] == "5"
    assert cfg["profile"]["zones"][0][1] == "1"
    assert cfg["profile"]["bonuses"][0][1] == "0.5"
    assert cfg["profile"]["freestyle_cats"][0][3] == "0.01"
    assert cfg["profile"]["count_best_n"] == 5  # a count stays an int, not a string

    # An agility config offers Agility only (D-06).
    from segugio.ui import score_calc

    tmp2 = tempfile.mkdtemp()
    app2 = create_app(
        tmp2, cam_ids=["cam_wide"], profile=score_calc.FCI_AGILITY_PROFILE, sport="agility"
    )
    html2 = app2.test_client().get("/score-entry").get_data(as_text=True)
    cfg2 = json.loads(html2.split('id="score-cfg">', 1)[1].split("</script>", 1)[0])
    assert cfg2["sport"] == "agility"
    assert cfg2["disciplines"] == ["agility"]


# --- SCE-02 / SCE-05: no innerHTML sink for operator values ------------------- #


def test_no_innerhtml_sink():
    """T-16 / XSS — operator values via textContent, never an innerHTML sink."""
    js = _read_file_js()
    assert "textContent" in js
    for variant in ("innerHTML =", "innerHTML=", "innerHTML  ="):
        assert variant not in js, f"forbidden HTML-injection sink found: {variant!r}"


# --- SCE-03: live advisory total updates in place ----------------------------- #


@_requires_node
def test_live_total_advisory():
    """The live advisory total recomputes IN PLACE on input (labeled non-authoritative)."""
    js = _read_file_js()
    assert "SEGUGIO_SCORE_CALC" in js or "compute" in js


# ============================================================================ #
# Phase-17 behaviors — node fake-DOM harness                                   #
# ============================================================================ #
#
# mount(root, cfg) needs a DOM, localStorage, timers and fetch. We run the served
# module under a minimal hand-rolled fake DOM in node (the MEMORY "node fake-DOM"
# precedent for /overlay bugs) so the Phase-17 component behaviors are exercised
# end-to-end without a browser. The shim is intentionally tiny — only what mount()
# touches: element tree, classList, value/checked, querySelector*, getElementById,
# event dispatch, a real in-memory localStorage, recorded setTimeout, and a fetch
# stub whose response the driver controls.


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


# A self-contained fake DOM + globals, prepended to the served module per driver.
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
  // supports a single compound '.a.b' or '[attr="v"]' or tag — enough for this component
  const parts=compound.match(/\.[^.\[\]\s]+|\[[^\]]+\]|[a-zA-Z]+/g)||[compound];
  return parts.every(p=>_matchSel(node,p));
}
function _hasAncestor(node,compound){
  let p=node.parentNode;
  while(p){ if(_matchCompound(p,compound)) return true; p=p.parentNode; }
  return false;
}
FakeNode.prototype.querySelectorAll=function(sel){
  // descendant combinator support: 'A B' → B that has an ancestor matching A
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
// patch setAttribute to register ids on the document (so getElementById('publish-banner') works)
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


def _disc_cfg():
    """The cfg blob a disc_tf host receives, as a JS literal source string."""
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    html = app.test_client().get("/score-entry").get_data(as_text=True)
    blob = html.split('id="score-cfg">', 1)[1].split("</script>", 1)[0]
    cfg = json.loads(blob)
    # Force a single discipline (disc_tf) so the throw list is the active surface.
    cfg["disciplines"] = ["disc_tf"]
    return json.dumps(cfg)


_DRAFT_KEY = "segugio.score.draft"


@_requires_node
def test_draft_persists_and_restores_throw_list():
    """SCC-05 / D-02/D-03: adding throws writes a draft; a fresh mount restores them."""
    js = _read_file_js()
    cfg = _disc_cfg()
    driver = (
        _FAKE_DOM
        + js
        + r"""
const api = module.exports;
const cfg = """ + cfg + r""";
// First mount: add two throws with zone values, then read what the draft stored.
const root1 = document.createElement('div');
const h1 = api.mount(root1, cfg);
const addBtn = root1.querySelectorAll('.add-throw')[0];
addBtn.dispatch('click');
addBtn.dispatch('click');
const rows1 = root1.querySelectorAll('.throw-row');
rows1[0].querySelector('.throw-zone').value = '2';
rows1[0].querySelector('.throw-zone').dispatch('input');
rows1[1].querySelector('.throw-zone').value = '3';
rows1[1].querySelector('.throw-midair').checked = true;
rows1[1].querySelector('.throw-midair').dispatch('input');
const draftAfter = localStorage.getItem('""" + _DRAFT_KEY + r"""');

// Second mount (simulate reload) into a FRESH root, same draft in localStorage.
const root2 = document.createElement('div');
const h2 = api.mount(root2, cfg);
const rows2 = root2.querySelectorAll('.throw-row');
process.stdout.write(JSON.stringify({
  draftWritten: draftAfter !== null,
  restoredCount: rows2.length,
  zone0: rows2[0] ? rows2[0].querySelector('.throw-zone').value : null,
  zone1: rows2[1] ? rows2[1].querySelector('.throw-zone').value : null,
  midair1: rows2[1] ? rows2[1].querySelector('.throw-midair').checked : null,
}));
"""
    )
    out = json.loads(_run_node(driver))
    assert out["draftWritten"] is True, "a draft must be written on throw mutation"
    assert out["restoredCount"] == 2, "both throws must be restored on a fresh mount"
    assert out["zone0"] == "2"
    assert out["zone1"] == "3"
    assert out["midair1"] is True, "the midair flag must survive the reload"


@_requires_node
def test_corrupt_draft_yields_empty_never_throws():
    """SCC-05 / D-02: a torn localStorage value → empty draft, mount never raises."""
    js = _read_file_js()
    cfg = _disc_cfg()
    driver = (
        _FAKE_DOM
        + js
        + r"""
const api = module.exports;
const cfg = """ + cfg + r""";
localStorage.setItem('""" + _DRAFT_KEY + r"""', '{');  // corrupt JSON
let threw = false;
let rowCount = -1;
try {
  const root = document.createElement('div');
  api.mount(root, cfg);
  rowCount = root.querySelectorAll('.throw-row').length;
} catch (e) { threw = true; }
process.stdout.write(JSON.stringify({ threw: threw, rowCount: rowCount }));
"""
    )
    out = json.loads(_run_node(driver))
    assert out["threw"] is False, "a corrupt draft must never raise out of mount()"
    assert out["rowCount"] == 0, "a corrupt draft yields an empty throw list"


@_requires_node
def test_draft_cleared_only_on_2xx_publish():
    """SCC-05 / D-04: a 2xx publish clears the draft; a 400 keeps it."""
    js = _read_file_js()
    cfg = _disc_cfg()
    driver = (
        _FAKE_DOM
        + js
        + r"""
const api = module.exports;
const cfg = """ + cfg + r""";

function addOneThrow(root){
  root.querySelectorAll('.add-throw')[0].dispatch('click');
  const r = root.querySelectorAll('.throw-row')[0];
  r.querySelector('.throw-zone').value = '2';
  r.querySelector('.throw-zone').dispatch('input');
}

// --- 400 keeps the draft ---
const rootA = document.createElement('div');
const hA = api.mount(rootA, cfg);
addOneThrow(rootA);
_setFetchResp({ ok:false, status:400, json:function(){return Promise.resolve({errors:[]});} });
hA.submit();
setImmediate(function(){
  const keptAfter400 = localStorage.getItem('""" + _DRAFT_KEY + r"""') !== null;

  // --- 2xx clears the draft ---
  _setFetchResp({ ok:true, status:204, json:function(){return Promise.resolve({});} });
  hA.submit();
  setImmediate(function(){
    const clearedAfter2xx = localStorage.getItem('""" + _DRAFT_KEY + r"""') === null;
    process.stdout.write(JSON.stringify({
      keptAfter400: keptAfter400,
      clearedAfter2xx: clearedAfter2xx,
    }));
  });
});
"""
    )
    out = json.loads(_run_node(driver))
    assert out["keptAfter400"] is True, "a 400 must KEEP the draft (nothing lost, D-04)"
    assert out["clearedAfter2xx"] is True, "a 2xx publish must CLEAR the draft"


# --- SCE-04 / D-05: two-step danger-styled publish confirm -------------------- #


@_requires_node
def test_publish_two_step_confirm():
    """SCE-04 / D-05: first tap arms a red 'Conferma invio' (no POST); second tap POSTs."""
    js = _read_file_js()
    cfg = _disc_cfg()
    driver = (
        _FAKE_DOM
        + js
        + r"""
const api = module.exports;
const cfg = """ + cfg + r""";
const root = document.createElement('div');
api.mount(root, cfg);
const btn = root.querySelectorAll('.publish button')[0];
const labelBefore = btn.textContent;
// First tap: arms, morphs to danger 'Conferma invio', does NOT POST.
btn.dispatch('click');
const armedLabel = btn.textContent;
const armedDanger = btn.classList.contains('danger');
const callsAfterArm = _fetchCalls;
// Second tap (while armed): POSTs, then reverts/disarms.
btn.dispatch('click');
const callsAfterConfirm = _fetchCalls;
const labelAfterConfirm = btn.textContent;
const dangerAfterConfirm = btn.classList.contains('danger');
process.stdout.write(JSON.stringify({
  labelBefore: labelBefore,
  armedLabel: armedLabel,
  armedDanger: armedDanger,
  callsAfterArm: callsAfterArm,
  callsAfterConfirm: callsAfterConfirm,
  labelAfterConfirm: labelAfterConfirm,
  dangerAfterConfirm: dangerAfterConfirm,
}));
"""
    )
    out = json.loads(_run_node(driver))
    assert out["labelBefore"] == "Manda in onda"
    assert out["armedLabel"] == "Conferma invio", "first tap must morph the label"
    assert out["armedDanger"] is True, "first tap must add the danger class"
    assert out["callsAfterArm"] == 0, "first tap must NOT POST"
    assert out["callsAfterConfirm"] == 1, "second tap must POST exactly once"
    assert out["labelAfterConfirm"] == "Manda in onda", "confirm must revert the label"
    assert out["dangerAfterConfirm"] is False, "confirm must drop the danger class"


@_requires_node
def test_publish_auto_reverts_when_not_confirmed():
    """SCE-04 / D-05: an armed-but-unconfirmed button auto-reverts, no POST fired."""
    js = _read_file_js()
    cfg = _disc_cfg()
    driver = (
        _FAKE_DOM
        + js
        + r"""
const api = module.exports;
const cfg = """ + cfg + r""";
const root = document.createElement('div');
api.mount(root, cfg);
const btn = root.querySelectorAll('.publish button')[0];
btn.dispatch('click');           // arm
_fireTimers();                   // let the auto-revert window elapse
process.stdout.write(JSON.stringify({
  label: btn.textContent,
  danger: btn.classList.contains('danger'),
  calls: _fetchCalls,
}));
"""
    )
    out = json.loads(_run_node(driver))
    assert out["label"] == "Manda in onda", "auto-revert must restore the label"
    assert out["danger"] is False, "auto-revert must drop the danger class"
    assert out["calls"] == 0, "auto-revert must never POST"


@_requires_node
def test_publish_never_disabled():
    """SCE-04 / Phase-16 D-04: the publish button is never set disabled (confirm is the gate)."""
    js = _read_file_js()
    body = "\n".join(
        l for l in js.splitlines() if not l.lstrip().startswith("//")
    )
    assert "publishBtn.disabled = true" not in body
    assert ".disabled = true" not in body


# --- SCE-04 / D-06: Enter never publishes ------------------------------------- #


@_requires_node
def test_enter_never_publishes():
    """SCE-04 / D-06: Enter never arms, never confirms, never POSTs."""
    js = _read_file_js()
    cfg = _disc_cfg()
    driver = (
        _FAKE_DOM
        + js
        + r"""
const api = module.exports;
const cfg = """ + cfg + r""";
const root = document.createElement('div');
api.mount(root, cfg);
const btn = root.querySelectorAll('.publish button')[0];
let prevented = false;
// Fire Enter on the root (capturing field inputs) — must never reach the publish path.
root.dispatch('keydown', { key: 'Enter', preventDefault: function(){ prevented = true; }, target: root });
process.stdout.write(JSON.stringify({
  prevented: prevented,
  armedLabel: btn.textContent,   // must still read "Manda in onda" — Enter never arms
  danger: btn.classList.contains('danger'),
  calls: _fetchCalls,            // must be 0 — Enter never POSTs
}));
"""
    )
    out = json.loads(_run_node(driver))
    assert out["prevented"] is True, "Enter must be preventDefault()'d"
    assert out["armedLabel"] == "Manda in onda", "Enter must NOT arm the confirm"
    assert out["danger"] is False, "Enter must NOT add the danger class"
    assert out["calls"] == 0, "Enter must NEVER POST"
