from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

# -----------------------------
# Import your LangGraph app
# -----------------------------
from backend import app   # <-- your compiled graph


# -----------------------------
# Helpers
# -----------------------------
def safe_slug(title: str) -> str:
    return (
        title.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .strip("_")
    )


def try_stream(graph_app, inputs: Dict[str, Any]):
    """
    Stream graph updates if supported, otherwise fallback to invoke().
    """
    try:
        for step in graph_app.stream(inputs, stream_mode="updates"):
            yield ("updates", step)
        yield ("final", graph_app.invoke(inputs))
        return
    except Exception:
        pass

    yield ("final", graph_app.invoke(inputs))


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="LangGraph Blog Writer", layout="wide")
st.title("📝 Blog Writing Agent")

# Sidebar
with st.sidebar:
    st.header("Generate Blog")

    topic = st.text_area(
        "Topic",
        height=120,
        placeholder="e.g. State of Multimodal LLMs in 2026",
    )

    as_of = st.date_input("As-of date", value=date.today())
    run_btn = st.button("🚀 Generate Blog", type="primary")

# Session storage
if "last_out" not in st.session_state:
    st.session_state["last_out"] = None

logs: List[str] = []

def log(msg: str):
    logs.append(msg)

# Tabs
tab_plan, tab_evidence, tab_preview, tab_logs = st.tabs(
    ["🧩 Plan", "🔎 Evidence", "📝 Markdown Preview", "🧾 Logs"]
)

# -----------------------------
# Run graph
# -----------------------------
if run_btn:
    if not topic.strip():
        st.warning("Please enter a topic.")
        st.stop()

    inputs = {
        "topic": topic.strip(),
        "mode": "",
        "needs_research": False,
        "queries": [],
        "evidence": [],
        "plan": None,
        "sections": [],
        "final": "",
    }

    status = st.status("Running LangGraph…", expanded=True)
    current_state: Dict[str, Any] = {}

    for kind, payload in try_stream(app, inputs):
        log(f"[{kind}] {str(payload)[:1000]}")

        if kind == "updates" and isinstance(payload, dict):
            current_state.update(
                next(iter(payload.values())) if len(payload) == 1 else payload
            )

            status.write(
                f"➡️ Mode: {current_state.get('mode')} | "
                f"Evidence: {len(current_state.get('evidence', []))} | "
                f"Sections: {len(current_state.get('sections', []))}"
            )

        elif kind == "final":
            st.session_state["last_out"] = payload
            status.update(label="✅ Done", state="complete", expanded=False)

# -----------------------------
# Render output
# -----------------------------
out = st.session_state.get("last_out")

if out:
    # -------- Plan --------
    with tab_plan:
        st.subheader("Plan")

        plan = out.get("plan")
        if not plan:
            st.info("No plan returned.")
        else:
            if hasattr(plan, "model_dump"):
                plan = plan.model_dump()

            st.write("**Title:**", plan.get("blog_title"))
            cols = st.columns(3)
            cols[0].write("**Audience:** " + plan.get("audience", ""))
            cols[1].write("**Tone:** " + plan.get("tone", ""))
            cols[2].write("**Type:** " + plan.get("blog_kind", ""))

            tasks = plan.get("tasks", [])
            if tasks:
                df = pd.DataFrame(
                    [
                        {
                            "ID": t["id"],
                            "Title": t["title"],
                            "Words": t["target_words"],
                            "Research": t["requires_research"],
                            "Citations": t["requires_citations"],
                            "Code": t["requires_code"],
                        }
                        for t in tasks
                    ]
                )
                st.dataframe(df, use_container_width=True, hide_index=True)

    # -------- Evidence --------
    with tab_evidence:
        st.subheader("Evidence")

        evidence = out.get("evidence") or []
        if not evidence:
            st.info("No evidence used.")
        else:
            rows = []
            for e in evidence:
                if hasattr(e, "model_dump"):
                    e = e.model_dump()

                rows.append(
                    {
                        "Title": e.get("title"),
                        "Source": e.get("source"),
                        "Published": e.get("published_at"),
                        "URL": e.get("url"),
                    }
                )

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # -------- Markdown Preview --------
    with tab_preview:
        st.subheader("Markdown Preview")

        final_md = out.get("final", "")
        if not final_md:
            st.warning("No markdown generated.")
        else:
            st.markdown(final_md)

            title = final_md.splitlines()[0].replace("#", "").strip()
            filename = f"{safe_slug(title)}.md"

            st.download_button(
                "⬇️ Download Markdown",
                data=final_md.encode("utf-8"),
                file_name=filename,
                mime="text/markdown",
            )

    # -------- Logs --------
    with tab_logs:
        st.subheader("Execution Logs")
        st.text_area(
            "Logs",
            value="\n\n".join(logs[-80:]),
            height=500,
        )

else:
    st.info("Enter a topic and click **Generate Blog**.")
