"""🛠 Tools — browse + run any of the agents' tools manually."""
from __future__ import annotations

import json as _json

import streamlit as st

from app.ui_helpers import ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY, logo_html
from tools import ALL_TOOLS

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">Toolkit</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        🛠 Tools ({len(ALL_TOOLS)})
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Every tool the agents have access to. Run any of them manually with a
        form — great for debugging or learning what each one returns.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Group tools by category
GROUPS = {
    "🔍 Search & discovery": ["duckduckgo_search", "analyze_serp_for_keyword",
                                "estimate_keyword_rank"],
    "🌐 Web fetch & parse": ["fetch_url", "extract_visible_text", "extract_all_links"],
    "📋 On-page audit": ["onpage_audit", "extract_structured_data",
                         "validate_schema_org", "validate_schema_remote",
                         "eeat_audit"],
    "🗺 Crawlability": ["fetch_robots_txt", "fetch_sitemap_urls"],
    "⚡ Performance": ["pagespeed_insights", "webpagetest"],
    "🔵 Search Console": ["gsc_top_queries", "gsc_url_inspection",
                          "gsc_sitemap_status", "gsc_inspect_url_sample"],
    "🟡 Google Analytics 4": ["ga4_top_pages", "ga4_traffic_sources",
                              "ga4_conversions", "ga4_landing_pages",
                              "ga4_realtime_active_users"],
    "📝 Content": ["competitor_content_compare", "content_gap_analysis",
                   "topic_cluster_planner", "internal_link_suggestions",
                   "content_calendar_add", "content_calendar_list"],
    "🔗 Links & authority": ["find_backlink_signals"],
    "🤖 AEO": ["check_ai_citations"],
}

by_name = {t.name: t for t in ALL_TOOLS}

for group_label, tool_names in GROUPS.items():
    st.markdown(f"### {group_label}")
    for tname in tool_names:
        t = by_name.get(tname)
        if not t:
            continue
        with st.expander(f"`{t.name}` — {(t.description or '').splitlines()[0]}"):
            st.markdown(t.description or "_(no description)_")

            # Schema
            schema = t.args_schema.model_json_schema() if t.args_schema else {}
            props = schema.get("properties", {})
            required = set(schema.get("required", []))
            if props:
                st.caption("**Parameters:**")
                args = {}
                for pname, spec in props.items():
                    label = pname + (" *" if pname in required else "")
                    desc = spec.get("description", "")
                    ptype = spec.get("type", "string")
                    default = spec.get("default", "")
                    if ptype == "boolean":
                        args[pname] = st.checkbox(label, value=bool(default),
                                                   key=f"arg_{tname}_{pname}",
                                                   help=desc)
                    elif ptype == "integer":
                        args[pname] = st.number_input(
                            label, value=int(default or 0), step=1,
                            key=f"arg_{tname}_{pname}", help=desc,
                        )
                    elif ptype == "number":
                        args[pname] = st.number_input(
                            label, value=float(default or 0), step=0.1,
                            key=f"arg_{tname}_{pname}", help=desc,
                        )
                    elif ptype == "array":
                        raw = st.text_input(
                            f"{label} (comma-separated)", value=",".join(default or []),
                            key=f"arg_{tname}_{pname}", help=desc,
                        )
                        args[pname] = [x.strip() for x in raw.split(",") if x.strip()]
                    else:
                        args[pname] = st.text_input(
                            label, value=str(default or ""),
                            key=f"arg_{tname}_{pname}", help=desc,
                        )

                if st.button(f"▶️ Run {tname}", key=f"run_{tname}"):
                    # Strip empties for optional fields so defaults apply
                    cleaned = {k: v for k, v in args.items()
                               if not (v in ("", [], None) and k not in required)}
                    with st.spinner("Running…"):
                        try:
                            result = t.invoke(cleaned)
                            st.success("✅ Done")
                            st.json(result)
                        except Exception as e:
                            st.error(f"Error: {e}")
            else:
                if st.button(f"▶️ Run {tname}", key=f"run_{tname}"):
                    with st.spinner("Running…"):
                        try:
                            result = t.invoke({})
                            st.success("✅ Done")
                            st.json(result)
                        except Exception as e:
                            st.error(f"Error: {e}")
