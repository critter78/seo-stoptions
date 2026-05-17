"""SEO tools used by the agents.

Each tool is a LangChain `@tool` decorated function so it can be bound to a
Claude / Anthropic model via LangChain's tool-calling interface.
"""
from .web_search import duckduckgo_search
from .web_fetch import fetch_url, extract_visible_text, extract_all_links
from .onpage_audit import onpage_audit
from .schema_extract import extract_structured_data
from .schema_validator import validate_schema_org, validate_schema_remote
from .sitemap_robots import fetch_robots_txt, fetch_sitemap_urls
from .pagespeed import pagespeed_insights
from .webpagetest import webpagetest
from .search_console import (
    gsc_top_queries,
    gsc_url_inspection,
    gsc_sitemap_status,
    gsc_inspect_url_sample,
)
from .google_analytics import (
    ga4_top_pages,
    ga4_traffic_sources,
    ga4_conversions,
    ga4_landing_pages,
    ga4_realtime_active_users,
)
from .content_tools import (
    competitor_content_compare,
    content_gap_analysis,
    eeat_audit,
    topic_cluster_planner,
    internal_link_suggestions,
    content_calendar_add,
    content_calendar_list,
)
from .aeo_scoreboard import check_ai_citations
from .backlinks import find_backlink_signals
from .serp_analyzer import analyze_serp_for_keyword
from .rank_tracker import estimate_keyword_rank

ALL_TOOLS = [
    # Discovery
    duckduckgo_search,
    fetch_url,
    extract_visible_text,
    extract_all_links,
    # On-page & technical
    onpage_audit,
    extract_structured_data,
    validate_schema_org,
    validate_schema_remote,
    fetch_robots_txt,
    fetch_sitemap_urls,
    # Performance
    pagespeed_insights,
    webpagetest,
    # Search Console
    gsc_top_queries,
    gsc_url_inspection,
    gsc_sitemap_status,
    gsc_inspect_url_sample,
    # Google Analytics 4
    ga4_top_pages,
    ga4_traffic_sources,
    ga4_conversions,
    ga4_landing_pages,
    ga4_realtime_active_users,
    # Content
    competitor_content_compare,
    content_gap_analysis,
    eeat_audit,
    topic_cluster_planner,
    internal_link_suggestions,
    content_calendar_add,
    content_calendar_list,
    # AEO
    check_ai_citations,
    # Authority & rank
    find_backlink_signals,
    analyze_serp_for_keyword,
    estimate_keyword_rank,
]
