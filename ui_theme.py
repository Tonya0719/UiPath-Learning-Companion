"""Presentation-only NTU-inspired styling; keep colours and group credits here."""
from html import escape
import streamlit as st

# NTU public Quick Brand Guide (2018): red D71440, blue 181C62.
NAVY = '#181C62'
RED = '#D71440'
MEMBERS = ('Fang Xinyi', 'Li Zihao', 'Miao Jiaxuan', 'Wang Chenyu',
           'Wang Senmiao', 'Wu Yushan')


def apply_theme():
    st.markdown('''<style>
    /* Keep Streamlit's live theme as the source of background/text colours.
       currentColor adapts immediately, including menu and system changes. */
    .stApp {--course-border:color-mix(in srgb,currentColor 22%,transparent);}
    [data-testid="stSidebar"] {border-right:1px solid var(--course-border);}
    [data-testid="stMainBlockContainer"] {max-width:1200px;}
    h1 {letter-spacing:-0.025em;}
    [data-testid="stForm"] {background:color-mix(in srgb,currentColor 3%,transparent);border-color:var(--course-border);border-radius:14px;}
    [data-testid="stTabs"] [role="tablist"] {gap:16px;border-bottom:1px solid var(--course-border);}
    [data-testid="stTabs"] [role="tab"] {padding:12px 8px;}
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {font-weight:700;}
    [data-baseweb="tab-highlight"] {background:#D71440;}
    [data-testid="stFormSubmitButton"] button {background:#D71440;color:white;border:1px solid #D71440;}
    [data-testid="stFormSubmitButton"] button:hover {background:#b91036;color:white;border-color:#b91036;}
    [data-testid="stFormSubmitButton"] button:disabled {opacity:0.55;}
    [data-testid="stButton"] button {border-color:var(--course-border);}
    [data-testid="stButton"] button:hover {border-color:currentColor;background:color-mix(in srgb,currentColor 8%,transparent);}
    button:focus-visible,a:focus-visible {outline:3px solid #6799d0;outline-offset:3px;}
    .course-brand {display:flex;flex-wrap:wrap;align-items:center;gap:12px;
      border-top:4px solid #D71440;padding-top:16px;margin-bottom:12px;
      font-size:12px;font-weight:700;letter-spacing:0.08em;}
    .course-brand span {background:#181C62;color:white;border-radius:5px;padding:5px 9px;}
    .course-footer {margin-top:44px;padding:24px 4px 12px;border-top:2px solid #6799d0;
      font-size:13px;line-height:1.9;}
    .course-members {display:flex;flex-wrap:wrap;gap:4px 20px;margin:8px 0;}
    .course-footer small {font-size:12px;}
    .st-key-practice_question_card {
      background:rgba(103,153,208,0.14);border:1px solid #6799d0;
      border-left:4px solid #6799d0;border-radius:12px;
      padding:20px 24px;margin:12px 0 20px;}
    .st-key-practice_question_card [data-testid="stForm"] {
      background:transparent;padding:0;border:0;}
    .question-eyebrow {font-size:12px;font-weight:600;letter-spacing:1px;margin-bottom:10px;}
    .question-stem {font-size:18px;line-height:1.8;white-space:pre-wrap;
      overflow-wrap:anywhere;margin-bottom:12px;}
    @media(max-width:640px) {.course-members {gap:4px 14px;}}
    </style>''', unsafe_allow_html=True)
    st.markdown('<div class="course-brand"><span>PE6203 A1</span> GROUP 5 · NTU STUDENT PROJECT</div>', unsafe_allow_html=True)


def render_footer():
    names = ''.join('<span>' + escape(name) + '</span>' for name in MEMBERS)
    st.markdown('<footer class="course-footer" aria-label="Project credits">'
                '<strong>PE6203 A1 · Group 5</strong>'
                '<div class="course-members">' + names + '</div>'
                '<div>© 2026 Group 5. All rights reserved.</div>'
                '<small>Student coursework project · 非 NTU 官方服务</small>'
                '</footer>', unsafe_allow_html=True)
