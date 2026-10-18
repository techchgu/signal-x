"""SignalX Streamlit dashboard for live research with a preserved saved-data fallback."""
import pandas as pd
import streamlit as st
from config import GEMINI_API_KEY, HISTORY_PATH, ROOT
from src.demo import demo_result
from src.orchestrator import run_research
from src.report import render_report
from src.schemas import ResearchResult
from src.storage import load_results, save_result

st.set_page_config(page_title="SignalX | Financial Research", page_icon="📈", layout="wide")

st.markdown("""
<style>
:root {
  --sx-bg: #061321; --sx-panel: #0a1c2e; --sx-panel-soft: #0d2237;
  --sx-border: rgba(79, 209, 219, .20); --sx-teal: #23d4cb;
  --sx-cyan: #58d9ef; --sx-text: #e7f1fb; --sx-muted: #90a9bf;
}
.stApp {
  background: radial-gradient(ellipse at 71% 0%, rgba(7, 91, 112, .19), transparent 38%),
              radial-gradient(ellipse at 4% 88%, rgba(8, 55, 88, .20), transparent 34%), var(--sx-bg);
  color: var(--sx-text);
}
[data-testid="stHeader"] { background: rgba(6, 19, 33, .84); }
[data-testid="stMainBlockContainer"] { max-width: 1580px; padding: 2.65rem 2.1rem 3.2rem; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #07192a 0%, #061321 100%); border-right: 1px solid var(--sx-border); }
[data-testid="stSidebar"] > div:first-child { padding-top: 1.1rem; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--sx-muted); }
h1, h2, h3 { color: var(--sx-text); letter-spacing: -.025em; }
h1 { font-size: 2.1rem !important; }
h2 { font-size: 1.35rem !important; }
h3 { font-size: 1.05rem !important; }
[data-testid="stCaptionContainer"] { color: var(--sx-muted); }
[data-testid="stMetric"] { background: linear-gradient(145deg, rgba(12, 37, 58, .95), rgba(8, 27, 44, .92)); border: 1px solid var(--sx-border); padding: 1rem 1.05rem; border-radius: 14px; min-height: 112px; }
[data-testid="stMetricLabel"] p { color: #9bb4ca !important; font-size: .82rem !important; }
[data-testid="stMetricValue"] { color: var(--sx-teal) !important; font-size: 1.55rem !important; }
[data-testid="stVerticalBlockBorderWrapper"] { background: linear-gradient(145deg, rgba(11, 31, 50, .92), rgba(8, 25, 42, .92)); border: 1px solid var(--sx-border); border-radius: 18px; }
[data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input { background: #081a2b; color: var(--sx-text); border: 1px solid rgba(88, 217, 239, .28); border-radius: 12px; }
[data-testid="stTextArea"] textarea:focus, [data-testid="stTextInput"] input:focus { border-color: var(--sx-teal); box-shadow: 0 0 0 1px var(--sx-teal); }
div.stButton > button { border-radius: 11px; border: 1px solid rgba(88, 217, 239, .32); background: #102a40; color: var(--sx-text); transition: all .18s ease; }
div.stButton > button:hover { border-color: var(--sx-teal); color: white; box-shadow: 0 0 18px rgba(35, 212, 203, .14); }
div.stButton > button[kind="primary"] { background: linear-gradient(100deg, #24d8cb, #55d9ee); color: #05202c; border: 0; font-weight: 750; }
div.stButton > button[kind="primary"]:hover { background: linear-gradient(100deg, #5ce8d6, #84e8fa); color: #05202c; }
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: .45rem; border-bottom: 1px solid var(--sx-border); }
[data-testid="stTabs"] button[role="tab"] { color: #9bb4ca; border-radius: 10px 10px 0 0; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color: var(--sx-teal); border-bottom-color: var(--sx-teal); }
[data-testid="stDataFrame"] { border: 1px solid var(--sx-border); border-radius: 12px; overflow: hidden; }
[data-testid="stAlert"] { border-radius: 12px; }
.sx-brand { display:block; width:100%; margin:0 0 1.25rem; padding:.15rem 0 .2rem; position:relative; z-index:1; }
.sx-wordmark { display:block; color:#f2fbff !important; opacity:1 !important; font-size:1.75rem; line-height:1.18; letter-spacing:.15em; font-weight:850; white-space:nowrap; text-shadow:0 0 22px rgba(63,213,230,.16); }
.sx-wordmark span { color:#36ddd2 !important; }
.sx-kicker { display:block; margin-top:.3rem; color:#8bb8cc !important; opacity:1 !important; text-transform:uppercase; letter-spacing:.14em; font-size:.68rem; line-height:1.4; font-weight:700; }
.sx-hero { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:1.1rem 1.25rem; border:1px solid var(--sx-border); border-radius:16px; background:linear-gradient(105deg,rgba(10,38,59,.92),rgba(8,26,44,.70)); margin:0 0 1.2rem; }
.sx-hero-title { font-size:1.35rem; font-weight:750; color:#f0f7ff; margin-bottom:.15rem; }
.sx-hero-sub { color:#94aec4; font-size:.9rem; }
.sx-pill { display:inline-flex; align-items:center; padding:.34rem .65rem; border-radius:99px; color:#67e5dc; background:rgba(35,212,203,.10); border:1px solid rgba(35,212,203,.23); font-size:.71rem; font-weight:700; white-space:nowrap; }
.sx-eyebrow { color:var(--sx-teal); text-transform:uppercase; letter-spacing:.12em; font-size:.68rem; font-weight:750; }
.sx-report-title { font-size:1.35rem; line-height:1.3; font-weight:750; color:#f2f8ff; margin:.3rem 0; }
.sx-muted { color:var(--sx-muted); font-size:.85rem; }
hr { border-color:var(--sx-border) !important; }
@media (max-width: 800px) { [data-testid="stMainBlockContainer"] { padding: 2rem .8rem 2rem; } .sx-wordmark { font-size:1.5rem; } .sx-hero { align-items:flex-start; flex-direction:column; } }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="sx-brand"><div class="sx-wordmark">SIGNAL<span>X</span></div><div class="sx-kicker">Find the signal · Verify the truth</div></div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div class='sx-eyebrow'>Research workspace</div>", unsafe_allow_html=True)
    st.caption("Optional AI interpretation: available" if GEMINI_API_KEY else "AI interpretation unavailable · deterministic analysis")
    with st.expander("Open checked sample report"):
        st.caption("Saved sample evidence only. This does not perform live research.")
        if st.button("Load sample report", width="stretch"):
            st.session_state["result"] = demo_result()
            st.rerun()
    history = load_results(HISTORY_PATH, limit=10)
    if history:
        st.divider()
        st.markdown("<div class='sx-eyebrow'>Recent research</div>", unsafe_allow_html=True)
        choice = st.selectbox("Open saved run", options=[None] + list(range(len(history))),
                              format_func=lambda value: "Choose a saved run" if value is None else f"{history[value].created_at:%Y-%m-%d %H:%M} · {history[value].question[:55]}")
        if choice is not None and st.button("Open saved run", width="stretch"):
            st.session_state["result"] = history[choice]
    st.divider()
    st.markdown("<div class='sx-muted'>Evidence first.<br>Always.</div>", unsafe_allow_html=True)

st.markdown("""
<div class="sx-hero"><div><div class="sx-hero-title">Research with a clear source trail.</div><div class="sx-hero-sub">Ask a question. SignalX searches, retrieves, calculates, and shows what the evidence can and cannot support.</div></div><span class="sx-pill">PUBLIC SOURCES · TRACEABLE RESULTS</span></div>
""", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("<div class='sx-eyebrow'>Start a research run</div>", unsafe_allow_html=True)
    question = st.text_area("Research question", placeholder="How does Microsoft's revenue growth compare with operating cash flow, and what public evidence could explain a divergence?", height=115, label_visibility="collapsed")
    company = st.text_input("Company or ticker (optional)", placeholder="e.g. Microsoft or MSFT")
    st.caption("Uses current public search. SEC EDGAR financial facts are requested when a supported US ticker is identified.")
    run_clicked = st.button("Start Research  →", type="primary", width="stretch")

if run_clicked:
    if not question.strip() and not company.strip():
        st.error("Enter a research question or a company/ticker first.")
    else:
        st.session_state.pop("result", None)
        search_stage = st.status("Starting research", expanded=True)
        try:
            search_stage.write("Preparing the research plan…")
            labels = {"plan": "Research planning completed", "search": "Public web search completed",
                      "fetch": "Page retrieval completed", "extract": "Financial data review",
                      "analyze": "Python analysis", "verify": "Evidence review completed"}
            def show_stage(name, state):
                search_stage.write(f"{labels.get(name, name.title())}: {state}")
            result = run_research(question.strip() or company.strip(), company=company,
                                  on_stage=show_stage)
            st.session_state["result"] = result
            search_failed = result.stage_status.get("search") == "failed"
            fetch_failed = result.stage_status.get("fetch") == "failed"
            search_count = next((line.rsplit(":", 1)[-1].strip() for line in result.trace
                                 if line.startswith("Public search completed:")), None)
            if search_failed or fetch_failed:
                search_stage.update(label="Research completed with retrieval errors", state="error", expanded=True)
            else:
                label = "Research completed" if search_count != "0 unique result(s)" else "Research completed · no search results"
                search_stage.update(label=label, state="complete", expanded=False)
        except Exception as exc:
            search_stage.update(label="Public search failed", state="error", expanded=True)
            st.error(f"Could not search the public web: {exc}. Check internet access and try again.")

if "result" in st.session_state:
    result: ResearchResult = st.session_state["result"]
    report = render_report(result)
    st.divider()
    if result.mode.startswith("Demo"):
        st.warning("DEMO — SAVED EVIDENCE. This view loads the checked dataset stored in the project; it does not search the live web, and the sample figures are illustrative.")

    title_left, title_right = st.columns([4, 1])
    with title_left:
        st.markdown("<div class='sx-eyebrow'>Research report</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='sx-report-title'>{result.question}</div>", unsafe_allow_html=True)
        st.caption(f"{result.mode}  ·  {result.created_at:%d %b %Y, %H:%M UTC}")
    with title_right:
        st.download_button("↓  Download report", report, file_name="signalx_report.md", mime="text/markdown", width="stretch")

    if result.stage_status:
        with st.container(border=True):
            status_cols = st.columns(4)
            status_items = list(result.stage_status.items())
            for index, (stage, value) in enumerate(status_items):
                with status_cols[index % 4]:
                    st.metric(stage.replace("_", " ").title(), value)
            if result.stage_status.get("search") == "failed":
                st.error("Public web search failed. Review the research trace; no search results were fabricated.")
            if result.stage_status.get("fetch") == "failed":
                st.error("Page retrieval failed. Review the evidence records and limitations.")

    overview_tab, evidence_tab, verification_tab, methods_tab = st.tabs(["Overview", "Evidence & sources", "Verification", "Method & trace"])

    with overview_tab:
        st.markdown("#### Key takeaway")
        st.write(result.summary)
        if result.ai_interpretation:
            with st.expander("Exploratory AI interpretation · unverified"):
                st.warning("Model output is an unverified hypothesis. Check all factual statements against the linked evidence.")
                st.write(result.ai_interpretation)
        if result.metrics:
            st.markdown("#### Key calculations")
            metric_cols = st.columns(min(4, len(result.metrics)))
            for index, metric in enumerate(result.metrics):
                metric_value = f"{metric.value:,.0f}" if abs(metric.value) >= 1_000_000 else f"{metric.value:g}"
                with metric_cols[index % len(metric_cols)]:
                    st.metric(metric.name, f"{metric_value} {metric.unit}")
                    st.caption(metric.period)
            with st.expander("Calculation details and source IDs"):
                for metric in result.metrics:
                    st.markdown(f"**{metric.name}** · {metric.period}")
                    st.code(metric.calculation, language=None)
                    st.caption("Evidence: " + (", ".join(metric.source_ids) or "Unavailable"))
        else:
            st.info("No comparable financial metric was available for calculation in this run.")
        st.markdown("#### Candidate findings")
        if result.findings:
            for finding in result.findings:
                cited = ", ".join(f"`{source_id}`" for source_id in finding.evidence_ids) or "No evidence IDs"
                st.markdown(f"**{finding.kind.title()} · {finding.confidence} confidence**  \n{finding.claim}  \nEvidence: {cited}")
        else:
            st.info("No evidence-backed findings were produced.")

    with evidence_tab:
        st.markdown("#### Evidence & sources")
        st.caption("Retrieved sources are not automatically verified. Original source URLs are retained.")
        if result.evidence:
            rows = [{"ID": e.evidence_id, "Title": e.title, "Publisher": e.publisher,
                     "Published": e.published_at or "Unavailable", "Extracted": e.extraction_status,
                     "Retrieval": e.retrieval_status, "Verification": e.verification_status,
                     "Source URL": e.url, "Excerpt": e.excerpt, "Retrieval error": e.error or ""}
                    for e in result.evidence]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         column_config={"Source URL": st.column_config.LinkColumn("Original source URL", display_text="Open source")})
        else:
            st.info("No source pages were retrieved.")

    with verification_tab:
        st.markdown("#### Claim review")
        if result.verifications:
            for item in result.verifications:
                with st.container(border=True):
                    st.markdown(f"**{item.verification_status.replace('_', ' ').title()}**  ·  {item.claim}")
                    st.caption("Supporting: " + (", ".join(item.supporting_evidence_ids) or "None") +
                               "  ·  Corroborating: " + (", ".join(item.corroborating_evidence_ids) or "None found") +
                               "  ·  Disconfirming: " + (", ".join(item.disconfirming_evidence_ids) or "None found"))
                    for gap in item.evidence_gaps:
                        st.write("Evidence gap: " + gap)
                    for discrepancy in item.discrepancies:
                        st.warning("Discrepancy: " + discrepancy)
                    for alternative in item.alternative_hypotheses:
                        st.write("Alternative hypothesis (unverified): " + alternative)
        else:
            st.info("No candidate findings were available for structured verification.")
        st.markdown("#### Counterarguments and discrepancies")
        if result.contradictions:
            for item in result.contradictions:
                st.warning(item)
        else:
            st.caption("No automated contradiction flags; this does not establish agreement.")
        alternatives = [alt for verification in result.verifications for alt in verification.alternative_hypotheses]
        for alternative in alternatives:
            st.write("• " + alternative)
        if not alternatives:
            st.write(result.counter_hypothesis)

    with methods_tab:
        st.markdown("#### Research plan")
        for index, step in enumerate(result.plan, 1):
            st.write(f"{index}. {step}")
        st.markdown("#### Hypotheses")
        for hypothesis in result.hypotheses:
            st.write("• " + hypothesis)
        st.markdown("#### Limitations")
        for limitation in result.limitations:
            st.write("• " + limitation)
        st.markdown("#### Research trace")
        for step in result.trace:
            st.write("› " + step)

    save_col, _ = st.columns([1, 4])
    with save_col:
        if st.button("Save report to project", width="stretch"):
            try:
                path = ROOT / "data" / "reports" / "latest_report.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(report, encoding="utf-8")
                save_result(result, HISTORY_PATH)
                st.success(f"Report and trace saved locally: {path}")
            except OSError as exc:
                st.error(f"Could not save report: {exc}")
