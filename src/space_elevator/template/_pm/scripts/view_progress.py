#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


PM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROGRESS_PATH = PM_ROOT / "progress.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18480

PROGRESS_PATH = DEFAULT_PROGRESS_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve a local HTML view for `_pm/progress.json`."
    )
    parser.add_argument(
        "--progress-file",
        type=Path,
        default=DEFAULT_PROGRESS_PATH,
        help="Path to the roadmap JSON file. Defaults to _pm/progress.json.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Host interface to bind. Defaults to {DEFAULT_HOST}.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"TCP port to bind. Defaults to {DEFAULT_PORT}.",
    )
    return parser.parse_args()


def load_progress() -> dict:
    return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))


def task_scope(task: dict) -> list[str]:
    return task.get("scope") or task.get("crate_scope") or []


def flatten_rows(progress: dict) -> list[dict]:
    workstreams = {item["id"]: item for item in progress.get("workstreams", [])}
    rows: list[dict] = []

    for phase_index, phase in enumerate(progress.get("phases", []), start=1):
        tasks = phase.get("tasks", [])
        phase_id = phase.get("id", "")
        phase_name = phase.get("name", "")
        phase_status = phase.get("status", "todo")

        if not tasks:
            rows.append(
                {
                    "kind": "phase",
                    "id": phase_id,
                    "phase_id": phase_id,
                    "phase_name": phase_name,
                    "phase_index": phase_index,
                    "status": phase_status,
                    "title": phase_name,
                    "description": phase.get("description", ""),
                    "workstream": "",
                    "workstream_name": "",
                    "scope": [],
                    "depends_on": [],
                    "done_when": phase.get("exit_criteria", []),
                }
            )
            continue

        for task_index, task in enumerate(tasks, start=1):
            stream = workstreams.get(task.get("workstream", ""), {})
            rows.append(
                {
                    "kind": "task",
                    "id": task.get("id", f"{phase_id}-T{task_index:02d}"),
                    "phase_id": phase_id,
                    "phase_name": phase_name,
                    "phase_index": phase_index,
                    "status": task.get("status", "todo"),
                    "title": task.get("title", ""),
                    "description": task.get("description", ""),
                    "workstream": task.get("workstream", ""),
                    "workstream_name": stream.get("name", ""),
                    "scope": task_scope(task),
                    "depends_on": task.get("depends_on", []),
                    "done_when": task.get("done_when", []),
                    "artifacts": task.get("artifacts", []),
                }
            )
    return rows


