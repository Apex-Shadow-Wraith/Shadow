"""Real-Time Introspection Dashboard for Shadow.

Provides a local-network web dashboard showing Shadow's internal state
during operation. Uses Python's built-in HTTP server — no external
dependencies. Read-only, auto-refreshing, dark theme.
"""

import json
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

logger = logging.getLogger("shadow.introspection_dashboard")

MODULE_CODENAMES = [
    "shadow", "wraith", "cerberus", "apex", "grimoire",
    "sentinel", "harbinger", "reaper", "cipher", "omen",
    "nova", "morpheus",
]


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the introspection dashboard."""

    dashboard = None  # Set by IntrospectionDashboard before server starts

    def do_GET(self):
        """Handle GET requests for dashboard endpoints."""
        if self.path == "/":
            self._respond(200, "text/html", self.dashboard.render_dashboard())
        elif self.path == "/api/state":
            data = self.dashboard.get_dashboard_data()
            self._respond(200, "application/json", json.dumps(data))
        elif self.path == "/api/health":
            uptime = time.time() - self.dashboard._start_time if self.dashboard._start_time else 0
            payload = {"status": "ok", "uptime": round(uptime, 2)}
            self._respond(200, "application/json", json.dumps(payload))
        else:
            self._respond(404, "application/json", json.dumps({"error": "not found"}))

    def _respond(self, code: int, content_type: str, body: str):
        """Send an HTTP response."""
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass


class IntrospectionDashboard:
    """Real-time web dashboard for Shadow's internal state.

    Runs a lightweight HTTP server in a daemon thread, serving a
    self-contained HTML page that auto-refreshes every 5 seconds.

    Args:
        host: Bind address. Defaults to 0.0.0.0 (all interfaces).
        port: Listen port. Defaults to 8377.
        orchestrator: Reference to Shadow's Orchestrator for live state.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8377, orchestrator=None):
        self.host = host
        self.port = port
        self.orchestrator = orchestrator
        self._server = None
        self._thread = None
        self._start_time = None

    def start(self) -> bool:
        """Start the dashboard server in a background daemon thread.

        Returns:
            True if the server started successfully, False otherwise.
        """
        try:
            DashboardHandler.dashboard = self
            self._server = HTTPServer((self.host, self.port), DashboardHandler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            self._start_time = time.time()
            logger.info(f"Introspection dashboard available at http://localhost:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start introspection dashboard: {e}")
            return False

    def stop(self) -> bool:
        """Gracefully stop the dashboard server.

        Returns:
            True if the server stopped successfully, False otherwise.
        """
        try:
            if self._server:
                self._server.shutdown()
                self._server.server_close()
                self._server = None
                self._thread = None
                self._start_time = None
                logger.info("Introspection dashboard stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop introspection dashboard: {e}")
            return False

    def get_dashboard_data(self) -> dict:
        """Aggregate current state from all available subsystems.

        Returns:
            Dictionary with module_states, operational_state, context_window,
            confidence, recent_tasks, grimoire_stats, active_lora, and
            retry_engine sections. Returns safe defaults when subsystems
            are unavailable.
        """
        data = {
            "timestamp": time.time(),
            "module_states": self._get_module_states(),
            "operational_state": self._get_operational_state(),
            "context_window": self._get_context_window(),
            "confidence": self._get_confidence(),
            "recent_tasks": self._get_recent_tasks(),
            "grimoire_stats": self._get_grimoire_stats(),
            "active_lora": self._get_active_lora(),
            "retry_engine": self._get_retry_engine(),
        }
        return data

    def _get_module_states(self) -> dict:
        """Get status for all 13 modules from the registry."""
        default = {name: {"status": "unknown", "current_task": None} for name in MODULE_CODENAMES}
        if not self.orchestrator:
            return default
        try:
            registry = getattr(self.orchestrator, "registry", None)
            if not registry:
                return default
            modules_info = registry.list_modules()
            states = {}
            for info in modules_info:
                name = info.get("name", "")
                states[name] = {
                    "status": info.get("status", "unknown"),
                    "current_task": info.get("current_task", None),
                }
            # Fill in any missing modules
            for name in MODULE_CODENAMES:
                if name not in states:
                    states[name] = {"status": "unknown", "current_task": None}
            return states
        except Exception:
            return default

    def _get_operational_state(self) -> dict:
        """Get frustration, momentum, curiosity, fatigue, health."""
        default = {
            "frustration": 0.0,
            "confidence_momentum": 0.0,
            "curiosity": 0.0,
            "fatigue": 0.0,
            "overall_health": 0.0,
        }
        if not self.orchestrator:
            return default
        try:
            op_state = getattr(self.orchestrator, "operational_state", None)
            if not op_state:
                return default
            snapshot = op_state.get_current_state()
            return {
                "frustration": snapshot.frustration,
                "confidence_momentum": snapshot.confidence_momentum,
                "curiosity": snapshot.curiosity,
                "fatigue": snapshot.fatigue,
                "overall_health": snapshot.overall_health,
            }
        except Exception:
            return default

    def _get_context_window(self) -> dict:
        """Get context profiler token usage stats."""
        default = {
            "last_usage_percent": 0.0,
            "avg_usage_percent": 0.0,
            "tokens_used": 0,
            "token_limit": 128000,
        }
        if not self.orchestrator:
            return default
        try:
            profiler = getattr(self.orchestrator, "context_profiler", None)
            if not profiler:
                return default
            stats = profiler.get_usage_stats() if hasattr(profiler, "get_usage_stats") else None
            if stats:
                return {
                    "last_usage_percent": stats.get("last_usage_percent", 0.0),
                    "avg_usage_percent": stats.get("avg_usage_percent", 0.0),
                    "tokens_used": stats.get("tokens_used", 0),
                    "token_limit": stats.get("token_limit", 128000),
                }
            return default
        except Exception:
            return default

    def _get_confidence(self) -> dict:
        """Get confidence calibration metrics."""
        default = {"calibration_error": 0.0, "direction": "unknown"}
        if not self.orchestrator:
            return default
        try:
            calibrator = getattr(self.orchestrator, "confidence_calibrator", None)
            if not calibrator:
                return default
            if hasattr(calibrator, "get_calibration_summary"):
                summary = calibrator.get_calibration_summary()
                return {
                    "calibration_error": summary.get("calibration_error", 0.0),
                    "direction": summary.get("direction", "unknown"),
                }
            return default
        except Exception:
            return default

    def _get_recent_tasks(self) -> list:
        """Get the last 10 tasks from the task tracker."""
        if not self.orchestrator:
            return []
        try:
            tracker = getattr(self.orchestrator, "_task_tracker", None)
            if tracker and hasattr(tracker, "get_recent"):
                return tracker.get_recent(limit=10)
            scorer = getattr(self.orchestrator, "confidence_scorer", None)
            if scorer and hasattr(scorer, "get_scoring_history"):
                history = scorer.get_scoring_history(limit=10)
                return [
                    {
                        "task": entry.get("task", ""),
                        "module": entry.get("module", ""),
                        "confidence": entry.get("confidence", 0.0),
                        "duration": entry.get("duration", 0.0),
                        "success": entry.get("success", False),
                    }
                    for entry in history
                ]
            return []
        except Exception:
            return []

    def _get_grimoire_stats(self) -> dict:
        """Get memory system statistics."""
        default = {"total_entries": 0, "recent_queries": 0, "avg_relevance": 0.0}
        if not self.orchestrator:
            return default
        try:
            registry = getattr(self.orchestrator, "registry", None)
            if not registry:
                return default
            grimoire = registry.get_module("grimoire")
            if grimoire and hasattr(grimoire, "get_stats"):
                stats = grimoire.get_stats()
                return {
                    "total_entries": stats.get("total_entries", 0),
                    "recent_queries": stats.get("recent_queries", 0),
                    "avg_relevance": stats.get("avg_relevance", 0.0),
                }
            return default
        except Exception:
            return default

    def _get_active_lora(self) -> str:
        """Get the currently active LoRA adapter name."""
        if not self.orchestrator:
            return "none"
        try:
            lora_mgr = getattr(self.orchestrator, "lora_manager", None)
            if lora_mgr and hasattr(lora_mgr, "get_active"):
                return lora_mgr.get_active() or "none"
            return "none"
        except Exception:
            return "none"

    def _get_retry_engine(self) -> dict:
        """Get retry/escalation engine status."""
        default = {"active_sessions": 0, "recent_escalations": 0}
        if not self.orchestrator:
            return default
        try:
            retry = getattr(self.orchestrator, "retry_engine", None)
            if retry and hasattr(retry, "get_status"):
                status = retry.get_status()
                return {
                    "active_sessions": status.get("active_sessions", 0),
                    "recent_escalations": status.get("recent_escalations", 0),
                }
            return default
        except Exception:
            return default

    def render_dashboard(self) -> str:
        """Return a self-contained HTML page for the introspection dashboard.

        The page uses inline CSS (dark theme, black-on-gold color scheme)
        and JavaScript that auto-refreshes state every 5 seconds via
        fetch() to /api/state. No external dependencies.

        Returns:
            Complete HTML string.
        """
        return _DASHBOARD_HTML


# ---------------------------------------------------------------------------
# Self-contained HTML dashboard — inline CSS + JS, no external dependencies
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shadow — Introspection Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#d4af37;font-family:'Segoe UI',Consolas,monospace;min-height:100vh}
a{color:#d4af37}

/* Top bar */
.topbar{display:flex;justify-content:space-between;align-items:center;padding:12px 24px;background:#111;border-bottom:2px solid #d4af37}
.topbar h1{font-size:1.4rem;letter-spacing:2px}
.topbar .health-dot{width:14px;height:14px;border-radius:50%;display:inline-block;margin-right:8px;vertical-align:middle}
.topbar .meta{font-size:.85rem;color:#aaa}

/* Layout */
.container{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px;max-width:1400px;margin:0 auto}
.full-width{grid-column:1/-1}

/* Cards */
.card{background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:16px}
.card h2{font-size:1rem;color:#d4af37;margin-bottom:12px;border-bottom:1px solid #2a2a2a;padding-bottom:6px}

/* Module grid */
.module-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px}
.module-box{background:#1a1a1a;border:1px solid #333;border-radius:6px;padding:10px;text-align:center;font-size:.82rem}
.module-box .name{font-weight:700;text-transform:uppercase;letter-spacing:1px}
.module-box .status{margin-top:4px;font-size:.75rem}
.module-box.idle{border-color:#555}
.module-box.online{border-color:#3a7;color:#3a7}
.module-box.busy{border-color:#d4af37;color:#d4af37}
.module-box.error{border-color:#c44;color:#c44}
.module-box.unknown{border-color:#555;color:#777}

/* Gauges */
.gauge-row{display:flex;gap:16px;flex-wrap:wrap}
.gauge{flex:1;min-width:120px}
.gauge .label{font-size:.78rem;color:#aaa;margin-bottom:4px}
.gauge .bar-bg{height:10px;background:#222;border-radius:5px;overflow:hidden}
.gauge .bar-fill{height:100%;border-radius:5px;transition:width .6s ease}
.gauge .value{font-size:.75rem;color:#ccc;margin-top:2px;text-align:right}

/* Context bar */
.ctx-bar-bg{height:18px;background:#222;border-radius:9px;overflow:hidden;margin-top:6px}
.ctx-bar-fill{height:100%;border-radius:9px;transition:width .6s ease;text-align:center;font-size:.7rem;line-height:18px;color:#000;font-weight:700}

/* Task list */
.task-list{max-height:260px;overflow-y:auto}
.task-item{display:flex;justify-content:space-between;padding:6px 8px;border-bottom:1px solid #1e1e1e;font-size:.8rem}
.task-item:hover{background:#1a1a1a}
.task-item .mod{color:#d4af37;min-width:80px}
.task-item .conf{min-width:50px;text-align:right}
.task-item .ok{color:#3a7}
.task-item .fail{color:#c44}

/* Alerts */
.alert{padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:.82rem}
.alert.warn{background:#3a2f00;border:1px solid #d4af37}
.alert.crit{background:#3a0000;border:1px solid #c44}
.alert.ok{background:#0a2a10;border:1px solid #3a7}

/* Info row */
.info-row{display:flex;justify-content:space-between;font-size:.85rem;padding:4px 0}
.info-row .lbl{color:#888}
</style>
</head>
<body>

<div class="topbar">
  <div><span class="health-dot" id="health-dot"></span><h1 style="display:inline">SHADOW INTROSPECTION</h1></div>
  <div class="meta">
    <span id="uptime">--</span> uptime &nbsp;|&nbsp; refreshing every 5s
  </div>
</div>

<div class="container">

  <!-- Module Grid -->
  <div class="card full-width">
    <h2>Module Status</h2>
    <div class="module-grid" id="module-grid"></div>
  </div>

  <!-- Operational State -->
  <div class="card">
    <h2>Operational State</h2>
    <div class="gauge-row" id="gauges"></div>
  </div>

  <!-- Context Window -->
  <div class="card">
    <h2>Context Window</h2>
    <div id="ctx-info"></div>
    <div class="ctx-bar-bg"><div class="ctx-bar-fill" id="ctx-bar"></div></div>
  </div>

  <!-- Recent Tasks -->
  <div class="card">
    <h2>Recent Tasks</h2>
    <div class="task-list" id="task-list"></div>
  </div>

  <!-- Alerts & Info -->
  <div class="card">
    <h2>Alerts &amp; Info</h2>
    <div id="alerts"></div>
    <div style="margin-top:10px">
      <div class="info-row"><span class="lbl">Confidence calibration</span><span id="cal-err">--</span></div>
      <div class="info-row"><span class="lbl">Active LoRA</span><span id="lora">--</span></div>
      <div class="info-row"><span class="lbl">Retry sessions</span><span id="retry-sessions">0</span></div>
      <div class="info-row"><span class="lbl">Recent escalations</span><span id="retry-esc">0</span></div>
      <div class="info-row"><span class="lbl">Grimoire entries</span><span id="grim-total">--</span></div>
      <div class="info-row"><span class="lbl">Grimoire queries</span><span id="grim-queries">--</span></div>
      <div class="info-row"><span class="lbl">Avg relevance</span><span id="grim-rel">--</span></div>
    </div>
  </div>

</div>

<script>
const MODULES = ["shadow","wraith","cerberus","apex","grimoire","sentinel","harbinger","reaper","cipher","omen","nova","morpheus"];

function healthColor(v){if(v>=0.75)return"#3a7";if(v>=0.45)return"#d4af37";return"#c44"}
function pct(v){return Math.round(v*100)}
function fmtUptime(s){var h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=Math.floor(s%60);return(h?h+"h ":"")+m+"m "+sec+"s"}

function render(d){
  // Health dot
  var oh=d.operational_state.overall_health||0;
  var dot=document.getElementById("health-dot");
  dot.style.background=healthColor(oh);

  // Module grid
  var grid=document.getElementById("module-grid");
  grid.innerHTML="";
  MODULES.forEach(function(m){
    var info=d.module_states[m]||{status:"unknown",current_task:null};
    var cls="module-box "+(info.status||"unknown");
    var task=info.current_task?" — "+info.current_task:"";
    grid.innerHTML+='<div class="'+cls+'"><div class="name">'+m+'</div><div class="status">'+info.status+task+'</div></div>';
  });

  // Gauges
  var gs=d.operational_state;
  var gauges=[
    {label:"Frustration",val:gs.frustration,color:"#c44"},
    {label:"Confidence Momentum",val:gs.confidence_momentum,color:"#3a7"},
    {label:"Curiosity",val:gs.curiosity,color:"#6af"},
    {label:"Fatigue",val:gs.fatigue,color:"#d4af37"},
    {label:"Overall Health",val:gs.overall_health,color:healthColor(gs.overall_health)}
  ];
  var gEl=document.getElementById("gauges");
  gEl.innerHTML="";
  gauges.forEach(function(g){
    gEl.innerHTML+='<div class="gauge"><div class="label">'+g.label+'</div><div class="bar-bg"><div class="bar-fill" style="width:'+pct(g.val)+'%;background:'+g.color+'"></div></div><div class="value">'+g.val.toFixed(2)+'</div></div>';
  });

  // Context window
  var cw=d.context_window;
  var cwPct=cw.last_usage_percent||0;
  document.getElementById("ctx-info").innerHTML='<div class="info-row"><span class="lbl">Tokens</span><span>'+cw.tokens_used.toLocaleString()+" / "+cw.token_limit.toLocaleString()+'</span></div><div class="info-row"><span class="lbl">Avg usage</span><span>'+cw.avg_usage_percent.toFixed(1)+'%</span></div>';
  var bar=document.getElementById("ctx-bar");
  bar.style.width=cwPct+"%";
  bar.style.background=cwPct>85?"#c44":cwPct>60?"#d4af37":"#3a7";
  bar.textContent=cwPct.toFixed(1)+"%";

  // Recent tasks
  var tl=document.getElementById("task-list");
  tl.innerHTML="";
  (d.recent_tasks||[]).forEach(function(t){
    var cls=t.success?"ok":"fail";
    tl.innerHTML+='<div class="task-item"><span class="mod">'+t.module+'</span><span style="flex:1;color:#aaa;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:0 8px">'+t.task+'</span><span class="conf '+cls+'">'+((t.confidence||0)*100).toFixed(0)+'%</span></div>';
  });
  if(!d.recent_tasks||!d.recent_tasks.length) tl.innerHTML='<div style="color:#555;font-size:.8rem">No recent tasks</div>';

  // Alerts
  var alerts=[];
  if(gs.fatigue>0.7) alerts.push({cls:"crit",msg:"High fatigue: "+gs.fatigue.toFixed(2)+" — consider cooldown"});
  if(gs.frustration>0.5) alerts.push({cls:"warn",msg:"Elevated frustration: "+gs.frustration.toFixed(2)});
  if(cwPct>85) alerts.push({cls:"warn",msg:"Context window usage high: "+cwPct.toFixed(1)+"%"});
  if(oh<0.45) alerts.push({cls:"crit",msg:"Overall health critical: "+oh.toFixed(2)});
  if(!alerts.length) alerts.push({cls:"ok",msg:"All systems nominal"});
  var aEl=document.getElementById("alerts");
  aEl.innerHTML="";
  alerts.forEach(function(a){aEl.innerHTML+='<div class="alert '+a.cls+'">'+a.msg+'</div>'});

  // Info
  document.getElementById("cal-err").textContent=d.confidence.calibration_error.toFixed(3)+" ("+d.confidence.direction+")";
  document.getElementById("lora").textContent=d.active_lora;
  document.getElementById("retry-sessions").textContent=d.retry_engine.active_sessions;
  document.getElementById("retry-esc").textContent=d.retry_engine.recent_escalations;
  document.getElementById("grim-total").textContent=d.grimoire_stats.total_entries.toLocaleString();
  document.getElementById("grim-queries").textContent=d.grimoire_stats.recent_queries;
  document.getElementById("grim-rel").textContent=d.grimoire_stats.avg_relevance.toFixed(2);
}

function refresh(){
  fetch("/api/state").then(function(r){return r.json()}).then(render).catch(function(){});
  fetch("/api/health").then(function(r){return r.json()}).then(function(h){
    document.getElementById("uptime").textContent=fmtUptime(h.uptime);
  }).catch(function(){});
}

refresh();
setInterval(refresh,5000);
</script>
</body>
</html>"""
