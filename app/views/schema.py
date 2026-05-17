"""🧬 Schema Validator — local rules + official validator.schema.org parse.

Two-pane validator:
  • Pane A: our local validator (`validate_schema_org`) — checks rich-result
    eligibility against Google's requirements + Schema.org type rules.
  • Pane B: the official validator (`validate_schema_remote`) — hits
    https://validator.schema.org/ for the canonical parse.

Both run in parallel. No API key needed.
"""
from __future__ import annotations

import json
from urllib.parse import quote as urlquote

import streamlit as st

from app.config import DEFAULT_TARGET_URL
from app.ui_helpers import (
    ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY, logo_html,
)

# Tools imported lazily — the file is heavy
from tools.schema_validator import validate_schema_org, validate_schema_remote

# ================================================================ hero
st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">Structured data</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        🧬 Schema Validator
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Paste a URL or raw JSON-LD. Runs against the official
        <a href="https://validator.schema.org/" target="_blank"
           style="color:{ACCENT};text-decoration:none;">validator.schema.org</a>
        (free, no API key) <em>and</em> Team Mamba's local rule check (Google
        rich-result requirements + recommended properties for every supported
        type).
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ================================================================ input
mode = st.radio(
    "Input mode",
    ["URL", "Paste JSON-LD / HTML"],
    horizontal=True,
    label_visibility="collapsed",
)

url_input = ""
code_input = ""

if mode == "URL":
    url_input = st.text_input(
        "Page URL",
        value=DEFAULT_TARGET_URL,
        placeholder="https://stoptions.ai/some-page",
    )
else:
    code_input = st.text_area(
        "Paste JSON-LD, microdata, or RDFa markup",
        placeholder='{"@context":"https://schema.org","@type":"Article",...}',
        height=200,
    )

run = st.button("Validate", type="primary", use_container_width=True)

st.markdown("---")

# ================================================================ run
def _coloured_pill(label: str, ok: bool) -> str:
    bg = "#143526" if ok else "#3A1A1F"
    fg = "#3DDC97" if ok else "#FF6B6B"
    return (
        f"<span style='display:inline-block;padding:3px 10px;border-radius:999px;"
        f"background:{bg};color:{fg};font-size:0.78rem;font-weight:600;'>"
        f"{label}</span>"
    )


def _types_chips_html(types: dict) -> str:
    if not types:
        return f"<span style='color:{TEXT_MUTED};font-size:0.85rem;'>(none detected)</span>"
    chips = []
    for t, n in sorted(types.items(), key=lambda kv: -kv[1]):
        chips.append(
            f"<span style='display:inline-block;padding:3px 10px;margin:2px;"
            f"border-radius:6px;background:{BG_CARD};border:1px solid {BORDER};"
            f"color:{TEXT_PRIMARY};font-size:0.8rem;'>{t} × {n}</span>"
        )
    return "".join(chips)