def build_page(port: int) -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Project Progress</title>
  <style>
    :root {
      --bg: #f7f6f3;
      --panel: #ffffff;
      --line: #e7e5df;
      --text: #2f3437;
      --muted: #6b6f76;
      --soft: #f1efe9;
      --shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px rgba(15, 23, 42, 0.06);
      --todo: #787774;
      --progress: #0f7b6c;
      --blocked: #c4554d;
      --review: #8f6b00;
      --done: #448361;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, #fffdf7 0, #fffdf7 220px, transparent 221px),
        linear-gradient(180deg, #fbfaf7 0%, var(--bg) 100%);
    }
    .page {
      max-width: 1440px;
      margin: 0 auto;
      padding: 32px 24px 64px;
    }
    .hero {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 20px;
      align-items: stretch;
      margin-bottom: 24px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
    }
    .hero-main {
      padding: 26px 28px;
    }
    h1 {
      margin: 0 0 6px;
      font-size: 34px;
      line-height: 1.05;
      letter-spacing: -0.04em;
    }
    .subtitle {
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 18px;
    }
    .meta {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      background: var(--soft);
      border: 1px solid var(--line);
      border-radius: 999px;
      font-size: 12px;
      color: var(--muted);
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      padding: 20px;
    }
    .stat {
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: linear-gradient(180deg, #fff 0%, #faf9f5 100%);
    }
    .stat-label {
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .stat-value {
      font-size: 30px;
      line-height: 1;
      letter-spacing: -0.04em;
    }
    .section-title {
      margin: 0 0 12px;
      font-size: 16px;
      letter-spacing: -0.02em;
    }
    .phase-strip {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .phase-card {
      padding: 14px;
      cursor: pointer;
      transition: transform 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
    }
    .phase-card:hover {
      transform: translateY(-1px);
      border-color: #d5d1c7;
    }
    .phase-card.active {
      border-color: #8a8578;
      box-shadow: 0 0 0 3px rgba(138, 133, 120, 0.12);
    }
    .phase-name {
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 10px;
      line-height: 1.3;
    }
    .phase-meta {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: center;
      font-size: 12px;
      color: var(--muted);
    }
    .toolbar {
      display: grid;
      grid-template-columns: 1.2fr repeat(3, minmax(160px, 0.35fr));
      gap: 12px;
      margin-bottom: 14px;
    }
    .field {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .field label {
      font-size: 12px;
      color: var(--muted);
    }
    input, select {
      width: 100%;
      appearance: none;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      font: inherit;
    }
    .db {
      overflow: hidden;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }
    th {
      background: #faf9f6;
      color: var(--muted);
      font-weight: 600;
      font-size: 12px;
    }
    tbody tr:hover {
      background: #fcfbf8;
    }
    .title {
      font-weight: 600;
      margin-bottom: 4px;
      line-height: 1.35;
    }
    .subtle {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }
    .tag-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .tag {
      display: inline-flex;
      align-items: center;
      padding: 4px 8px;
      border-radius: 999px;
      background: var(--soft);
      color: var(--text);
      border: 1px solid var(--line);
      font-size: 11px;
      line-height: 1;
      white-space: nowrap;
    }
    .status {
      display: inline-flex;
      align-items: center;
      padding: 5px 9px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.02em;
      text-transform: uppercase;
      border: 1px solid transparent;
    }
    .status.todo { color: var(--todo); background: #f1efea; border-color: #e4dfd7; }
    .status.in_progress { color: var(--progress); background: #e8f5f2; border-color: #c4e6df; }
    .status.blocked { color: var(--blocked); background: #fbe9e7; border-color: #f3c5bf; }
    .status.ready_for_review { color: var(--review); background: #fbf3db; border-color: #ebd79a; }
    .status.done { color: var(--done); background: #ebf5ee; border-color: #cde3d5; }
    .empty {
      padding: 40px 18px;
      color: var(--muted);
      text-align: center;
    }
    .footer {
      color: var(--muted);
      font-size: 12px;
      margin-top: 12px;
    }
    @media (max-width: 1080px) {
      .hero { grid-template-columns: 1fr; }
      .toolbar { grid-template-columns: 1fr 1fr; }
      table { display: block; overflow-x: auto; }
    }
    @media (max-width: 720px) {
      .page { padding: 20px 14px 48px; }
      .toolbar { grid-template-columns: 1fr; }
      .stats { grid-template-columns: 1fr 1fr; }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div class="card hero-main">
        <h1 id="hero-title">Project Progress</h1>
        <div class="subtitle">A local execution view for <code>_pm/progress.json</code></div>
        <div class="meta">
          <div class="pill"><strong>Project</strong><span id="project"></span></div>
          <div class="pill"><strong>Mode</strong><span id="planning-mode"></span></div>
          <div class="pill"><strong>Updated</strong><span id="last-updated"></span></div>
        </div>
      </div>
      <div class="card stats">
        <div class="stat">
          <div class="stat-label">Phases</div>
          <div class="stat-value" id="phase-count">0</div>
        </div>
        <div class="stat">
          <div class="stat-label">Tasks</div>
          <div class="stat-value" id="task-count">0</div>
        </div>
        <div class="stat">
          <div class="stat-label">In Progress</div>
          <div class="stat-value" id="progress-count">0</div>
        </div>
        <div class="stat">
          <div class="stat-label">Done</div>
          <div class="stat-value" id="done-count">0</div>
        </div>
      </div>
    </div>

    <h2 class="section-title">Phases</h2>
    <div class="phase-strip" id="phase-strip"></div>

    <h2 class="section-title">Database</h2>
    <div class="toolbar">
      <div class="field">
        <label for="search">Search</label>
        <input id="search" type="search" placeholder="Search title, description, task id, scope, dependency">
      </div>
      <div class="field">
        <label for="status-filter">Status</label>
        <select id="status-filter">
          <option value="">All statuses</option>
        </select>
      </div>
      <div class="field">
        <label for="workstream-filter">Workstream</label>
        <select id="workstream-filter">
          <option value="">All workstreams</option>
        </select>
      </div>
      <div class="field">
        <label for="kind-filter">Kind</label>
        <select id="kind-filter">
          <option value="">All rows</option>
          <option value="task">Tasks</option>
          <option value="phase">Phase-only rows</option>
        </select>
      </div>
    </div>

    <div class="card db">
      <table>
        <thead>
          <tr>
            <th style="width: 14%">Name</th>
            <th style="width: 8%">ID</th>
            <th style="width: 10%">Phase</th>
            <th style="width: 9%">Status</th>
            <th style="width: 10%">Workstream</th>
            <th style="width: 17%">Description</th>
            <th style="width: 14%">Scope</th>
            <th style="width: 8%">Depends On</th>
            <th style="width: 10%">Done When</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
      <div class="empty" id="empty" hidden>No rows match the current filters.</div>
    </div>

    <div class="footer">Served by <code>_pm/scripts/view_progress.py</code> on port __PORT__.</div>
  </div>

  <script>
    const state = {
      progress: null,
      rows: [],
      activePhase: "",
    };

    const els = {
      heroTitle: document.getElementById("hero-title"),
      project: document.getElementById("project"),
      planningMode: document.getElementById("planning-mode"),
      lastUpdated: document.getElementById("last-updated"),
      phaseCount: document.getElementById("phase-count"),
      taskCount: document.getElementById("task-count"),
      progressCount: document.getElementById("progress-count"),
      doneCount: document.getElementById("done-count"),
      phaseStrip: document.getElementById("phase-strip"),
      rows: document.getElementById("rows"),
      empty: document.getElementById("empty"),
      search: document.getElementById("search"),
      statusFilter: document.getElementById("status-filter"),
      workstreamFilter: document.getElementById("workstream-filter"),
      kindFilter: document.getElementById("kind-filter"),
    };

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[ch]));
    }

    function uniq(values) {
      return [...new Set(values.filter(Boolean))].sort();
    }

    function statusPill(status) {
      return `<span class="status ${escapeHtml(status)}">${escapeHtml(status.replaceAll("_", " "))}</span>`;
    }

    function renderTags(values) {
      if (!values || values.length === 0) return '<span class="subtle">-</span>';
      return `<div class="tag-list">${values.map((value) => `<span class="tag">${escapeHtml(value)}</span>`).join("")}</div>`;
    }

    function rowSearchText(row) {
      return [
        row.id,
        row.title,
        row.description,
        row.phase_id,
        row.phase_name,
        row.status,
        row.workstream,
        row.workstream_name,
        ...(row.scope || []),
        ...(row.depends_on || []),
        ...(row.done_when || []),
      ].join(" ").toLowerCase();
    }

    function applyFilters() {
      const search = els.search.value.trim().toLowerCase();
      const status = els.statusFilter.value;
      const workstream = els.workstreamFilter.value;
      const kind = els.kindFilter.value;

      const filtered = state.rows.filter((row) => {
        if (state.activePhase && row.phase_id !== state.activePhase) return false;
        if (status && row.status !== status) return false;
        if (workstream && row.workstream !== workstream) return false;
        if (kind && row.kind !== kind) return false;
        if (search && !rowSearchText(row).includes(search)) return false;
        return true;
      });

      renderRows(filtered);
      renderPhaseCards();
    }

    function renderRows(rows) {
      els.rows.innerHTML = rows.map((row) => `
        <tr>
          <td>
            <div class="title">${escapeHtml(row.title || row.phase_name)}</div>
            <div class="subtle">${escapeHtml(row.kind === "task" ? "Task" : "Phase row")}</div>
          </td>
          <td><code>${escapeHtml(row.id)}</code></td>
          <td>
            <div class="title">${escapeHtml(row.phase_id)}</div>
            <div class="subtle">${escapeHtml(row.phase_name)}</div>
          </td>
          <td>${statusPill(row.status)}</td>
          <td>${row.workstream ? `<div class="title">${escapeHtml(row.workstream)}</div><div class="subtle">${escapeHtml(row.workstream_name || "")}</div>` : '<span class="subtle">-</span>'}</td>
          <td>${row.description ? `<div class="subtle">${escapeHtml(row.description)}</div>` : '<span class="subtle">-</span>'}</td>
          <td>${renderTags(row.scope)}</td>
          <td>${renderTags(row.depends_on)}</td>
          <td>${renderTags((row.done_when || []).slice(0, 3))}</td>
        </tr>
      `).join("");

      const hasRows = rows.length > 0;
      els.empty.hidden = hasRows;
      document.querySelector("table").hidden = !hasRows;
    }

    function renderPhaseCards() {
      const phases = state.progress.phases || [];
      els.phaseStrip.innerHTML = phases.map((phase) => {
        const rows = state.rows.filter((row) => row.phase_id === phase.id && row.kind === "task");
        const done = rows.filter((row) => row.status === "done").length;
        const active = state.activePhase === phase.id ? "active" : "";
        return `
          <div class="card phase-card ${active}" data-phase-id="${escapeHtml(phase.id)}">
            <div class="phase-name">${escapeHtml(phase.id)} · ${escapeHtml(phase.name)}</div>
            <div class="phase-meta">
              ${statusPill(phase.status)}
              <span>${done}/${rows.length || 0} done</span>
            </div>
          </div>
        `;
      }).join("");

      els.phaseStrip.querySelectorAll(".phase-card").forEach((node) => {
        node.addEventListener("click", () => {
          const phaseId = node.dataset.phaseId || "";
          state.activePhase = state.activePhase === phaseId ? "" : phaseId;
          applyFilters();
        });
      });
    }

    function populateFilters() {
      uniq(state.rows.map((row) => row.status)).forEach((value) => {
        els.statusFilter.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`);
      });
      uniq(state.rows.map((row) => row.workstream)).forEach((value) => {
        els.workstreamFilter.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`);
      });
    }

    function renderSummary() {
      const phases = state.progress.phases || [];
      const tasks = state.rows.filter((row) => row.kind === "task");
      const project = state.progress.project || "Project";
      els.heroTitle.textContent = `${project} progress`;
      document.title = `${project} progress`;
      els.project.textContent = project;
      els.planningMode.textContent = state.progress.planning_mode || "-";
      els.lastUpdated.textContent = state.progress.last_updated || "-";
      els.phaseCount.textContent = String(phases.length);
      els.taskCount.textContent = String(tasks.length);
      els.progressCount.textContent = String(tasks.filter((row) => row.status === "in_progress").length);
      els.doneCount.textContent = String(tasks.filter((row) => row.status === "done").length);
    }

    async function init() {
      const response = await fetch("/api/progress");
      const progress = await response.json();
      state.progress = progress;
      state.rows = progress.rows || [];

      renderSummary();
      populateFilters();
      renderPhaseCards();
      applyFilters();

      [els.search, els.statusFilter, els.workstreamFilter, els.kindFilter].forEach((el) => {
        el.addEventListener("input", applyFilters);
        el.addEventListener("change", applyFilters);
      });
    }

    init().catch((error) => {
      document.body.innerHTML = `<pre style="padding:24px;color:#c4554d">Failed to load progress data\\n\\n${escapeHtml(error.message || String(error))}</pre>`;
    });
  </script>
</body>
</html>
""".replace("__PORT__", str(port))


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = build_page(self.server.server_port).encode("utf-8")
            self._send(HTTPStatus.OK, body, "text/html; charset=utf-8")
            return

        if parsed.path == "/api/progress":
            try:
                progress = load_progress()
                progress["rows"] = flatten_rows(progress)
                body = json.dumps(progress, ensure_ascii=False).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json; charset=utf-8")
            except FileNotFoundError:
                body = json.dumps({"error": f"Missing {PROGRESS_PATH}"}).encode("utf-8")
                self._send(HTTPStatus.NOT_FOUND, body, "application/json; charset=utf-8")
            return

        if parsed.path == "/health":
            self._send(HTTPStatus.OK, b"ok", "text/plain; charset=utf-8")
            return

        self._send(
            HTTPStatus.NOT_FOUND,
            json.dumps({"error": "Not found"}).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    global PROGRESS_PATH

    args = parse_args()
    PROGRESS_PATH = args.progress_file.resolve()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Progress viewer: http://{args.host}:{args.port}")
    print(f"Roadmap file: {PROGRESS_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
