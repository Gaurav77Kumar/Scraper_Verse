"""Streamlit dashboard: trends, latest snapshot, and healing-event timeline."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from scrapeverse.config import load_settings, load_targets
from scrapeverse.store import connect

st.set_page_config(page_title="Scrape-Verse Intel", page_icon="🕸️", layout="wide")

settings = load_settings()
targets = load_targets()
conn = connect(settings.db_path)

st.title("🕸️ Scrape-Verse — Competitive Intel Dashboard")
st.caption("Powered by Bright Data Scraper Studio · self-healing collectors")

snapshots = pd.read_sql(
    "SELECT target, collected_at, row_count, fingerprint FROM snapshots ORDER BY id",
    conn,
)
heals = pd.read_sql(
    "SELECT target, healed_at, issue, recovered FROM healing_events ORDER BY id DESC",
    conn,
)

col1, col2, col3 = st.columns(3)
col1.metric("Targets", len(targets))
col2.metric("Snapshots", len(snapshots))
col3.metric("Healing events", len(heals))

if not snapshots.empty:
    st.subheader("Rows collected over time")
    chart = (
        snapshots.assign(collected_at=pd.to_datetime(snapshots.collected_at))
        .pivot_table(index="collected_at", columns="target", values="row_count")
        .sort_index()
    )
    st.line_chart(chart)

st.subheader("Latest data per target")
for t in targets:
    with st.expander(f"📡 {t.name} — `{t.collector_id}`"):
        cur = conn.execute(
            "SELECT payload FROM snapshots WHERE target = ? ORDER BY id DESC LIMIT 1",
            (t.name,),
        )
        row = cur.fetchone()
        if row:
            st.dataframe(pd.DataFrame(json.loads(row[0])))
        else:
            st.info("No snapshot yet. Run `python -m scrapeverse`.")

if not heals.empty:
    st.subheader("🩹 Self-healing timeline")
    st.dataframe(heals, use_container_width=True)
else:
    st.success("No healing events yet — scrapers have been healthy.")
