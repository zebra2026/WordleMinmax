"""
Wordle Minmax Analyzer — Streamlit UI
======================================
Web front-end for the wordle_minmax_CLI_newdetailed engine.

HOW TO RUN:
    streamlit run wordle_app.py

REQUIRES:
    wordle_minmax_CLI_newdetailed.py   — engine (same directory)
    wordle-answers-alphabetical.txt    — answer word list (same directory)
    nyt-wordle-allowed-guesses-2026-03-06.txt — allowed guesses list
    pip install streamlit requests pandas

DEPLOYMENT:
    Streamlit Cloud : push all 4 files to a GitHub repo,
                      connect at share.streamlit.io

Author: Dr. Victor & Claude (Anthropic)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHANGELOG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

v1.0 — Initial Streamlit UI
    Two-column layout: Wordle board (left) + guess input (right).
    Wordle board renders previous guesses as colored tiles using
    inline CSS (gray/yellow/green), matching real Wordle appearance.
    Guess input: text box + 5 tile buttons that cycle colors
    Gray → Yellow → Green → Gray on each click.
    Submit button validates input, updates constraints via engine,
    filters answer_pool, appends guess to board.
    New Game button resets all session state.
    Word lists loaded once at startup via @st.cache_resource —
    answer list (~2315 words) and allowed list (~10638 words).

    Analysis section (shown after first guess):
      Candidate grid — all remaining words displayed as a code
        block, 10 per line, alphabetical, uppercase.
      Rankings — st.dataframe table, top 20 from answer list,
        columns: Word, Worst, #Worst, Buckets, Solve%, P(>5), Unique.
        ✓ suffix on Word if it is also a valid candidate.
      Radio toggle "Answer list only / Both lists" — when Both is
        selected, answer list and allowed list rankings are merged
        into one table with a Source column (Answer / Allowed),
        sorted by Worst ascending so best guesses from either list
        interleave naturally. Toggling rerenders instantly with no
        resubmit needed.
      Bucket detail panel — text input accepts any 5-letter word;
        renders a DataFrame showing Pattern / Size / Odds / Words
        for every bucket, live as you type. Does not affect game state.

    Replaced all custom HTML/CSS table rendering (which caused raw
    HTML to display as text in Streamlit) with native st.dataframe()
    widgets throughout. Board tiles are the only remaining use of
    st.markdown(unsafe_allow_html=True), using inline styles only.

v1.2 — Tile display, copy buttons, iOS keyboard, multi-guess fix
    INPUT REDESIGN (hybrid approach — reliable across all platforms):
      The input widget uses a two-layer architecture:
        Layer 1 (visual): st.markdown renders 5 colored tiles showing
          the current letter and color state — purely cosmetic, no
          data flow through this layer.
        Layer 2 (data): st.text_input captures the typed word via
          Streamlit's WebSocket, preserving session state across
          reruns. Five st.button widgets cycle each tile's color.
          Submit button triggers engine processing.
      This hybrid avoids the session-state-wipe bug caused by
      location.reload() in the earlier pure-JS approach, where
      full browser reloads destroyed Streamlit session state after
      the first guess.

    TILE COLOR CYCLE BEHAVIOR:
      ⬛ Gray → 🟨 Yellow → 🟩 Green → clears letter (resets to gray)
      Matches Wordlewise behavior — clicking green removes the letter.

    COPY BUTTONS:
      📋 Copy button added below the ranking table and bucket detail
      table. Text is base64-encoded in Python before passing to JS
      (avoids unicode escape issues with emoji and special chars).
      Button label briefly shows ✅ Copied! on success.
      Ranking copy: fixed-width plain text table with ASCII dashes.
      Bucket detail copy: pattern + size + odds + words per line.

    DUPLICATE ROW FIX (Both lists mode):
      The OG cfreshman allowed list overlaps with the answer list —
      all 2315 answer words appear in both files. Merged table now
      deduplicates by word (keeping Answer-tagged row), preventing
      every answer-list word from appearing twice.

    iOS CHROME COLUMN TOGGLE FIX:
      Added unique key= to both ranking dataframes so Streamlit
      creates a fresh widget on toggle rather than reusing the old
      one, which caused columns to disappear on iOS Chrome.

    WORD LIST CHANGE (engine v1.5):
      Switched allowed list from NYT combined list (14855 words,
      fully overlapping) to OG cfreshman list (~10657 words, truly
      separate). Local filename changed to wordle-allowed-guesses.txt.

    PROBLEM: Rightmost column was clipped or hidden on narrower
    screens; vertical scrollbar consumed pixels from the last column
    in the 40-row merged table.

    FIX — three changes:
      Column order revised to match user priority ranking:
        Word, Worst, Solve%, P(>5), #Worst, Unique, Buckets
        (Source inserted after Word in merged mode)
        Most important columns are leftmost — visible before
        horizontal scrolling is needed on mobile.
      use_container_width=False — table no longer stretches to fill
        the container. When table is wider than the viewport,
        Streamlit adds a horizontal scrollbar instead of squishing
        columns. Users can swipe to see all columns on mobile.
      Explicit pixel widths on all columns via column_config to
        prevent Streamlit auto-sizing from making columns too wide
        or too narrow.
      TABLE_HEIGHT = 740px — fixed height with internal vertical
        scrollbar so the table does not grow the page height when
        showing 40 merged rows.
"""

