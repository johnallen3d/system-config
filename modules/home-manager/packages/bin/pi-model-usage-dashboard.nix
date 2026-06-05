{pkgs, ...}:
pkgs.writeShellScriptBin "pi-model-usage-dashboard" ''
  exec ${pkgs.python3}/bin/python3 - "$@" <<'PY'
import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pi-model-usage-dashboard",
        description="Build local HTML dashboard from pi-model-usage JSON output.",
    )
    parser.add_argument(
        "--profile",
        choices=["both", "personal", "work", "auto"],
        default="both",
        help="Profile scope to load (default: both).",
    )
    parser.add_argument(
        "--repo",
        help="Optional repo path filter passed through to pi-model-usage.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Recent sessions to load per profile (default: 50).",
    )
    parser.add_argument(
        "--output",
        help="Write HTML to this path instead of temp file.",
    )
    parser.add_argument(
        "--open",
        dest="open_browser",
        action="store_true",
        default=True,
        help="Open generated dashboard in browser (default).",
    )
    parser.add_argument(
        "--no-open",
        dest="open_browser",
        action="store_false",
        help="Do not open browser; only write HTML.",
    )
    return parser.parse_args()


def run_usage(profile: str, repo: str | None, limit: int) -> dict:
    command = ["pi-model-usage", "--json"]
    if profile != "auto":
        command.extend(["--profile", profile])
    if repo:
        command.extend(["--repo", repo])
    command.extend(["recent", str(limit)])
    return json.loads(subprocess.check_output(command, text=True))


def bucket_totals(buckets: list[dict]) -> dict:
    totals = {
        "responses": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
    }
    for bucket in buckets:
        totals["responses"] += int(bucket.get("responses") or 0)
        totals["input_tokens"] += int(bucket.get("input_tokens") or 0)
        totals["output_tokens"] += int(bucket.get("output_tokens") or 0)
        totals["cache_read_tokens"] += int(bucket.get("cache_read_tokens") or 0)
        totals["cache_write_tokens"] += int(bucket.get("cache_write_tokens") or 0)
        totals["total_tokens"] += int(bucket.get("total_tokens") or 0)
        totals["total_cost"] += float(bucket.get("total_cost") or 0.0)
    return totals


def day_key(timestamp: str | None) -> str:
    if not timestamp:
        return "unknown"
    return timestamp[:10]


def normalize_payload(payload: dict) -> tuple[list[dict], list[dict]]:
    sessions: list[dict] = []
    bucket_rows: list[dict] = []

    for session in payload.get("sessions") or []:
        profile = session.get("profile") or "unknown"
        repo = session.get("cwd") or ""
        parent = session.get("parent") or {}
        children = session.get("children") or []
        all_logs = [parent, *children]
        session_buckets: list[dict] = []
        model_changes: list[str] = []

        for log in all_logs:
            log_role = log.get("role") or "unknown"
            log_name = log.get("name") or ""
            for model_change in log.get("model_changes") or []:
                if model_change not in model_changes:
                    model_changes.append(model_change)
            for bucket in log.get("buckets") or []:
                row = {
                    "session_key": f"{profile}:{session.get('path')}",
                    "profile": profile,
                    "repo": repo,
                    "repo_name": Path(repo).name if repo else "unknown",
                    "started": session.get("started"),
                    "day": day_key(session.get("started")),
                    "path": session.get("path"),
                    "parent_path": session.get("path"),
                    "parent_session_id": parent.get("session_id"),
                    "log_role": log_role,
                    "log_name": log_name,
                    "log_path": log.get("path"),
                    "log_session_id": log.get("session_id"),
                    "provider": bucket.get("provider") or "unknown",
                    "model": bucket.get("model") or "unknown",
                    "api": bucket.get("api") or "unknown",
                    "responses": int(bucket.get("responses") or 0),
                    "input_tokens": int(bucket.get("input_tokens") or 0),
                    "output_tokens": int(bucket.get("output_tokens") or 0),
                    "cache_read_tokens": int(bucket.get("cache_read_tokens") or 0),
                    "cache_write_tokens": int(bucket.get("cache_write_tokens") or 0),
                    "total_tokens": int(bucket.get("total_tokens") or 0),
                    "total_cost": float(bucket.get("total_cost") or 0.0),
                }
                bucket_rows.append(row)
                session_buckets.append(row)

        totals = bucket_totals(session_buckets)
        child_responses = sum(int((child or {}).get("responses") or 0) for child in children)
        sessions.append(
            {
                "session_key": f"{profile}:{session.get('path')}",
                "profile": profile,
                "repo": repo,
                "repo_name": Path(repo).name if repo else "unknown",
                "started": session.get("started"),
                "day": day_key(session.get("started")),
                "path": session.get("path"),
                "parent_session_id": parent.get("session_id"),
                "parent_responses": int(parent.get("responses") or 0),
                "child_sessions": len(children),
                "child_responses": child_responses,
                "responses": totals["responses"],
                "input_tokens": totals["input_tokens"],
                "output_tokens": totals["output_tokens"],
                "cache_read_tokens": totals["cache_read_tokens"],
                "cache_write_tokens": totals["cache_write_tokens"],
                "total_tokens": totals["total_tokens"],
                "total_cost": totals["total_cost"],
                "model_changes": model_changes,
                "logs": all_logs,
            }
        )

    return sessions, bucket_rows


