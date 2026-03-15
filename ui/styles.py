"""Global CSS for Artificier."""

import streamlit as st


def inject_styles() -> None:
    st.markdown(
        """
    <style>
    .artificier-card {
        border: 1px solid var(--default-border-color, #ddd);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        background: var(--background-secondary, #fafafa);
    }
    .artificier-card h3 { margin-top: 0; }
    .artificier-read-aloud {
        font-style: italic;
        padding: 1rem;
        background: var(--background-tertiary, #f0f0f0);
        border-left: 4px solid #666;
        margin: 0.5rem 0;
    }
    .artificier-dm-notes {
        padding: 0.5rem;
        background: #fffbe6;
        border-left: 4px solid #faad14;
        margin: 0.5rem 0;
    }
    details { margin: 0.5rem 0; }
    .stExpander summary { font-weight: 600; }
    </style>
    """,
        unsafe_allow_html=True,
    )
