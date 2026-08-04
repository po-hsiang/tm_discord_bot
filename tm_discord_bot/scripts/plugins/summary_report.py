"""影片快速摘要的本地成本/成效追蹤報告（短期觀察用，非長期功能）。

每分析完一部影片（快取命中不計，因為沒有花費）就在本地 HTML 報告追加一列；
報告只寫在本機 `reports/video_summary_report.html`（gitignore 排除、
Docker 以 volume 掛載），不會回覆到 Discord。
不需要追蹤時：移除 video_summary.py 內的 append_record 呼叫與本模組即可。
"""
from pathlib import Path
import datetime
import html
import threading

REPORT_PATH = Path(__file__).resolve().parents[3] / "reports" / "video_summary_report.html"

# ---- 計價常數（短期追蹤用的估算，請依實際牌價調整）----
# USD / 1M tokens；來源對應目前 n8n 端的模型：
#   transcript = OpenAI gpt-5.6-luna（CC 字幕→文字摘要）
#   audio / video = Gemini Flash-Lite（音訊輸入 / 低解析影片輸入）
PRICING_USD_PER_M = {
    "transcript": {"input": 1.25, "output": 10.0},
    "audio": {"input": 0.30, "output": 0.40},
    "video": {"input": 0.10, "output": 0.40},
}
USD_TO_TWD = 31.5
# CC 路徑拿不到實際 token 數，以「逐字稿字數＋提詞 ≈ input tokens」粗估（中文約 1 字 1 token）
_ESTIMATE_PROMPT_OVERHEAD = 150
_ESTIMATE_OUTPUT_TOKENS = 150

_SOURCE_LABELS = {
    "transcript": "CC 字幕",
    "audio": "音訊轉錄",
    "video": "Gemini 看影片",
}

_APPEND_MARKER = "<!-- APPEND -->"

_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>影片快速摘要 成本追蹤</title>
<style>
body { font-family: "Microsoft JhengHei", sans-serif; margin: 24px; background: #fafafa; color: #222; }
h1 { font-size: 1.3rem; }
p.note { color: #777; font-size: 0.85rem; }
table { border-collapse: collapse; width: 100%; background: #fff; font-size: 0.9rem; }
th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; white-space: nowrap; }
td.title { white-space: normal; max-width: 28em; }
th { background: #f0f0f0; }
tr:nth-child(even) { background: #f9f9f9; }
#totals { font-weight: bold; margin-top: 12px; }
</style>
</head>
<body>
<h1>影片快速摘要 成本/成效追蹤</h1>
<p class="note">由 bot 於每次實際分析後自動追加（快取命中不計）；「（估）」為推估值。
計價常數在 <code>plugins/summary_report.py</code>，請依實際牌價調整。</p>
<table>
<thead>
<tr><th>時間</th><th>影片</th><th>片長</th><th>字幕</th><th>來源</th><th>逐字稿字數</th><th>結果</th><th>Input Tokens</th><th>預估花費</th></tr>
</thead>
<tbody>
<!-- APPEND -->
</tbody>
</table>
<p id="totals"></p>
<script>
(function () {
  var rows = document.querySelectorAll("tbody tr");
  var count = rows.length, okCount = 0, tokens = 0, twd = 0;
  rows.forEach(function (r) {
    if (r.dataset.ok === "1") okCount += 1;
    tokens += Number(r.dataset.intok || 0);
    twd += Number(r.dataset.twd || 0);
  });
  document.getElementById("totals").textContent =
    "累計 " + count + " 筆｜成功 " + okCount + " 筆｜Input Tokens 合計 " +
    tokens.toLocaleString() + "｜預估總花費 NT$" + twd.toFixed(2);
})();
</script>
</body>
</html>
"""

_lock = threading.Lock()


def _format_duration(seconds):
    minutes, sec = divmod(int(seconds or 0), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def _estimate_cost_twd(source, input_tokens, output_tokens):
    pricing = PRICING_USD_PER_M.get(source)
    if not pricing or input_tokens is None:
        return None
    usd = (
        input_tokens / 1_000_000 * pricing["input"]
        + (output_tokens or 0) / 1_000_000 * pricing["output"]
    )
    return usd * USD_TO_TWD


def _build_row(video_id, result, now=None):
    now = now or datetime.datetime.now()
    stats = result.get("stats") or {}
    source = result.get("source")
    ok = bool(result.get("ok"))

    title = str(result.get("title") or "").strip() or video_id
    url = result.get("video_url") or f"https://www.youtube.com/watch?v={video_id}"

    duration = result.get("duration_seconds")
    duration_text = _format_duration(duration) if duration else "—"

    if source == "transcript":
        caption_text = "有"
    elif source in ("audio", "video") or result.get("error_code") == "NO_TRANSCRIPT":
        caption_text = "無"
    else:
        caption_text = "—"

    transcript_chars = stats.get("transcript_chars")
    chars_text = f"{transcript_chars:,}" if transcript_chars else "—"

    result_text = "✅ 成功" if ok else f"❌ {result.get('error_code') or 'UNKNOWN'}"

    input_tokens = stats.get("input_tokens")
    output_tokens = stats.get("output_tokens")
    estimated = False
    if input_tokens is None and source == "transcript" and transcript_chars:
        # CC 路徑的 chainLlm 節點拿不到實際用量，以逐字稿字數粗估
        input_tokens = transcript_chars + _ESTIMATE_PROMPT_OVERHEAD
        output_tokens = _ESTIMATE_OUTPUT_TOKENS
        estimated = True
    tokens_text = f"{input_tokens:,}（估）" if (input_tokens and estimated) else (
        f"{input_tokens:,}" if input_tokens else "—"
    )

    cost_twd = _estimate_cost_twd(source, input_tokens, output_tokens)
    cost_text = (
        ("約 " if estimated else "") + f"NT${cost_twd:.4f}" if cost_twd is not None else "—"
    )

    return (
        f'<tr data-ok="{1 if ok else 0}" data-intok="{input_tokens or 0}" '
        f'data-twd="{cost_twd or 0:.6f}">'
        f"<td>{now.strftime('%Y-%m-%d %H:%M')}</td>"
        f'<td class="title"><a href="{html.escape(url, quote=True)}">{html.escape(title)}</a></td>'
        f"<td>{duration_text}</td>"
        f"<td>{caption_text}</td>"
        f"<td>{_SOURCE_LABELS.get(source, '—')}</td>"
        f"<td>{chars_text}</td>"
        f"<td>{html.escape(result_text)}</td>"
        f"<td>{tokens_text}</td>"
        f"<td>{cost_text}</td>"
        f"</tr>"
    )


def append_record(video_id, result, report_path=REPORT_PATH):
    """在本地 HTML 報告追加一列分析紀錄；檔案不存在（或損毀）時重建。"""
    row = _build_row(video_id, result)
    with _lock:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        content = _TEMPLATE
        if report_path.exists():
            existing = report_path.read_text(encoding="utf-8")
            if _APPEND_MARKER in existing:
                content = existing
        content = content.replace(_APPEND_MARKER, f"{row}\n{_APPEND_MARKER}")
        report_path.write_text(content, encoding="utf-8")
