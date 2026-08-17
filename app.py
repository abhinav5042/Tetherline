import io
import json
import textwrap
import html as html_lib

import streamlit as st

import db
from pipeline import run_pipeline
from agents.drift_detector import find_stale_tickets
from agents import linear_client

db.init_db()

st.set_page_config(page_title="Tetherline", page_icon="◆", layout="wide")

# ----------------------------------------------------------------------------
# Theme
# ----------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Inter:wght@400;500;600&display=swap');

:root {
  --bg: #1A1A18;
  --sidebar: #171715;
  --surface: #232320;
  --surface-2: #2A2A26;
  --border: #34342F;
  --ink: #ECE9E2;
  --muted: #8F8B82;
  --accent: #D97757;
  --accent-soft: #3A2A22;
  --blue: #6C93B5;
  --blue-soft: #1E2A32;
  --tan: #B5A48C;
  --tan-soft: #2B2822;
}

.stApp { background-color: var(--bg); }

section[data-testid="stSidebar"] {
  background-color: var(--sidebar);
  border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] > div:first-child { padding-top: 1.2rem; }

body, .stApp, p, span, label, div {
  font-family: 'Inter', sans-serif;
  color: var(--ink);
}

h1, h2, h3, .display { font-family: 'Source Serif 4', serif !important; }

/* --- Brand mark, top of sidebar, large --- */
.brand-row { display: flex; align-items: center; gap: 12px; padding: 0 4px 22px 4px; }
.brand-mark {
  width: 34px; height: 34px; border-radius: 10px;
  background: linear-gradient(135deg, var(--accent), #B5563A);
  position: relative; flex-shrink: 0;
}
.brand-mark:before {
  content: "";
  position: absolute; top: 9px; left: 9px; width: 16px; height: 16px;
  border: 2.5px solid #171715; border-radius: 50%;
}
.brand-name { font-family: 'Source Serif 4', serif; font-size: 26px; font-weight: 600; color: var(--ink); line-height: 1.1; }
.brand-tagline { font-size: 11px; color: var(--muted); margin-top: 1px; }

.sidebar-section-label {
  font-size: 11px; letter-spacing: 0.5px; text-transform: uppercase;
  color: var(--muted); margin: 18px 0 6px 4px;
}
.recent-meta { font-size: 11px; color: var(--muted); }

/* --- Main header --- */
.app-header { padding: 4px 0 20px 0; }
.app-header .display { font-size: 24px; font-weight: 600; margin-bottom: 3px; color: var(--ink); }
.app-header .sub { font-size: 13.5px; color: var(--muted); }
.empty-state {
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 40px 24px; text-align: center; color: var(--muted); font-size: 14px;
}

/* --- Buttons --- */
div[data-testid="stButton"] > button, div[data-testid="stSidebar"] div[data-testid="stButton"] > button {
  border-radius: 10px; font-weight: 500; font-size: 14px; border: 1px solid var(--border);
  background-color: var(--surface); color: var(--ink);
}
button[kind="primary"] {
  background-color: var(--accent) !important; color: #1A1A18 !important;
  border: 1px solid var(--accent) !important; font-weight: 600 !important;
}
button[kind="secondary"] { background-color: var(--surface) !important; color: var(--ink) !important; }

/* --- Inputs --- */
div[data-testid="stTextInput"] label, div[data-testid="stTextArea"] label {
  font-size: 13px; font-weight: 500; color: var(--muted);
}
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {
  background-color: var(--surface); color: var(--ink);
  border: 1px solid var(--border); border-radius: 14px;
}

/* --- Chat-style composer pinned at bottom (native Streamlit chat_input) --- */
div[data-testid="stChatInput"] {
  background-color: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 22px !important;
}
div[data-testid="stChatInput"] textarea { color: var(--ink) !important; }

/* --- Section label --- */
.section-label { font-size: 13px; color: var(--muted); margin: 30px 0 10px 2px; }

/* --- Requirement card --- */
.req-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 18px 20px; margin: 14px 0 0 0;
}
.req-card-header { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 8px; }
.req-key { font-size: 13px; font-weight: 600; color: var(--ink); }
.priority-chip { font-size: 11px; font-weight: 500; padding: 3px 10px; border-radius: 20px; white-space: nowrap; }
.priority-must { background: var(--accent-soft); color: var(--accent); }
.priority-should { background: var(--blue-soft); color: var(--blue); }
.priority-could { background: var(--tan-soft); color: var(--tan); }