import streamlit as st
import pandas as pd
import wordle_minmax_CLI_newdetailed as engine

# ─────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🍦 Jeni's Wordle Analyzer",
    page_icon="🍦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────
# MINIMAL GLOBAL STYLING  (only things Streamlit reliably applies)
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.board-row   { display:flex; gap:6px; justify-content:center; margin-bottom:6px; }
.tile        { width:52px; height:52px; border-radius:4px; display:flex;
               align-items:center; justify-content:center;
               font-size:1.3rem; font-weight:700; color:white; }
.tile-green  { background:#538d4e; }
.tile-yellow { background:#b59f3b; }
.tile-gray   { background:#787c7e; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# WORD LIST LOADING  (cached — loads once, reused every rerun)
# ─────────────────────────────────────────────────────────────────
@st.cache_resource
def load_lists():
    answer_list  = engine.load_answer_list()
    allowed_list = engine.load_allowed_list()
    return answer_list, allowed_list

with st.spinner("Loading word lists…"):
    answer_list, allowed_list = load_lists()


# ─────────────────────────────────────────────────────────────────
# SESSION STATE INITIALISATION
# ─────────────────────────────────────────────────────────────────
def reset_game():
    st.session_state.constraints  = {}
    st.session_state.answer_pool  = answer_list[:]
    st.session_state.guess_number = 1
    st.session_state.board        = []
    st.session_state.solved       = False
    st.session_state.tile_colors  = [0, 0, 0, 0, 0]
    st.session_state.tile_letters = ["", "", "", "", ""]
    st.session_state.error_msg    = ""

if "constraints" not in st.session_state:
    reset_game()


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────
COLOR_CYCLE = {0: 1, 1: 2, 2: 0}          # gray → yellow → green → gray


# ─────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────
st.title("🍦 Jeni's Wordle Minmax Analyzer")
st.caption("True minimax analysis · Click tiles to cycle colors · Submit to update")
st.divider()


# ─────────────────────────────────────────────────────────────────
# BOARD + INPUT  (two columns)
# ─────────────────────────────────────────────────────────────────
col_board, col_input = st.columns([1, 1.6], gap="large")

# ── Left: Wordle board ──
with col_board:
    st.subheader("Board")
    if not st.session_state.board:
        st.caption("No guesses yet.")
    else:
        for word, pattern in st.session_state.board:
            tiles_html = "".join(
                f'<div class="tile tile-{["gray","yellow","green"][c]}">'
                f'{ch.upper()}</div>'
                for ch, c in zip(word, pattern)
            )
            st.markdown(
                f'<div class="board-row">{tiles_html}</div>',
                unsafe_allow_html=True
            )

# ── Right: Input ──
with col_input:
    if st.session_state.solved:
        st.success("🎉 Solved! Press New Game to play again.")
    elif st.session_state.guess_number > 6:
        st.warning("😔 Out of guesses. Press New Game to play again.")
    else:
        st.subheader(f"Guess {st.session_state.guess_number} of 6")

        # ── RELIABLE HYBRID INPUT ──
        # Architecture: Streamlit owns all state. The JS component is purely
        # cosmetic — it displays colored tiles. The actual data source is:
        #   - st.text_input  → the word (reliable on all platforms)
        #   - st.button      → one per tile position, cycles color
        #   - st.button      → Submit, triggers engine processing
        #
        # Why not a pure JS component?
        #   Streamlit session state is wiped on full page reloads.
        #   Using location.reload() as a JS→Streamlit bridge causes the
        #   board to reset after every guess. st.text_input + st.button
        #   use Streamlit's WebSocket, which preserves session state.
        #
        # The tile display above the text input mirrors the typed letters
        # and current colors purely for visual feedback — it does not
        # affect the data flow.

        tile_letters = list(st.session_state.tile_letters)
        tile_colors  = list(st.session_state.tile_colors)
        COLOR_BG     = {0: "#787c7e", 1: "#b59f3b", 2: "#538d4e"}

        # ── Colored tile display (visual only) ──
        tile_html = "".join(
            f'<div style="width:56px;height:56px;border-radius:6px;'
            f'background:{COLOR_BG[tile_colors[i]]};'
            f'display:flex;align-items:center;justify-content:center;'
            f'font-size:1.6rem;font-weight:700;color:white;'
            f'border:3px solid {"#aaa" if not tile_letters[i] else COLOR_BG[tile_colors[i]]};">'
            f'{tile_letters[i].upper() if tile_letters[i] else ""}</div>'
            for i in range(5)
        )
        st.markdown(
            f'<div style="display:flex;gap:8px;justify-content:center;'
            f'margin-bottom:10px;">{tile_html}</div>',
            unsafe_allow_html=True
        )

        # ── Word text input ──
        # Single text field — works reliably on iOS, Android, desktop.
        # Letters typed here are reflected in the tile display above.
        word_val = st.text_input(
            "Word",
            value="".join(tile_letters).strip(),
            max_chars=5,
            placeholder="Type your 5-letter guess…",
            label_visibility="collapsed",
            key="word_input",
        ).strip().lower()

        # Sync letters from text input → session state → tile display
        padded = list((word_val + "     ")[:5])
        padded = [c if c.strip() else "" for c in padded]
        st.session_state.tile_letters = padded

        # ── Color cycle buttons ──
        # One per tile position. Clicking cycles Gray→Yellow→Green→clears.
        st.caption("Click to cycle: ⬛ Gray → 🟨 Yellow → 🟩 Green → clears letter")
        btn_cols = st.columns(5)
        COLOR_LABELS = {0: "⬛", 1: "🟨", 2: "🟩"}
        for i, bc in enumerate(btn_cols):
            with bc:
                color = tile_colors[i]
                if st.button(COLOR_LABELS[color], key=f"color_{i}",
                             use_container_width=True):
                    if color == 2:
                        # Green → clear letter AND reset to gray
                        new_letters = list(st.session_state.tile_letters)
                        new_letters[i] = ""
                        st.session_state.tile_letters = new_letters
                        st.session_state.tile_colors[i] = 0
                    else:
                        st.session_state.tile_colors[i] = color + 1
                    st.rerun()

        if st.session_state.get("error_msg"):
            st.error(st.session_state.error_msg)
            st.session_state.error_msg = ""

        # ── Submit ──
        if st.button("▶ Submit Guess", type="primary", use_container_width=True):
            w = word_val
            p = tuple(st.session_state.tile_colors)

            if len(w) != 5 or not w.isalpha():
                st.session_state.error_msg = "Enter a valid 5-letter word."
            elif all(c == 2 for c in p):
                st.session_state.board.append((w, p))
                st.session_state.solved = True
                st.session_state.tile_colors  = [0, 0, 0, 0, 0]
                st.session_state.tile_letters = ["", "", "", "", ""]
            else:
                engine.update_constraints(st.session_state.constraints, w, p)
                st.session_state.answer_pool = engine.filter_candidates(
                    answer_list, st.session_state.constraints
                )
                st.session_state.board.append((w, p))
                st.session_state.guess_number += 1
                st.session_state.tile_colors  = [0, 0, 0, 0, 0]
                st.session_state.tile_letters = ["", "", "", "", ""]
            st.rerun()

    if st.button("↺ New Game"):
        reset_game()
        st.rerun()


# ─────────────────────────────────────────────────────────────────
# ANALYSIS SECTION  (only after at least one guess)
# ─────────────────────────────────────────────────────────────────
if not st.session_state.board:
    st.stop()

st.divider()
answer_pool = st.session_state.answer_pool

# ── Status messages ──
if len(answer_pool) == 0:
    st.warning("⚠️ No candidates remaining — check your tile colors.")
    st.stop()
elif len(answer_pool) == 1:
    st.info(f"🎯 One candidate left: **{answer_pool[0].upper()}**")
    st.stop()

# ── Candidate grid ──
st.subheader(f"{len(answer_pool)} Candidates")
words_sorted = sorted(w.upper() for w in answer_pool)
chunk_size   = 10
rows         = [" · ".join(words_sorted[i:i+chunk_size])
                for i in range(0, len(words_sorted), chunk_size)]
st.code("\n".join(rows), language=None)

st.divider()

# ─────────────────────────────────────────────────────────────────
# RANKINGS
# ─────────────────────────────────────────────────────────────────
st.subheader("Rankings")

ranking_source = st.radio(
    "Ranking source",
    options=["Answer list only", "Both lists"],
    horizontal=True,
    label_visibility="collapsed",
)

def ranking_to_rows(ranking, candidate_set, source_label=None):
    """
    Convert rank_guesses() output to a list of row dicts.
    source_label: if provided, adds a 'Source' column (for merged table).
    """
    rows = []
    for wc, nb, nu, sp, gp, nwb, w in ranking:
        row = {
            "Word"    : w.upper() + (" ✓" if w in candidate_set else ""),
            "Worst"   : wc,
            "#Worst"  : f"{nwb} ❌" if nwb > 1 else str(nwb),
            "Buckets" : nb,
            "Solve%"  : f"{sp:.1f}%",
            "P(>5)"   : f"{gp:.1f}% ❌" if gp >= 50.0 else f"{gp:.1f}%",
            "Unique"  : nu,
        }
        if source_label is not None:
            row["Source"] = source_label
        rows.append(row)
    return rows

def copy_button(text, label="📋 Copy to clipboard"):
    """
    Renders a clipboard copy button via st.components.v1.html.
    The text is base64-encoded to avoid any JS escaping issues with
    special characters (emoji, dashes, etc.).
    """
    import base64
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    st.components.v1.html(f"""
    <button id="cb" style="padding:6px 14px;border:1px solid #ccc;
      border-radius:5px;background:#f8f9fa;cursor:pointer;
      font-size:0.85rem;color:#1a1a2e;margin-top:4px;">
      {label}
    </button>
    <script>
      document.getElementById('cb').addEventListener('click', function() {{
        var b64 = "{b64}";
        var txt = decodeURIComponent(escape(atob(b64)));
        var btn = this;
        if (navigator.clipboard) {{
          navigator.clipboard.writeText(txt).then(function() {{
            btn.textContent = '✅ Copied!';
            setTimeout(function() {{ btn.textContent = '{label}'; }}, 2000);
          }});
        }} else {{
          var ta = document.createElement('textarea');
          ta.value = txt;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
          btn.textContent = '✅ Copied!';
          setTimeout(function() {{ btn.textContent = '{label}'; }}, 2000);
        }}
      }});
    </script>
    """, height=44)


def df_to_copy_text(df, title=""):
    """
    Convert a DataFrame to a clean plain-text table for pasting into
    ChatGPT / Gemini. Uses ASCII dashes to avoid unicode escape issues.
    """
    lines = []
    if title:
        lines.append(title)
        lines.append("-" * len(title))
    cols   = list(df.columns)
    widths = [max(len(str(c)), max((len(str(v)) for v in df[c]), default=0))
              for c in cols]
    lines.append("  ".join(str(c).ljust(w) for c, w in zip(cols, widths)))
    lines.append("  ".join("-" * w for w in widths))
    for _, row in df.iterrows():
        lines.append("  ".join(str(row[c]).ljust(w) for c, w in zip(cols, widths)))
    return "\n".join(lines)


candidate_set = set(answer_pool)

with st.spinner("Computing answer-list ranking…"):
    answer_ranking = engine.rank_guesses(
        guess_pool  = answer_list,
        answer_pool = answer_pool,
        top_n       = 20,
    )

# Column config — explicit widths, ordered by priority.
# Columns are ordered: Word, Worst, Solve%, P(>5), #Worst, Unique, Buckets
# (Source inserted after Word when both lists are shown)
# use_container_width=False + fixed widths = horizontal scroll on narrow screens.
RANKING_COL_CONFIG = {
    "Word"    : st.column_config.TextColumn(   "Word",    width=90),
    "Source"  : st.column_config.TextColumn(   "Source",  width=75),
    "Worst"   : st.column_config.NumberColumn( "Worst",   width=65),
    "Solve%"  : st.column_config.TextColumn(   "Solve%",  width=75),
    "P(>5)"   : st.column_config.TextColumn(   "P(>5)",   width=95),
    "#Worst"  : st.column_config.TextColumn(   "#Worst",  width=75),
    "Unique"  : st.column_config.NumberColumn( "Unique",  width=65),
    "Buckets" : st.column_config.NumberColumn( "Buckets", width=75),
}
TABLE_HEIGHT = 740   # fits 20 rows + header; inner scrollbar avoids page jump

if ranking_source == "Answer list only":
    rows = ranking_to_rows(answer_ranking, candidate_set)
    df   = pd.DataFrame(rows)
    df   = df[["Word", "Worst", "Solve%", "P(>5)", "#Worst", "Unique", "Buckets"]]
    st.caption("Top 20 from answer list  ·  ✓ = word is also a candidate")
    st.dataframe(
        df,
        use_container_width=False,
        hide_index=True,
        height=TABLE_HEIGHT,
        column_config=RANKING_COL_CONFIG,
        key="ranking_df_answers",
    )
    copy_button(df_to_copy_text(df, "Rankings — Answer list"))

else:
    with st.spinner("Computing allowed-list ranking…"):
        burner_ranking = engine.rank_guesses(
            guess_pool  = allowed_list,
            answer_pool = answer_pool,
            top_n       = 20,
        )

    answer_rows = ranking_to_rows(answer_ranking, candidate_set, source_label="Answer")
    burner_rows = ranking_to_rows(burner_ranking, candidate_set, source_label="Allowed")

    # Combine and sort by Worst ascending
    merged_df = (
        pd.concat([pd.DataFrame(answer_rows), pd.DataFrame(burner_rows)], ignore_index=True)
        .sort_values("Worst", kind="stable")
        .reset_index(drop=True)
    )

    # Deduplicate by word — the allowed guesses file contains all answer words
    # too, so without this every answer-list word appears twice. Strip the ✓
    # suffix before comparing, then drop Allowed duplicates (Answer rows sort
    # first because answer_rows was concatenated first, stable sort preserves order).
    merged_df["_key"] = merged_df["Word"].str.replace(" ✓", "", regex=False).str.upper()
    merged_df = (
        merged_df
        .drop_duplicates(subset="_key", keep="first")
        .drop(columns="_key")
        .reset_index(drop=True)
    )

    # Reorder columns by priority (Source after Word)
    merged_df = merged_df[
        ["Word", "Source", "Worst", "Solve%", "P(>5)", "#Worst", "Unique", "Buckets"]
    ]

    st.caption(
        "Top 20 from each list merged · sorted by Worst · deduped  ·  "
        "✓ = valid candidate  ·  Source: Answer / Allowed"
    )
    st.dataframe(
        merged_df,
        use_container_width=False,
        hide_index=True,
        height=TABLE_HEIGHT,
        column_config=RANKING_COL_CONFIG,
        key="ranking_df_merged",
    )
    copy_button(df_to_copy_text(merged_df, "Rankings — Both lists"))

st.divider()

# ─────────────────────────────────────────────────────────────────
# BUCKET DETAIL PANEL
# ─────────────────────────────────────────────────────────────────
st.subheader("Bucket Detail")
detail_word = st.text_input(
    "Word to analyse",
    placeholder="Type any word to see its full bucket breakdown…",
    max_chars=5,
    key="detail_word_input",
).strip().lower()

if detail_word:
    if len(detail_word) != 5 or not detail_word.isalpha():
        st.warning("Enter a 5-letter word.")
    else:
        buckets = engine.bucket_distribution(detail_word, answer_pool)
        total   = len(answer_pool)
        wc      = max(len(v) for _, v in buckets)
        unique  = sum(1 for _, v in buckets if len(v) == 1)
        nb      = len(buckets)
        sp      = nb / total * 100
        gp      = sum(len(v) for _, v in buckets if len(v) > 5) / total * 100

        summary = (f"{detail_word.upper()} — {nb} buckets · "
                   f"worst-case={wc} · unique={unique} · "
                   f"Solve%={sp:.1f}% · P(>5)={gp:.1f}%")
        st.caption(f"**{detail_word.upper()}** — {nb} buckets · "
                   f"worst-case={wc} · unique={unique} · "
                   f"Solve%={sp:.1f}% · P(>5)={gp:.1f}%")

        bucket_rows = []
        copy_lines  = [summary, "-" * len(summary)]
        for p, words in buckets:
            size     = len(words)
            odds     = "certain!" if size == 1 else f"1-in-{size}"
            word_str = " ".join(w.upper() for w in sorted(words))
            bucket_rows.append({
                "Pattern" : engine.pattern_str(p),
                "Size"    : size,
                "Odds"    : odds,
                "Words"   : word_str,
            })
            copy_lines.append(
                f"{engine.pattern_str(p)}  {size:>4}  {odds:<12}  {word_str}"
            )

        bucket_df = pd.DataFrame(bucket_rows)
        st.dataframe(
            bucket_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Pattern": st.column_config.TextColumn(width="small"),
                "Size"   : st.column_config.NumberColumn(width="small"),
                "Odds"   : st.column_config.TextColumn(width="small"),
                "Words"  : st.column_config.TextColumn(width="large"),
            }
        )
        copy_button("\n".join(copy_lines),
                    label=f"📋 Copy {detail_word.upper()} bucket detail")