def build_dataset(args: argparse.Namespace) -> dict:
    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")

    profiles = [args.profile]
    if args.profile == "both":
        profiles = ["personal", "work"]

    sessions: list[dict] = []
    bucket_rows: list[dict] = []
    loaded_profiles: list[dict] = []
    errors: list[dict] = []

    for profile in profiles:
        try:
            payload = run_usage(profile, args.repo, args.limit)
        except subprocess.CalledProcessError as exc:
            errors.append(
                {
                    "profile": profile,
                    "command": exc.cmd,
                    "error": exc.stderr or str(exc),
                }
            )
            continue
        normalized_sessions, normalized_rows = normalize_payload(payload)
        sessions.extend(normalized_sessions)
        bucket_rows.extend(normalized_rows)
        loaded_profiles.append(
            {
                "profile": profile,
                "recent_sessions": payload.get("recent_sessions") or 0,
                "profiles_searched": payload.get("profiles_searched") or [],
            }
        )

    sessions.sort(key=lambda item: item.get("started") or "", reverse=True)
    bucket_rows.sort(key=lambda item: (item.get("started") or "", item.get("session_key") or ""), reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "requested_profile": args.profile,
        "repo_filter": args.repo,
        "limit": args.limit,
        "loaded_profiles": loaded_profiles,
        "errors": errors,
        "sessions": sessions,
        "bucket_rows": bucket_rows,
    }