.req-text { font-size: 14px; line-height: 1.55; color: var(--ink); margin-bottom: 10px; }
.ac-list { font-size: 13px; color: var(--muted); margin: 0; padding-left: 20px; }
.ac-list li { margin-bottom: 3px; }

/* --- Ticket card --- */
.ticket-card {
  background: var(--surface-2); border: 1px solid var(--border); border-left: 3px solid var(--accent);
  border-radius: 12px; padding: 14px 18px; margin: 10px 0 10px 26px;
}
.ticket-card.stale { border-left-color: var(--muted); }
.ticket-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.ticket-title { font-size: 14px; font-weight: 600; margin-bottom: 5px; color: var(--ink); }
.ticket-desc { font-size: 13px; color: var(--ink); line-height: 1.5; margin-bottom: 8px; opacity: 0.9; }

.needs-review {
  font-size: 11px; font-weight: 500; color: var(--accent);
  background: var(--accent-soft); padding: 3px 10px; border-radius: 20px; white-space: nowrap;
}

details.payload { margin-top: 8px; }
details.payload summary {
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  color: var(--accent);
  background: var(--accent-soft);
  border: 1px solid var(--accent);
  border-radius: 8px;
  padding: 6px 12px;
  display: inline-block;
  list-style: none;
  user-select: none;
}
details.payload summary::-webkit-details-marker { display: none; }
details.payload summary::before {
  content: "▶ ";
  font-size: 9px;
}
details.payload[open] summary::before { content: "▼ "; }
details.payload summary:hover {
  background: var(--accent);
  color: #1A1A18;
}
details.payload pre {
  background: var(--bg); border: 1px solid var(--border); border-radius: 10px;
  padding: 10px; font-size: 11.5px; overflow-x: auto; color: var(--ink);
}

/* --- Constraint chip --- */
.constraint-chip {
  display: inline-block; background: var(--surface); border: 1px solid var(--border);
  border-radius: 20px; padding: 6px 14px; font-size: 12.5px; margin: 0 8px 8px 0; color: var(--ink);
}
.constraint-chip .tag { color: var(--muted); margin-right: 4px; }

/* --- Check results --- */
.check-clear {
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 16px 20px; font-size: 14px; color: var(--ink);
}
.check-flag {
  background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--accent);
  border-radius: 12px; padding: 14px 18px; margin-bottom: 10px;
}
.check-flag .ticket-title { color: var(--accent); }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# New case dialog — asks for the name only at case-creation time
# ----------------------------------------------------------------------------
@st.dialog("Name this case")
def new_case_dialog():
    name = st.text_input("Case name", placeholder="e.g. Checkout Redesign")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create case", type="primary", use_container_width=True):
            if name.strip():
                st.session_state["current_case"] = name.strip()
                st.session_state.pop("last_result", None)
                st.session_state.pop("stale_tickets", None)
                st.session_state["open_new_case_dialog"] = False
                st.rerun()
            else:
                st.warning("Give this case a name.")
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.session_state["open_new_case_dialog"] = False
            st.rerun()


def extract_text_from_upload(f) -> str:
    name = getattr(f, "name", "uploaded_file").lower()
    data = f.read()
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as e:
            return f"[Could not read PDF: {e}]"
    if name.endswith(".docx"):
        try:
            import docx
            d = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in d.paragraphs)
        except Exception as e:
            return f"[Could not read DOCX: {e}]"
    return ""


def esc(s: str) -> str:
    """
    Escapes HTML special characters AND strips any embedded newlines from
    single-line fields (titles, descriptions, criteria). This matters
    because a stray "\n" in generated text would corrupt textwrap.dedent's
    margin calculation the same way the JSON payload did — dedent looks at
    every line in the final string, so any 0-indent line anywhere breaks it
    for the whole block.
    """
    return html_lib.escape(str(s)).replace("\n", " ").replace("\r", "")


