"""Global CSS for Artificier."""

import streamlit as st


def inject_styles(theme: str = "Light") -> None:
    dark = str(theme).lower() == "dark"
    css_vars = """
    :root {
        --art-bg-primary: #0f172a;
        --art-bg-secondary: #111827;
        --art-bg-tertiary: #1f2937;
        --art-text-primary: #e5e7eb;
        --art-border: #334155;
        --art-accent: #7dd3fc;
        --art-warning-bg: #3f2f1b;
        --art-warning-border: #fbbf24;
        --art-button-bg: #1e293b;
        --art-button-bg-hover: #334155;
        --art-button-text: #e5e7eb;
        --art-button-border: #475569;
        --art-button-primary-bg: #0284c7;
        --art-button-primary-bg-hover: #0369a1;
        --art-button-primary-text: #f8fafc;
    }
    """ if dark else """
    :root {
        --art-bg-primary: #ffffff;
        --art-bg-secondary: #fafafa;
        --art-bg-tertiary: #f0f0f0;
        --art-text-primary: #111827;
        --art-border: #d9d9d9;
        --art-accent: #2563eb;
        --art-warning-bg: #fffbe6;
        --art-warning-border: #faad14;
        --art-button-bg: #f8fafc;
        --art-button-bg-hover: #f1f5f9;
        --art-button-text: #0f172a;
        --art-button-border: #cbd5e1;
        --art-button-primary-bg: #2563eb;
        --art-button-primary-bg-hover: #1d4ed8;
        --art-button-primary-text: #ffffff;
    }
    """
    st.markdown(
        """
    <style>
    """
        + css_vars
        + """
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
        background: var(--art-bg-primary);
        color: var(--art-text-primary);
    }
    [data-testid="stHeader"] {
        background: var(--art-bg-primary);
        border-bottom: 1px solid var(--art-border);
    }
    [data-testid="stToolbar"] {
        background: transparent;
    }
    [data-testid="stDecoration"] {
        background: var(--art-bg-primary);
    }
    [data-testid="stStatusWidget"] {
        background: transparent;
    }
    [data-testid="stSidebarContent"] {
        background: var(--art-bg-secondary);
    }
    h1, h2, h3, h4, h5, h6, p, li, label {
        color: var(--art-text-primary);
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--art-border);
    }
    .stButton > button,
    button[kind="secondary"],
    button[data-testid="baseButton-secondary"],
    button[data-testid="stBaseButton-secondary"] {
        background: var(--art-button-bg) !important;
        color: var(--art-button-text) !important;
        border: 1px solid var(--art-button-border) !important;
        border-radius: 8px;
    }
    .stButton > button:hover,
    button[kind="secondary"]:hover,
    button[data-testid="baseButton-secondary"]:hover,
    button[data-testid="stBaseButton-secondary"]:hover {
        background: var(--art-button-bg-hover) !important;
        border-color: var(--art-accent) !important;
        color: var(--art-button-text) !important;
    }
    .stButton > button:focus,
    .stButton > button:focus-visible,
    button[kind="secondary"]:focus,
    button[kind="secondary"]:focus-visible,
    button[data-testid="baseButton-secondary"]:focus,
    button[data-testid="baseButton-secondary"]:focus-visible,
    button[data-testid="stBaseButton-secondary"]:focus,
    button[data-testid="stBaseButton-secondary"]:focus-visible {
        box-shadow: 0 0 0 0.2rem color-mix(in srgb, var(--art-accent) 30%, transparent);
        border-color: var(--art-accent) !important;
        color: var(--art-button-text) !important;
    }
    .stButton > button[kind="primary"],
    button[data-testid="baseButton-primary"],
    button[data-testid="stBaseButton-primary"] {
        background: var(--art-button-primary-bg) !important;
        color: var(--art-button-primary-text) !important;
        border: 1px solid var(--art-button-primary-bg) !important;
    }
    .stButton > button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        background: var(--art-button-primary-bg-hover) !important;
        border-color: var(--art-button-primary-bg-hover) !important;
        color: var(--art-button-primary-text) !important;
    }
    .artificier-card {
        border: 1px solid var(--art-border);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        background: var(--art-bg-secondary);
    }
    .artificier-card h3 { margin-top: 0; }
    .artificier-read-aloud {
        font-style: italic;
        padding: 1rem;
        background: var(--art-bg-tertiary);
        border-left: 4px solid var(--art-accent);
        margin: 0.5rem 0;
    }
    .artificier-dm-notes {
        padding: 0.5rem;
        background: var(--art-warning-bg);
        border-left: 4px solid var(--art-warning-border);
        margin: 0.5rem 0;
    }
    details { margin: 0.5rem 0; }
    .stExpander summary { font-weight: 600; }
    </style>
    """,
        unsafe_allow_html=True,
    )