if run:
    has_input = (mode == "URL" and url_input.strip()) or \
                (mode == "Paste JSON-LD / HTML" and code_input.strip())
    if not has_input:
        st.warning("Provide a URL or paste some markup first.")
        st.stop()

    col_left, col_right = st.columns(2, gap="medium")

    # ---------------- Pane A: official validator.schema.org ----------------
    with col_left:
        st.markdown(f"#### 🌐 validator.schema.org")
        st.caption("Official Schema.org / Google parser. Authoritative.")
        with st.spinner("Calling validator.schema.org…"):
            try:
                kw = {"url": url_input.strip()} if mode == "URL" else {"code": code_input}
                remote = validate_schema_remote.invoke(kw)
            except Exception as e:  # noqa: BLE001
                remote = {"ok": False, "error": str(e)}

        if not remote.get("ok"):
            st.error(f"Validator error: {remote.get('error', 'unknown')}")
            if remote.get("body_preview"):
                with st.expander("Response preview"):
                    st.code(remote["body_preview"])
        else:
            valid = remote.get("overall_valid", False)
            st.markdown(
                _coloured_pill(
                    f"{'✅ Valid' if valid else '⚠ ' + str(remote.get('num_errors', 0)) + ' issue(s)'}",
                    valid,
                ),
                unsafe_allow_html=True,
            )

            c1, c2 = st.columns(2)
            c1.metric("Nodes parsed", remote.get("num_nodes", 0))
            c2.metric("Errors", remote.get("num_errors", 0))

            st.markdown("**Types found**")
            st.markdown(_types_chips_html(remote.get("types_found", {})),
                        unsafe_allow_html=True)

            errs = remote.get("errors") or []
            if errs:
                with st.expander(f"⚠ {len(errs)} error(s) from schema.org",
                                 expanded=True):
                    for e in errs[:30]:
                        st.markdown(f"- {e}")
                    if len(errs) > 30:
                        st.caption(f"…and {len(errs) - 30} more.")

            with st.expander(f"📦 {remote.get('num_nodes', 0)} parsed node(s)"):
                for i, node in enumerate(remote.get("nodes", []), start=1):
                    st.markdown(f"**Node {i} — `{node.get('type', '?')}`**")
                    props = node.get("properties", [])
                    if not props:
                        st.caption("(no properties)")
                        continue
                    for p in props:
                        st.markdown(
                            f"- **{p['property']}**: `{p['value']}`"
                            if p.get("property") else f"- `{p.get('value','')}`"
                        )
                    st.markdown("")

            if remote.get("deep_link"):
                st.link_button(
                    "↗ Open in validator.schema.org",
                    remote["deep_link"],
                    use_container_width=True,
                )

    # ---------------- Pane B: local rich-result rule check ----------------
    with col_right:
        st.markdown(f"#### 📋 Local rich-result rules")
        st.caption("Team Mamba's check: Google rich-result requirements + best practice.")

        if mode != "URL":
            st.info("Local check needs a URL (it fetches the page). "
                    "Switch to URL mode to also run it.")
        else:
            with st.spinner("Running local validator…"):
                try:
                    local = validate_schema_org.invoke({"url": url_input.strip()})
                except Exception as e:  # noqa: BLE001
                    local = {"ok": False, "error": str(e)}

            if not local.get("ok"):
                st.error(f"Local validator error: {local.get('error', 'unknown')}")
            else:
                valid = local.get("overall_valid", False)
                st.markdown(
                    _coloured_pill(
                        f"{'✅ Valid' if valid else '⚠ ' + str(local.get('total_issues', 0)) + ' issue(s)'}",
                        valid,
                    ),
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns(3)
                c1.metric("JSON-LD blocks", local.get("json_ld_blocks", 0))
                c2.metric("Issues", local.get("total_issues", 0))
                c3.metric("Warnings", local.get("total_warnings", 0))

                st.markdown("**Types found**")
                st.markdown(_types_chips_html(local.get("types_found", {})),
                            unsafe_allow_html=True)

                for i, block in enumerate(local.get("per_block", []) or [], start=1):
                    types = ", ".join(block.get("types", [])) or "(no @type)"
                    issues = block.get("issues", [])
                    warnings = block.get("warnings", [])
                    badge = "✅" if not issues else "⚠"
                    with st.expander(
                        f"{badge} Block {i} — {types}  ·  "
                        f"{len(issues)} issue(s), {len(warnings)} warning(s)",
                        expanded=bool(issues),
                    ):
                        if issues:
                            st.markdown("**Issues (block rich-result eligibility):**")
                            for x in issues:
                                st.markdown(f"- {x}")
                        if warnings:
                            st.markdown("**Warnings (recommended properties missing):**")
                            for x in warnings:
                                st.markdown(f"- {x}")
                        if not (issues or warnings):
                            st.caption("Clean — all required + recommended props present.")

            # Google Rich Results Test deep link (no API but one-click)
            rr_url = (
                "https://search.google.com/test/rich-results?url="
                + urlquote(url_input.strip(), safe="")
            )
            st.link_button(
                "↗ Also test on Google Rich Results Test",
                rr_url,
                use_container_width=True,
            )

else:
    st.markdown(
        f"<div style='color:{TEXT_MUTED};font-size:0.88rem;'>"
        "Enter a URL or paste markup above and click <strong>Validate</strong>. "
        "Both validators run in parallel."
        "</div>",
        unsafe_allow_html=True,
    )