def render_html(content: str):
    """
    Wraps st.markdown for raw HTML blocks. Strips common leading whitespace
    first — Markdown treats 4+ leading spaces as a literal code block, which
    was causing every HTML template (indented to match the surrounding Python
    code) to render as visible raw tags instead of actual HTML.
    """
    st.markdown(textwrap.dedent(content), unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    render_html("""
    <div class="brand-row">
      <div class="brand-mark"></div>
      <div>
        <div class="brand-name">Tetherline</div>
        <div class="brand-tagline">every ticket, tethered to its truth</div>
      </div>
    </div>
    """)

    if st.button("+ New case", type="primary", use_container_width=True):
        st.session_state["open_new_case_dialog"] = True
        st.rerun()

    st.markdown('<div class="sidebar-section-label">Recent cases</div>', unsafe_allow_html=True)
    recents = db.get_recent_prd_titles()
    if not recents:
        st.markdown('<div class="recent-meta" style="padding:4px;">Nothing yet — start a new case.</div>',
                    unsafe_allow_html=True)
    for r in recents:
        if st.button(r["title"], key=f"recent_{r['title']}", use_container_width=True):
            st.session_state["current_case"] = r["title"]
            snapshot = db.get_case_snapshot(r["title"])
            if snapshot:
                st.session_state["last_result"] = snapshot
            else:
                st.session_state.pop("last_result", None)
            st.session_state.pop("stale_tickets", None)
            st.rerun()
        st.markdown(
            f'<div class="recent-meta" style="margin: -6px 0 8px 10px;">'
            f'{r["ticket_count"]} tickets · v{r["latest_version"]}</div>',
            unsafe_allow_html=True,
        )

if st.session_state.get("open_new_case_dialog"):
    new_case_dialog()

# ----------------------------------------------------------------------------
# Main panel
# ----------------------------------------------------------------------------
current_case = st.session_state.get("current_case")

if current_case:
    header_col1, header_col2, header_col3 = st.columns([3, 1, 1])
    with header_col1:
        render_html(f"""
        <div class="app-header">
          <div class="display">{esc(current_case)}</div>
          <div class="sub">Paste a PRD below, or attach a file, to generate tickets.</div>
        </div>
        """)
    with header_col2:
        st.write("")
        if st.button("Check for drift", use_container_width=True):
            st.session_state["stale_tickets"] = find_stale_tickets(current_case)
    with header_col3:
        st.write("")
        if st.button("Send to Linear", use_container_width=True):
            st.session_state["send_to_linear_clicked"] = True
else:
    render_html("""
    <div class="app-header">
      <div class="display">Tetherline</div>
      <div class="sub">Start a new case from the sidebar to begin.</div>
    </div>
    """)
    st.markdown('<div class="empty-state">No case selected. Click "+ New case" in the sidebar to name one.</div>',
                unsafe_allow_html=True)

PRIORITY_CLASS = {"must": "priority-must", "should": "priority-should", "could": "priority-could"}

if "last_result" in st.session_state:
    result = st.session_state["last_result"]
    st.markdown(
        f'<div class="section-label">{len(result["tickets"])} tickets · '
        f'{len(result["requirements"])} requirements</div>',
        unsafe_allow_html=True,
    )

    if result.get("constraints"):
        chips = "".join(
            f'<span class="constraint-chip"><span class="tag">Constraint</span>{esc(c["text"])}</span>'
            for c in result["constraints"]
        )
        st.markdown(f'<div style="margin-bottom:8px;">{chips}</div>', unsafe_allow_html=True)

    stale_ids = {s["ticket_id"] for s in st.session_state.get("stale_tickets", [])}

    for req in result["requirements"]:
        related = [t for t in result["tickets"] if t["source_requirement"] == req["req_key"]]
        priority = req.get("priority", "should")
        prio_class = PRIORITY_CLASS.get(priority, "priority-should")

        ac_html = "".join(f"<li>{esc(c)}</li>" for c in req["acceptance_criteria"])
        render_html(f"""
        <div class="req-card">
          <div class="req-card-header">
            <div class="req-key">{esc(req['req_key'])}</div>
            <div class="priority-chip {prio_class}">{esc(priority).upper()}</div>
          </div>
          <div class="req-text">{esc(req['text'])}</div>
          <ul class="ac-list">{ac_html}</ul>
        </div>
        """)

        for t in related:
            is_stale = t.get("ticket_id") in stale_ids
            stub_class = "ticket-card stale" if is_stale else "ticket-card"
            review_html = '<span class="needs-review">Needs review</span>' if is_stale else ""

            payload = next(
                (p for p in result["linear_payloads"] if p["title"] == t["title"]), None
            )
            # json.dumps(indent=2) produces lines like "{" with zero leading
            # spaces. If that gets embedded directly into the f-string below,
            # textwrap.dedent (which looks at EVERY line in the final string)
            # finds a 0-space minimum and skips dedenting entirely — the same
            # bug as before, just hiding one level deeper. Fix: dedent the
            # template with a placeholder first, then substitute the raw
            # (undedented) JSON in afterward, so it never affects the margin
            # calculation.
            payload_json = esc(json.dumps(payload, indent=2)) if payload else ""
            payload_placeholder = "@@PAYLOAD_JSON@@"

            tac_html = "".join(f"<li>{esc(c)}</li>" for c in t["acceptance_criteria"])

            template = f"""
            <div class="{stub_class}">
              <div class="ticket-top">
                <div class="ticket-title">{esc(t['title'])}</div>
                {review_html}
              </div>
              <div class="ticket-desc">{esc(t['description'])}</div>
              <ul class="ac-list">{tac_html}</ul>
              <details class="payload">
                <summary>View Linear payload</summary>
                <pre>{payload_placeholder}</pre>
              </details>
            </div>
            """
            final_html = textwrap.dedent(template).replace(payload_placeholder, payload_json)
            st.markdown(final_html, unsafe_allow_html=True)

if "stale_tickets" in st.session_state:
    stale = st.session_state["stale_tickets"]
    st.markdown('<div class="section-label">Drift check</div>', unsafe_allow_html=True)
    if not stale:
        st.markdown(
            '<div class="check-clear">Every ticket still matches its source requirement.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="margin-bottom:10px; font-size:13.5px; color:var(--muted);">'
            f'{len(stale)} ticket(s) may need review — their source requirement changed:</div>',
            unsafe_allow_html=True,
        )
        for s in stale:
            render_html(f"""
            <div class="check-flag">
              <div class="ticket-title">{esc(s['ticket_title'])}</div>
              <div style="font-size:12px; color:var(--muted); margin:4px 0;">
                source: {esc(s['requirement_key'])}
              </div>
              <div style="font-size:13px;">{esc(s['reason'])}</div>
              <div style="font-size:12.5px; margin-top:6px; color:var(--muted);">
                Current requirement text: <em>{esc(s['current_requirement_text'])}</em>
              </div>
            </div>
            """)

if st.session_state.get("send_to_linear_clicked"):
    st.session_state["send_to_linear_clicked"] = False
    result = st.session_state.get("last_result")
    if not result or not result.get("linear_payloads"):
        st.warning("Generate tickets first — there's nothing to send yet.")
    else:
        try:
            with st.spinner(f"Creating {len(result['linear_payloads'])} issue(s) in Linear..."):
                linear_results = linear_client.create_issues_bulk(result["linear_payloads"])
            st.session_state["linear_send_results"] = linear_results
        except linear_client.LinearConfigError as e:
            st.error(str(e))

if "linear_send_results" in st.session_state:
    lr = st.session_state["linear_send_results"]
    succeeded = [r for r in lr if r["success"]]
    failed = [r for r in lr if not r["success"]]
    st.markdown('<div class="section-label">Linear</div>', unsafe_allow_html=True)
    for r in succeeded:
        render_html(f"""
        <div class="check-clear" style="margin-bottom:8px;">
          Created <a href="{esc(r['url'])}" target="_blank" style="color:var(--accent);">{esc(r['title'])}</a>
        </div>
        """)
    for r in failed:
        render_html(f"""
        <div class="check-flag">
          <div class="ticket-title">{esc(r['title'])}</div>
          <div style="font-size:12.5px;">Failed to create: {esc(r['error'])}</div>
        </div>
        """)

# ----------------------------------------------------------------------------
# Bottom-pinned composer (native Streamlit chat_input docks to the bottom
# of the screen automatically — this is what gives the Claude-style feel).
# Falls back to a plain text-only composer if an older Streamlit version
# doesn't support file attachments on chat_input.
# ----------------------------------------------------------------------------
placeholder = "Paste PRD text, or attach a .txt/.md/.pdf/.docx file" if current_case else "Start a new case first"
submitted = None
try:
    submitted = st.chat_input(
        placeholder,
        accept_file="multiple",
        file_type=["txt", "md", "pdf", "docx"],
        disabled=(current_case is None),
    )
except TypeError:
    submitted = st.chat_input(placeholder, disabled=(current_case is None))

if submitted and current_case:
    if hasattr(submitted, "text"):
        raw_text = submitted.text or ""
        uploaded_files = list(getattr(submitted, "files", []) or [])
    else:
        raw_text = submitted
        uploaded_files = []

    combined_text = raw_text
    for f in uploaded_files:
        extracted = extract_text_from_upload(f)
        if extracted:
            combined_text += "\n\n" + extracted

    if not combined_text.strip():
        st.warning("Add some text or attach a document.")
    else:
        with st.spinner("Reading the PRD and drafting tickets..."):
            result = run_pipeline(current_case, combined_text)
        st.session_state["last_result"] = result
        st.rerun()