def html_template(data_json: str) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Pi Model Usage Dashboard</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #191724;
      --panel: #1f1d2e;
      --panel-2: #26233a;
      --text: #e0def4;
      --muted: #908caa;
      --accent: #c4a7e7;
      --accent-2: #9ccfd8;
      --good: #31748f;
      --warn: #ebbcba;
      --border: #403d52;
      --bar: #524f67;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, sans-serif; background: var(--bg); color: var(--text); }}
    a {{ color: var(--accent-2); }}
    .wrap {{ max-width: 1500px; margin: 0 auto; padding: 24px; }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    h1 {{ font-size: 28px; }}
    h2 {{ font-size: 18px; margin-top: 28px; }}
    .subtle {{ color: var(--muted); }}
    .grid {{ display: grid; gap: 16px; }}
    .cards {{ grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }}
    .two {{ grid-template-columns: 1.2fr 1fr; align-items: start; }}
    .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }}
    .card-value {{ font-size: 24px; font-weight: 700; margin-top: 8px; }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: end; }}
    label {{ display: grid; gap: 6px; font-size: 13px; color: var(--muted); min-width: 160px; }}
    select, input {{ background: var(--panel-2); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 600; position: sticky; top: 0; background: var(--panel); }}
    tbody tr:hover {{ background: rgba(255,255,255,0.03); }}
    tbody tr.active {{ background: rgba(196, 167, 231, 0.15); }}
    .table-wrap {{ max-height: 420px; overflow: auto; border: 1px solid var(--border); border-radius: 10px; }}
    .bars {{ display: grid; gap: 10px; }}
    .bar-row {{ display: grid; gap: 6px; }}
    .bar-head {{ display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }}
    .bar-track {{ height: 12px; background: var(--bar); border-radius: 999px; overflow: hidden; }}
    .bar-fill {{ height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent-2)); border-radius: 999px; }}
    .pill {{ display: inline-block; background: var(--panel-2); border: 1px solid var(--border); border-radius: 999px; padding: 4px 8px; margin: 3px 6px 0 0; font-size: 12px; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    .list {{ display: grid; gap: 8px; }}
    .error {{ color: var(--warn); }}
    button {{ background: var(--panel-2); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; cursor: pointer; }}
    @media (max-width: 1000px) {{ .two {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"panel\">
      <h1>Pi Model Usage Dashboard</h1>
      <div class=\"subtle\" id=\"meta\"></div>
    </div>

    <div class=\"panel\" style=\"margin-top: 16px;\">
      <div class=\"filters\">
        <label>Profile
          <select id=\"profileFilter\"></select>
        </label>
        <label>Repo
          <select id=\"repoFilter\"></select>
        </label>
        <label>Provider
          <select id=\"providerFilter\"></select>
        </label>
        <label>Model
          <select id=\"modelFilter\"></select>
        </label>
        <label>Session path contains
          <input id=\"pathFilter\" type=\"text\" placeholder=\"subagent, date, id...\" />
        </label>
        <button id=\"resetFilters\" type=\"button\">Reset filters</button>
      </div>
    </div>

    <div class=\"grid cards\" id=\"cards\" style=\"margin-top: 16px;\"></div>

    <div class=\"grid two\" style=\"margin-top: 16px;\">
      <div class=\"panel\">
        <h2>Usage by day</h2>
        <div class=\"bars\" id=\"dayBars\"></div>
      </div>
      <div class=\"panel\">
        <h2>Usage by provider</h2>
        <div class=\"bars\" id=\"providerBars\"></div>
      </div>
    </div>

    <div class=\"grid two\" style=\"margin-top: 16px;\">
      <div class=\"panel\">
        <h2>Usage by model</h2>
        <div class=\"table-wrap\"><table id=\"modelTable\"></table></div>
      </div>
      <div class=\"panel\">
        <h2>Usage by repo</h2>
        <div class=\"table-wrap\"><table id=\"repoTable\"></table></div>
      </div>
    </div>

    <div class=\"grid two\" style=\"margin-top: 16px;\">
      <div class=\"panel\">
        <h2>Sessions</h2>
        <div class=\"table-wrap\"><table id=\"sessionTable\"></table></div>
      </div>
      <div class=\"panel\">
        <h2>Session detail</h2>
        <div id=\"sessionDetail\" class=\"subtle\">Select session row.</div>
      </div>
    </div>
  </div>

  <script>
    const DATA = {data_json};

    const numberFmt = new Intl.NumberFormat();
    const costFmt = new Intl.NumberFormat(undefined, {{ style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 6 }});

    const state = {{
      selectedSessionKey: null,
      filters: {{
        profile: 'all',
        repo: 'all',
        provider: 'all',
        model: 'all',
        pathText: ""
      }}
    }};

    const nodes = {{
      meta: document.getElementById('meta'),
      cards: document.getElementById('cards'),
      dayBars: document.getElementById('dayBars'),
      providerBars: document.getElementById('providerBars'),
      modelTable: document.getElementById('modelTable'),
      repoTable: document.getElementById('repoTable'),
      sessionTable: document.getElementById('sessionTable'),
      sessionDetail: document.getElementById('sessionDetail'),
      profileFilter: document.getElementById('profileFilter'),
      repoFilter: document.getElementById('repoFilter'),
      providerFilter: document.getElementById('providerFilter'),
      modelFilter: document.getElementById('modelFilter'),
      pathFilter: document.getElementById('pathFilter'),
      resetFilters: document.getElementById('resetFilters')
    }};

    function fmtInt(value) {{ return numberFmt.format(value || 0); }}
    function fmtCost(value) {{ return value ? costFmt.format(value) : '$0.00'; }}
    function escapeHtml(value) {{
      return String(value ?? "").replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
    }}

    function sumRows(rows) {{
      return rows.reduce((acc, row) => {{
        acc.responses += row.responses || 0;
        acc.input_tokens += row.input_tokens || 0;
        acc.output_tokens += row.output_tokens || 0;
        acc.cache_read_tokens += row.cache_read_tokens || 0;
        acc.cache_write_tokens += row.cache_write_tokens || 0;
        acc.total_tokens += row.total_tokens || 0;
        acc.total_cost += row.total_cost || 0;
        return acc;
      }}, {{ responses: 0, input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, total_tokens: 0, total_cost: 0 }});
    }}

    function uniqueSorted(values) {{
      return [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
    }}

    function groupBy(rows, keyFn) {{
      const map = new Map();
      for (const row of rows) {{
        const key = keyFn(row);
        if (!map.has(key)) map.set(key, []);
        map.get(key).push(row);
      }}
      return map;
    }}

    function buildOptions(select, values, current) {{
      select.innerHTML = ['<option value="all">all</option>', ...values.map(v => `<option value="''${{escapeHtml(v)}}">''${{escapeHtml(v)}}</option>`)].join("");
      select.value = values.includes(current) ? current : 'all';
    }}

    function filteredSessions() {{
      return DATA.sessions.filter(session => {{
        if (state.filters.profile !== 'all' && session.profile !== state.filters.profile) return false;
        if (state.filters.repo !== 'all' && session.repo !== state.filters.repo) return false;
        if (state.filters.pathText) {{
          const hay = `''${{session.path || ""}} ''${{session.parent_session_id || ""}} ''${{session.repo || ""}}`.toLowerCase();
          if (!hay.includes(state.filters.pathText.toLowerCase())) return false;
        }}
        if (state.filters.provider === 'all' && state.filters.model === 'all') return true;
        const rows = DATA.bucket_rows.filter(row => row.session_key === session.session_key);
        if (state.filters.provider !== 'all' && !rows.some(row => row.provider === state.filters.provider)) return false;
        if (state.filters.model !== 'all' && !rows.some(row => row.model === state.filters.model)) return false;
        return true;
      }});
    }}

    function filteredRows() {{
      const allowedSessions = new Set(filteredSessions().map(session => session.session_key));
      return DATA.bucket_rows.filter(row => {{
        if (!allowedSessions.has(row.session_key)) return false;
        if (state.filters.provider !== 'all' && row.provider !== state.filters.provider) return false;
        if (state.filters.model !== 'all' && row.model !== state.filters.model) return false;
        return true;
      }});
    }}

    function renderCards(rows, sessions) {{
      const totals = sumRows(rows);
      const cards = [
        ['sessions', fmtInt(sessions.length)],
        ['responses', fmtInt(totals.responses)],
        ['input tokens', fmtInt(totals.input_tokens)],
        ['output tokens', fmtInt(totals.output_tokens)],
        ['cache read', fmtInt(totals.cache_read_tokens)],
        ['cache write', fmtInt(totals.cache_write_tokens)],
        ['total tokens', fmtInt(totals.total_tokens)],
        ['cost', fmtCost(totals.total_cost)]
      ];
      nodes.cards.innerHTML = cards.map(([label, value]) => `
        <div class="panel">
          <div class="subtle">''${{label}}</div>
          <div class="card-value">''${{value}}</div>
        </div>
      `).join("");
    }}

    function renderBars(node, groups, labelFn) {{
      const entries = [...groups.entries()].map(([key, rows]) => ({{
        key,
        label: labelFn(key, rows),
        totals: sumRows(rows)
      }})).sort((a, b) => b.totals.total_tokens - a.totals.total_tokens).slice(0, 12);
      const max = Math.max(...entries.map(entry => entry.totals.total_tokens), 1);
      node.innerHTML = entries.length ? entries.map(entry => `
        <div class="bar-row">
          <div class="bar-head">
            <span>''${{escapeHtml(entry.label)}}</span>
            <span>''${{fmtInt(entry.totals.total_tokens)}} tok · ''${{fmtCost(entry.totals.total_cost)}} · ''${{fmtInt(entry.totals.responses)}} rsp</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:''${{(entry.totals.total_tokens / max) * 100}}%"></div></div>
        </div>
      `).join("") : '<div class="subtle">No data.</div>';
    }}

    function renderAggTable(node, titleKey, rows, keyFn, labelFn) {{
      const grouped = [...groupBy(rows, keyFn).entries()].map(([key, bucketRows]) => {{
        const totals = sumRows(bucketRows);
        return {{
          key,
          label: labelFn(key, bucketRows),
          sessions: new Set(bucketRows.map(row => row.session_key)).size,
          ...totals
        }};
      }}).sort((a, b) => b.total_tokens - a.total_tokens);

      node.innerHTML = `
        <thead>
          <tr>
            <th>''${{titleKey}}</th>
            <th>sessions</th>
            <th>responses</th>
            <th>cache read</th>
            <th>total tokens</th>
            <th>cost</th>
          </tr>
        </thead>
        <tbody>
          ''${{grouped.map(item => `
            <tr>
              <td class="mono">''${{escapeHtml(item.label)}}</td>
              <td>''${{fmtInt(item.sessions)}}</td>
              <td>''${{fmtInt(item.responses)}}</td>
              <td>''${{fmtInt(item.cache_read_tokens)}}</td>
              <td>''${{fmtInt(item.total_tokens)}}</td>
              <td>''${{fmtCost(item.total_cost)}}</td>
            </tr>
          `).join("")}}
        </tbody>
      `;
    }}

    function renderSessionTable(sessions) {{
      nodes.sessionTable.innerHTML = `
        <thead>
          <tr>
            <th>started</th>
            <th>profile</th>
            <th>repo</th>
            <th>responses</th>
            <th>child</th>
            <th>total tokens</th>
            <th>cost</th>
          </tr>
        </thead>
        <tbody>
          ''${{sessions.map(session => `
            <tr data-session-key="''${{escapeHtml(session.session_key)}}" class="''${{state.selectedSessionKey === session.session_key ? 'active' : ""}}">
              <td class="mono">''${{escapeHtml(session.started || 'unknown')}}</td>
              <td>''${{escapeHtml(session.profile)}}</td>
              <td title="''${{escapeHtml(session.repo)}}">''${{escapeHtml(session.repo_name)}}</td>
              <td>''${{fmtInt(session.responses)}}</td>
              <td>''${{fmtInt(session.child_sessions)}}</td>
              <td>''${{fmtInt(session.total_tokens)}}</td>
              <td>''${{fmtCost(session.total_cost)}}</td>
            </tr>
          `).join("")}}
        </tbody>
      `;
      nodes.sessionTable.querySelectorAll('tbody tr').forEach(row => {{
        row.addEventListener('click', () => {{
          state.selectedSessionKey = row.dataset.sessionKey;
          render();
        }});
      }});
    }}

    function renderSessionDetail(sessions, rows) {{
      const session = sessions.find(item => item.session_key === state.selectedSessionKey) || sessions[0];
      if (!session) {{
        nodes.sessionDetail.innerHTML = '<div class="subtle">No session matches current filters.</div>';
        return;
      }}
      if (!state.selectedSessionKey) state.selectedSessionKey = session.session_key;
      const sessionRows = rows.filter(row => row.session_key === session.session_key);
      const totals = sumRows(sessionRows);
      const rowHtml = sessionRows.map(row => `
        <tr>
          <td>''${{escapeHtml(row.log_role)}}''${{row.log_name ? ` · ''${{escapeHtml(row.log_name)}}` : ""}}</td>
          <td class="mono">''${{escapeHtml(`''${{row.provider}}/''${{row.model}}`)}}</td>
          <td>''${{escapeHtml(row.api)}}</td>
          <td>''${{fmtInt(row.responses)}}</td>
          <td>''${{fmtInt(row.total_tokens)}}</td>
          <td>''${{fmtCost(row.total_cost)}}</td>
        </tr>
      `).join("");
      nodes.sessionDetail.innerHTML = `
        <div class="list">
          <div><span class="subtle">Started:</span> <span class="mono">''${{escapeHtml(session.started || 'unknown')}}</span></div>
          <div><span class="subtle">Profile:</span> ''${{escapeHtml(session.profile)}}</div>
          <div><span class="subtle">Repo:</span> <span class="mono">''${{escapeHtml(session.repo || 'unknown')}}</span></div>
          <div><span class="subtle">Path:</span> <span class="mono">''${{escapeHtml(session.path || 'unknown')}}</span></div>
          <div><span class="subtle">Parent session id:</span> <span class="mono">''${{escapeHtml(session.parent_session_id || 'unknown')}}</span></div>
          <div><span class="subtle">Totals:</span> ''${{fmtInt(totals.responses)}} rsp · ''${{fmtInt(totals.total_tokens)}} tok · ''${{fmtInt(totals.cache_read_tokens)}} cache read · ''${{fmtCost(totals.total_cost)}}</div>
          <div><span class="subtle">Model changes:</span><br/>''${{session.model_changes.length ? session.model_changes.map(item => `<span class="pill mono">''${{escapeHtml(item)}}</span>`).join("") : '<span class="subtle">none</span>'}}</div>
        </div>
        <h3 style="margin-top:16px;">Buckets</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>role</th>
                <th>model</th>
                <th>api</th>
                <th>responses</th>
                <th>total tokens</th>
                <th>cost</th>
              </tr>
            </thead>
            <tbody>''${{rowHtml}}</tbody>
          </table>
        </div>
      `;
    }}

    function syncFilterOptions() {{
      buildOptions(nodes.profileFilter, uniqueSorted(DATA.sessions.map(session => session.profile)), state.filters.profile);
      buildOptions(nodes.repoFilter, uniqueSorted(DATA.sessions.map(session => session.repo)), state.filters.repo);
      const profileSessions = DATA.sessions.filter(session => state.filters.profile === 'all' || session.profile === state.filters.profile);
      const sessionKeys = new Set(profileSessions.map(session => session.session_key));
      const scopedRows = DATA.bucket_rows.filter(row => sessionKeys.has(row.session_key) && (state.filters.repo === 'all' || row.repo === state.filters.repo));
      buildOptions(nodes.providerFilter, uniqueSorted(scopedRows.map(row => row.provider)), state.filters.provider);
      const providerRows = scopedRows.filter(row => state.filters.provider === 'all' || row.provider === state.filters.provider);
      buildOptions(nodes.modelFilter, uniqueSorted(providerRows.map(row => row.model)), state.filters.model);
      nodes.pathFilter.value = state.filters.pathText;
    }}

    function renderMeta() {{
      const loaded = DATA.loaded_profiles.map(item => `''${{item.profile}}:''${{item.recent_sessions}}`).join(' · ');
      const repo = DATA.repo_filter ? `repo filter ''${{DATA.repo_filter}}` : 'all repos';
      const err = DATA.errors.length ? ` · <span class="error">errors: ''${{DATA.errors.map(e => e.profile).join(', ')}}</span>` : "";
      nodes.meta.innerHTML = `generated ''${{escapeHtml(DATA.generated_at)}} · requested profile ''${{escapeHtml(DATA.requested_profile)}} · ''${{escapeHtml(repo)}} · per-profile limit ''${{DATA.limit}} · loaded ''${{escapeHtml(loaded || 'none')}}''${{err}}`;
    }}

    function render() {{
      renderMeta();
      syncFilterOptions();
      const sessions = filteredSessions();
      const rows = filteredRows();
      renderCards(rows, sessions);
      renderBars(nodes.dayBars, groupBy(rows, row => row.day), key => key);
      renderBars(nodes.providerBars, groupBy(rows, row => row.provider), key => key);
      renderAggTable(nodes.modelTable, 'model', rows, row => `''${{row.provider}}/''${{row.model}}`, key => key);
      renderAggTable(nodes.repoTable, 'repo', rows, row => row.repo || 'unknown', key => key);
      renderSessionTable(sessions);
      renderSessionDetail(sessions, rows);
    }}

    nodes.profileFilter.addEventListener('change', event => {{ state.filters.profile = event.target.value; state.selectedSessionKey = null; render(); }});
    nodes.repoFilter.addEventListener('change', event => {{ state.filters.repo = event.target.value; state.selectedSessionKey = null; render(); }});
    nodes.providerFilter.addEventListener('change', event => {{ state.filters.provider = event.target.value; state.selectedSessionKey = null; render(); }});
    nodes.modelFilter.addEventListener('change', event => {{ state.filters.model = event.target.value; state.selectedSessionKey = null; render(); }});
    nodes.pathFilter.addEventListener('input', event => {{ state.filters.pathText = event.target.value; state.selectedSessionKey = null; render(); }});
    nodes.resetFilters.addEventListener('click', () => {{
      state.filters = {{ profile: 'all', repo: 'all', provider: 'all', model: 'all', pathText: "" }};
      state.selectedSessionKey = null;
      render();
    }});

    render();
  </script>
</body>
</html>
"""


def maybe_open(path: Path) -> None:
    candidates = [
        ["open", str(path)],
        ["xdg-open", str(path)],
    ]
    for command in candidates:
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue


def main() -> int:
    args = parse_args()
    dataset = build_dataset(args)
    data_json = json.dumps(dataset).replace("</", "<\\/")
    html = html_template(data_json)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        handle = tempfile.NamedTemporaryFile(prefix="pi-model-usage-dashboard-", suffix=".html", delete=False)
        output_path = Path(handle.name)
        handle.close()

    output_path.write_text(html, encoding="utf-8")
    print(output_path)
    if args.open_browser:
        maybe_open(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
''
