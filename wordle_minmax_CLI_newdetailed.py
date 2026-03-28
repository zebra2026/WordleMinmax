"""
Wordle Minmax Analyzer
======================
A tool for computing optimal Wordle guesses using true minimax analysis.
Built for use with the cfreshman Wordle answer list.

WHAT THIS FILE IS:
    A Python "module" — think of it like a .cpp file containing a library
    of functions. Each function does one specific job. The bottom section
    (if __name__ == '__main__') is the equivalent of int main() and only
    runs when you launch this file directly.

HOW TO RUN:
    python wordle_minmax_CLI_newdetailed.py

HOW TO IMPORT (future Streamlit UI):
    import wordle_minmax_CLI_newdetailed as engine
    engine.load_answer_list()      # call any function by name

PYTHON NOTES FOR C/C++ VETERANS:
    - No header files — functions are defined and declared in one place
    - No type declarations — Python infers types at runtime
    - No semicolons — newlines end statements
    - Indentation IS the block structure (replaces { } braces)
    - str  = std::string  (but immutable! can't modify chars in place)
    - list = std::vector  (dynamic, mixed types allowed)
    - dict = std::unordered_map  (key/value pairs, called "dictionary")
    - tuple = fixed-size immutable array (like a const struct)
    - None = nullptr / null

DEPENDENCIES:
    pip install requests    (HTTP library, like libcurl but much simpler)

Author: Dr. Victor & Claude (Anthropic)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHANGELOG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

v1.0 — Initial release
    Core engine: get_pattern(), get_buckets(), worst_case()
    Candidate filtering: filter_candidates() with Rules 1–4
    Constraint tracking: update_constraints() with green/yellow/gray/must_contain
    CLI game loop with GUESS:PATTERN input format
    Dual word list support: answer list + allowed guesses list
    Burner word search: prompted Y/N after each answer-list ranking
    top_n raised to 20 (was 10) for both answer and burner rankings

v1.1 — Bug fix: duplicate-letter upper bound (max_count)
    PROBLEM DISCOVERED: Playing CLOOT after RAISE gave 17 candidates
    instead of the correct 11. The engine's get_buckets() was correct —
    CLOOT's worst-case bucket genuinely had 11 words. But after entering
    the result (O at pos 2 green, O at pos 3 gray), filter_candidates()
    was returning 17 words including BROOD, BROOK, BROOM, DROOP, GROOM,
    PROOF — all of which contain two O's and are therefore impossible.

    ROOT CAUSE: When a letter appears twice in a guess and one copy comes
    back gray, Wordle is signalling that the answer has EXACTLY as many
    of that letter as the non-gray copies. The old update_constraints()
    simply skipped the gray O (because O was already in must_contain),
    so no upper bound was ever recorded. filter_candidates() had no way
    to reject words with too many O's.

    FIX — two changes:
      update_constraints(): Added 'max_count' key to the constraints dict.
        After processing all five positions, scans for any letter that
        appeared 2+ times with a mix of confirmed (green/yellow) and gray
        copies. Records max_count[letter] = confirmed_count as an upper
        bound. Uses min() so multiple guesses only tighten the bound.

      filter_candidates(): Added Rule 5.
        Rejects any word where w.count(letter) > max_count[letter].

    VERIFIED: RAISE → CLOOT(⬛⬛🟩⬛⬛) now correctly returns 11 words.

v1.2 — Bug fix: cross-guess yellow overcount (min_count)
    PROBLEM DISCOVERED: Playing FJORD after RAISE → CLOOT gave 0
    candidates and triggered the "something may be wrong" warning,
    even though 6 valid candidates existed (BROWN, GROUP, GROWN,
    PRONG, PROXY, WRONG).

    ROOT CAUSE: The old Rule 3b computed yellow letter minimums as:
        yellow_counts = Counter(yellow.values())
    The yellow dict accumulates position→letter entries across ALL
    guesses. After RAISE the dict held {0:'r'}. After FJORD it held
    {0:'r', 3:'r'}. Counter({'r':2}) then demanded every candidate
    contain R at least TWICE — but all six surviving words have only
    one R. This is wrong: seeing R yellow in two separate guesses
    confirms the same fact twice, not that there are two R's.

    FIX — two changes:
      update_constraints(): Added 'min_count' key to the constraints dict.
        After processing each guess, counts green+yellow occurrences of
        each letter IN THAT SINGLE GUESS. Takes the MAX across all guesses
        (the tightest lower bound seen is the one that matters). A letter
        yellow in two separate guesses contributes 1 from each guess →
        max(1, 1) = 1. A letter yellow TWICE in the same guess contributes
        2 → min_count correctly requires 2+ copies in the answer.

      filter_candidates(): Rule 3b now uses min_count instead of
        Counter(yellow.values()). The yellow dict is now used ONLY for
        position avoidance (Sub-check A). Minimum count enforcement is
        handled entirely by min_count (Sub-check B).

    VERIFIED: RAISE → CLOOT(⬛⬛🟩⬛⬛) → FJORD(⬛⬛🟩🟨⬛) now
    correctly returns 6 candidates. v1.1 fix still passes (11 words
    after CLOOT alone).

v1.3 — New display columns: Solve%, P(>5), #Worst Buckets
    MOTIVATION: COLON appeared at the top of the ranking after RAISE
    (best worst-case = 10) but played poorly — more than half the
    candidate pool landed in large groups (P(>5) = 57%). The old table
    only showed Worst/Buckets/Unique, hiding this risk. Real play
    confirmed that minimising worst-case alone is not the full story.

    NEW METRICS — added to rank_guesses() return tuple and print_ranking():

      Solve%  = num_buckets / total_candidates × 100
                The probability that your guess produces a pattern that
                uniquely identifies the next guess. Each bucket is one
                distinct outcome — more buckets relative to candidates
                means more of those outcomes narrow things down to one
                word. Equivalent to asking: "If the answer is chosen
                uniformly at random, what fraction of the time does this
                guess give me a unique pattern?"
                Flagged with ❌ if >= 50% of candidates land in big groups.

      P(>5)   = words_in_buckets_larger_than_5 / total_candidates × 100
                The probability you're left with more than 5 candidates
                after this guess — a rough proxy for "stuck" situations
                where two more guesses may not be enough.
                Flagged with ❌ if >= 50%.

      #Worst  = number of buckets that tie for the worst-case size.
                A worst-case of 11 with #Worst=1 means only one specific
                pattern leaves you with 11 words — bad luck but rare.
                A worst-case of 11 with #Worst=2 ❌ means two different
                patterns both leave 11 words — doubly dangerous.

    RETURN TUPLE change (rank_guesses):
        Before: (worst, buckets, unique, word)
        After:  (worst, buckets, unique, solve_pct, gt5_pct, num_worst, word)

    VERIFIED: All five sample words match the reference table exactly:
        CLOOT  11  1   38  36.9%  37.9%   19
        COOPT  11  2❌  33  32.0%  35.9%   17
        COLON  10  1   32  31.1%  57.3%❌  14
        TURON  12  1   40  38.8%  41.7%   20
        CHOON  12  1   37  35.9%  50.5%❌  21

v1.5 — Switch allowed list from NYT to OG cfreshman
    PROBLEM DISCOVERED: The NYT allowed guesses file
    (nyt-wordle-allowed-guesses-2026-03-06.txt, 14855 words) is a
    COMBINED list — it contains all 2315 answer words plus extra
    guesses. This caused every answer-list word to appear twice in
    the "Both lists" merged ranking table (e.g. CLOUT showing as
    both Answer and Allowed).

    ROOT CAUSE: cfreshman's comment on his GitHub clarified that
    the NYT list is not stable and not truly separated. The OG
    Wordle lists (pre-NYT) are the properly separated versions:
        OG answers:       ~2315 words
        OG allowed:      ~10657 words  (no overlap with answers)
        Total OG Wordle: ~12972 words

    FIX: Switched load_allowed_list() to the OG cfreshman allowed
    guesses URL and local filename ('wordle-allowed-guesses.txt').
    The two lists are now truly mutually exclusive again, eliminating
    duplicate rows in the merged ranking table without needing
    deduplication logic. Comments updated throughout to reflect the
    correct overlap status of each list version.

    NOTE FOR DEPLOYMENT: Download the OG allowed guesses file from
    cfreshman's gist and save locally as 'wordle-allowed-guesses.txt'
    alongside the other project files. The engine will fall back to
    this local file if GitHub is unreachable.

v1.4 — New CLI command: D (Detailed bucket analysis)
    NEW FEATURE: At the guess prompt, typing D triggers a detailed
    bucket breakdown for any word against the current candidate pool.

    WORKFLOW:
      1. User types D at the guess prompt
      2. Prompted: "Word to analyse >"  (accepts any valid 5-letter word,
         including allowed-list burners — no strict list validation)
      3. print_bucket_distribution() is called — prints every distinct
         pattern with emoji tiles, the bucket size, the word list, and
         the guess-3 odds for each pattern
      4. Does NOT count as a guess — guess_number is NOT incremented
      5. The allowed list is NOT auto-loaded by D — it remains on-demand
         via the Y/N burner prompt after a normal guess, as before

    WHY USEFUL:
      After the ranking table suggests a top guess, this command lets you
      drill into exactly how that word splits the candidate pool before
      committing. You can see whether the worst-case bucket is a realistic
      outcome or a rare edge case, and which specific words land together.

    DISPLAY IMPROVEMENTS to print_bucket_distribution():
      - Header now shows Solve% and P(>5) alongside bucket/unique counts
      - Word lists wrap at ~50 chars so large buckets stay readable
        (previously printed as one long Python list repr per bucket)
      - Columns: Pattern | Size | Odds | Words

v1.3.1 — Bug fix: emoji column alignment in print_ranking()
    PROBLEM: The ❌ emoji is 2 terminal columns wide but Python's len()
    counts it as 1 character. f-string width specifiers (:<N, :>N) use
    len(), so any row containing ❌ printed 1 column wider than rows
    without it, shifting all subsequent columns rightward.

    Attempts to fix with runtime width variables (worst_w, gt5_w) and
    left-alignment (:<N) both failed for the same reason — they still
    rely on len() internally.

    FIX: Bypass f-string width specs for flag cells entirely. Instead,
    manually construct both variants of each cell to the same VISUAL
    width by adding explicit trailing spaces to the non-flag variant:
        flagged:     "2 ❌ "  → len=5, displays as 6 cols
        non-flagged: "1    "  → len=5, displays as 5 cols... wait
    Correction: ❌ has len=1 but displays as 2, so:
        "2 ❌ " → len=5 but displays as 6 cols
        "1    " → len=5 and displays as 5 cols
    Adding one extra trailing space to the non-flag variant makes both
    display as the same width, so the next column always starts at the
    same horizontal position regardless of flag presence.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONSTRAINT SYSTEM REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The constraints dict accumulates everything we know from all guesses
played so far. It has 6 keys, all optional (filter_candidates uses
.get() with safe defaults so missing keys never crash):

    Key            Type              Meaning
    ─────────────────────────────────────────────────────────
    'green'        dict{int:str}     Position → confirmed letter
                                     w[pos] MUST equal letter
    'yellow'       dict{int:str}     Position → excluded letter
                                     w[pos] MUST NOT equal letter
                                     (position avoidance only — v1.2)
    'gray'         set{str}          Letters confirmed absent
                                     w MUST NOT contain any of these
    'must_contain' set{str}          Letters confirmed present
                                     w MUST contain all of these
    'min_count'    dict{str:int}     Letter → minimum required count
                                     w.count(letter) >= min_count[letter]
                                     (replaces Counter(yellow.values()) — v1.2)
    'max_count'    dict{str:int}     Letter → maximum allowed count
                                     w.count(letter) <= max_count[letter]
                                     (added in v1.1 for duplicate-letter gray)

filter_candidates() applies these as 5 sequential rules (Rules 1–5).
Any rule failure → word is rejected immediately (early exit).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RANKING TUPLE REFERENCE  (output of rank_guesses())
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each element of the returned list is a 7-tuple:

    Index  Name              Type   Meaning
    ──────────────────────────────────────────────────────────
    0      worst             int    Largest bucket size (lower = better)
    1      num_buckets       int    Total distinct patterns produced
    2      num_unique        int    Singleton buckets (certain ID)
    3      solve_pct         float  num_buckets / total_candidates × 100
    4      gt5_pct           float  % of candidates in buckets of size > 5
    5      num_worst_buckets int    How many buckets tie for worst size
    6      word              str    The guess word (lowercase)

Sort order: worst ASC → num_buckets DESC → num_unique DESC
"""

# ── Standard library imports (built into Python, no pip needed) ──
import sys                          # sys.exit() — like exit() in C

# ── Third-party imports (installed via pip) ──
import requests                     # HTTP fetching — like libcurl wrapper

# ── Standard library: collections module ──
# defaultdict is a smarter dict that auto-initializes missing keys
#             Explained in detail in get_buckets() below
# Counter     counts occurrences of each item in a sequence
#             Like building an unordered_map<char,int> automatically
#             Used in filter_candidates() to enforce minimum letter counts
from collections import defaultdict, Counter


# ═════════════════════════════════════════════════════════════════
# SECTION 1: WORD LIST LOADING
#
# TWO SEPARATE LISTS — different purposes, never mixed!
#
#   answer_list  (~2315 words) — what Wordle will actually pick
#                                Used ONLY for candidate filtering
#                                "Could this BE the answer?"
#
#   allowed_list (~10657 words) — OG cfreshman allowed guesses,
#                                 truly separate from answer list
#                                 (no overlap — unlike the NYT list
#                                 which is a combined 14855-word list
#                                 containing all answer words too)
#                                 Used ONLY for burner word search
#                                 "What should I TYPE to best split?"
#
# The OG lists are MUTUALLY EXCLUSIVE.
# Total OG Wordle words = answer_list + allowed_list (~12972)
# ═════════════════════════════════════════════════════════════════

def _load_word_list_from(url, local_path, label):
    """
    Internal helper — shared fallback chain logic for both loaders.
    Not called directly — use load_answer_list() or load_allowed_list().

    PARAMETERS:
        url        (str) : GitHub URL to fetch from
        local_path (str) : Local backup filename
        label      (str) : Human readable name for error messages
                           e.g. "answer list" or "allowed guesses list"

    RETURNS:
        words (list of str) : Loaded word list, all lowercase

    RAISES:
        RuntimeError : If both GitHub and local file fail
    """
    network_error = None
    local_error   = None

    # ── ATTEMPT 1: Fetch from GitHub ──
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        words = [w.strip().lower() for w in response.text.splitlines()
                 if len(w.strip()) == 5]
        print(f"✅ Loaded {len(words)} words ({label}) from GitHub")
        return words
    except requests.exceptions.ConnectionError:
        network_error = "Could not reach GitHub (no network or DNS failure)"
        print(f"⚠️  GitHub unavailable — trying local file...")
    except requests.exceptions.Timeout:
        network_error = "Request timed out after 5 seconds"
        print(f"⚠️  GitHub timed out — trying local file...")
    except requests.exceptions.HTTPError as e:
        network_error = f"HTTP error: {e}"
        print(f"⚠️  GitHub HTTP error — trying local file...")

    # ── ATTEMPT 2: Load from local file ──
    try:
        with open(local_path) as f:
            words = [w.strip().lower() for w in f if len(w.strip()) == 5]
        print(f"✅ Loaded {len(words)} words ({label}) from local file '{local_path}'")
        return words
    except FileNotFoundError:
        local_error = f"Local file '{local_path}' not found"
        print(f"⚠️  {local_error}")
    except PermissionError:
        local_error = f"Permission denied reading '{local_path}'"
        print(f"⚠️  {local_error}")

    # ── ATTEMPT 3: Both failed ──
    raise RuntimeError(
        f"❌ Could not load {label} from any source!\n"
        f"   GitHub failed : {network_error}\n"
        f"   Local failed  : {local_error}\n"
    )


def load_answer_list(local_path='wordle-answers-alphabetical.txt'):
    """
    Load the cfreshman Wordle ANSWER list — words Wordle actually picks.
    Uses fallback chain: GitHub → local file → RuntimeError.

    THIS LIST IS USED FOR:
        ✅ filter_candidates() — filtering possible answers
        ✅ Default guess ranking (answer_pool parameter in rank_guesses)
        ❌ NEVER used as guess_pool for burner search

    PARAMETERS:
        local_path (str) : Local backup filename
                           Default: 'wordle-answers-alphabetical.txt'
                           Download from cfreshman GitHub to create backup

    RETURNS:
        words (list of str) : ~2315 valid Wordle answer words, lowercase

    RAISES:
        RuntimeError : If both GitHub and local file fail
    """
    url = "https://gist.githubusercontent.com/cfreshman/a03ef2cba789d8cf00c08f767e0fad7b/raw/wordle-answers-alphabetical.txt"
    return _load_word_list_from(url, local_path, "answer list")


def load_allowed_list(local_path='wordle-allowed-guesses.txt'):
    """
    Load the cfreshman OG allowed GUESSES list — the original Wordle
    allowed guesses (not NYT), truly separate from the answer list.
    Uses fallback chain: GitHub → local file → RuntimeError.
    Called ON DEMAND — only when user requests burner word search.

    WHY OG NOT NYT:
        The NYT allowed list (nyt-wordle-allowed-guesses-2026-03-06.txt,
        14855 words) is a COMBINED list — it includes all 2315 answer
        words plus extra guesses, so the two lists overlap completely.
        The OG cfreshman list (~10657 words) is truly separate from the
        answer list — no overlap, clean burner search, less processing.
        Since Jeni's Wordle is not NYT Wordle, the OG list is appropriate.

    THIS LIST IS USED FOR:
        ✅ Burner word search (guess_pool parameter in rank_guesses)
        ❌ NEVER used for filter_candidates() — would create false candidates!
        ❌ NEVER used as answer_pool — these words can't be answers!

    TRULY MUTUALLY EXCLUSIVE with answer list (OG cfreshman lists).
    Total OG Wordle words = answer_list + allowed_list (~12972)

    PARAMETERS:
        local_path (str) : Local backup filename
                           Default: 'wordle-allowed-guesses.txt'
                           Download from cfreshman GitHub to create backup

    RETURNS:
        words (list of str) : ~10657 allowed guess words, lowercase

    RAISES:
        RuntimeError : If both GitHub and local file fail
    """
    url = "https://gist.githubusercontent.com/cfreshman/cdcdf777450c5b5301e439061d29694c/raw/wordle-allowed-guesses.txt"
    return _load_word_list_from(url, local_path, "allowed guesses list")


# ═════════════════════════════════════════════════════════════════
# SECTION 2: CORE WORDLE SCORING ENGINE
# ═════════════════════════════════════════════════════════════════

def get_pattern(guess, answer):
    """
    The heart of the engine. Simulates Wordle's color scoring for
    a guess against a known answer. Called thousands of times during
    minmax analysis so it must be correct and efficient.

    PARAMETERS:
        guess  (str) : The 5-letter word being tested as a guess
                       C++ equivalent: const std::string& guess
                       Example: "slate"  (lowercase throughout)

        answer (str) : The 5-letter secret word we're scoring against
                       C++ equivalent: const std::string& answer
                       Example: "crane"

    RETURNS:
        pattern (tuple of int) : 5-element immutable sequence
                                 C++ equivalent: std::array<int,5>
                                 2 = Green  (right letter, right position)
                                 1 = Yellow (right letter, wrong position)
                                 0 = Gray   (letter not in word)
                                 Example: (0,1,2,0,1)

                                 WHY TUPLE NOT LIST?
                                 Tuples are immutable (like const in C++)
                                 and can be used as dictionary keys.
                                 Lists cannot be dict keys — this matters
                                 in get_buckets() where patterns ARE keys!

    ALGORITHM — TWO PASS (handles duplicate letters correctly):
        Pass 1: Find all greens first, "consume" those letters
        Pass 2: Find yellows from remaining unconsumed letters
        This matches official Wordle behavior exactly.

        WHY TWO PASSES?
        If answer="speed" and guess="spell":
        - 's' at pos 0: green (consume answer[0])
        - 'p' at pos 1: green (consume answer[1])
        - 'e' at pos 2: must check — answer still has 'e' at pos 3? yes → yellow
        - 'e' at pos 3: answer[3] already consumed by above → gray
        - 'l' at pos 4: not in answer → gray
        Without two passes, duplicate 'e' gets miscounted.

    PYTHON SYNTAX NOTES:
        list(answer)   Converts immutable string to mutable list of chars
                       Like: char chars[] = answer.c_str() in C++
                       Needed because strings are immutable in Python —
                       you cannot do answer[i] = None on a string!
        None           Used as a sentinel to "consume" matched letters
                       Like setting a char to '\0' in C
        tuple(pattern) Converts mutable list back to immutable tuple
                       Immutable = can be used as a dictionary key later
    """

    pattern = [0, 0, 0, 0, 0]           # start all gray (like memset to 0)
    answer_chars = list(answer)          # mutable copy — we'll consume matched letters
    guess_chars  = list(guess)           # mutable copy — track which we've processed

    # ── PASS 1: Greens — correct letter AND correct position ──
    for i in range(5):                   # range(5) = 0,1,2,3,4  like for(i=0;i<5;i++)
        if guess_chars[i] == answer_chars[i]:
            pattern[i] = 2              # green
            answer_chars[i] = None      # consume — prevents reuse in pass 2
            guess_chars[i]  = None      # mark as processed — skip in pass 2

    # ── PASS 2: Yellows — correct letter but wrong position ──
    for i in range(5):
        if guess_chars[i] is None:       # already matched green in pass 1, skip
            continue                     # like 'continue' in C++

        if guess_chars[i] in answer_chars:   # 'in' searches the list — like std::find
            pattern[i] = 1              # yellow
            # Consume the FIRST matching letter in answer_chars
            # .index() returns position of first match — like std::find returning index
            answer_chars[answer_chars.index(guess_chars[i])] = None

    return tuple(pattern)               # convert list → immutable tuple for dict key use


def pattern_str(pattern):
    """
    Convert a numeric pattern tuple into emoji for display.
    Pure cosmetic helper — not used in any calculation.

    PARAMETERS:
        pattern (tuple of int) : e.g. (2, 0, 1, 0, 2)

    RETURNS:
        (str) : Emoji string  e.g. "🟩⬛🟨⬛🟩"

    PYTHON SYNTAX NOTE — Ternary operator:
        C++:    x == 2 ? "🟩" : x == 1 ? "🟨" : "⬛"
        Python: "🟩" if x == 2 else "🟨" if x == 1 else "⬛"
        Same logic, different syntax. Python reads more like English.

    LIST COMPREHENSION used here:
        ['🟩' if x==2 else '🟨' if x==1 else '⬛' for x in pattern]
        Builds a list by applying the ternary to each element of pattern.
        C++ equivalent: std::transform() into a vector, then join.
        ''.join(list)  concatenates list of strings with no separator.
    """
    return ''.join(['🟩' if x == 2 else '🟨' if x == 1 else '⬛' for x in pattern])


# ═════════════════════════════════════════════════════════════════
# SECTION 3: BUCKET ANALYSIS (Core of Minmax)
# ═════════════════════════════════════════════════════════════════

def get_buckets(guess, candidates):
    """
    Groups all candidate words by what color pattern they would produce
    if 'guess' were played against them. This is the fundamental operation
    of minmax — partitioning the search space.

    Think of it as: "If I guess this word, how does it split the remaining
    possibilities into groups?"

    PARAMETERS:
        guess      (str)         : Word to test as a potential guess
                                   C++ equivalent: const std::string& guess
                                   Does NOT need to be in candidates —
                                   burner words are often outside the list!

        candidates (list of str) : Current pool of possible answers
                                   C++ equivalent: std::vector<std::string>

    RETURNS:
        buckets (dict) : Maps each pattern → list of words producing it
                         C++ equivalent: std::unordered_map<
                                             std::array<int,5>,
                                             std::vector<std::string>>
                         Example:
                         {
                           (2,0,0,2,0): ["crane","crate"],
                           (0,1,0,0,2): ["slate","flame"],
                           (2,2,2,2,2): ["arose"]   ← exact match!
                         }

    PYTHON SYNTAX — defaultdict:
        defaultdict(list) is from the collections module.
        It's a dict that auto-creates a default value for missing keys.

        Regular dict — crash on missing key:
            d = {}
            d['newkey'].append('x')  ← KeyError crash! key doesn't exist yet

        defaultdict(list) — auto-creates empty list for missing key:
            d = defaultdict(list)
            d['newkey'].append('x')  ← works! auto-creates [] then appends
            C++ equivalent: std::unordered_map with operator[] auto-insert

        The 'list' argument tells defaultdict WHAT to create for new keys.
        defaultdict(list) → creates []    for new keys
        defaultdict(int)  → creates 0     for new keys
        defaultdict(dict) → creates {}    for new keys

        dict(buckets) at the end converts back to a regular dict for return.
        Not strictly necessary but signals "this is now a finished result."
    """

    buckets = defaultdict(list)         # auto-creates [] for any new pattern key

    for answer in candidates:
        p = get_pattern(guess, answer)  # get the color pattern tuple
        buckets[p].append(answer)       # add word to its pattern's bucket
                                        # defaultdict auto-creates [] if p is new

    return dict(buckets)                # convert to regular dict before returning


def worst_case(guess, candidates):
    """
    Returns the minimax score for a single guess — the size of the
    LARGEST bucket it creates. Lower is better (fewer words left
    in the worst case scenario).

    This is the key metric: we want to minimize the maximum bucket size.

    PARAMETERS:
        guess      (str)         : Word to evaluate
        candidates (list of str) : Current possible answer pool

    RETURNS:
        (int) : Size of largest bucket
                Example: 8 means worst case leaves 8 possible words
                         1 means every word is uniquely identified!

    PYTHON SYNTAX — Generator expression inside max():
        max(len(v) for v in buckets.values())
        This is like a list comprehension but without building a list first.
        Equivalent to:
            sizes = [len(v) for v in buckets.values()]  # build list
            return max(sizes)                            # find max
        But more memory efficient — generates values one at a time.
        C++ equivalent: std::max_element with a transform iterator.

        .values() returns all the values in the dict (the word lists).
        Like iterating over the values of std::unordered_map.
    """

    buckets = get_buckets(guess, candidates)
    return max(len(v) for v in buckets.values())


# ═════════════════════════════════════════════════════════════════
# SECTION 4: CANDIDATE FILTERING
# ═════════════════════════════════════════════════════════════════

def filter_candidates(all_words, constraints):
    """
    Filters the full word list down to only words that are still
    possible given what we know from previous guesses.
    Called after each real game guess to eliminate impossible words.

    PARAMETERS:
        all_words   (list of str) : Full Wordle word list (~2315 words)
                                    C++ equivalent: const std::vector<std::string>&

        constraints (dict)        : Rules derived from game results so far
                                    C++ equivalent: struct Constraints { ... }
                                    Contains 5 keys (all optional):

                                    'green'  → dict {position: letter}
                                               Positions are 0-indexed!
                                               pos 0=leftmost, pos 4=rightmost
                                               Example: {4:'e', 2:'a'}
                                               means E confirmed at pos 5,
                                               A confirmed at pos 3

                                    'yellow' → dict {position: letter}
                                               Letter IS in word but NOT
                                               at this specific position
                                               Example: {1:'a', 3:'l'}

                                    'gray'   → set of letters
                                               C++ equivalent: std::unordered_set
                                               Letters confirmed NOT in word
                                               Example: {'r','s','t'}

                                    'must_contain' → set of letters
                                               Letters confirmed IN word
                                               (position unknown)
                                               Usually derived from yellows

                                    'min_count' → dict {letter: int}
                                               LOWER BOUND on letter frequency.
                                               Replaces Counter(yellow.values())
                                               which was wrong across multiple
                                               guesses. E.g. R yellow in guess1
                                               AND guess2 gave Counter={'r':2}
                                               incorrectly demanding 2+ R's.
                                               min_count takes the MAX confirmed
                                               count from any single guess.

                                    'max_count' → dict {letter: int}
                                               UPPER BOUND on letter frequency.
                                               Set when a duplicate-letter guess
                                               has some copies green/yellow and
                                               at least one copy gray.
                                               Example: CLOOT result ⬛⬛🟩⬛⬛
                                               O at pos2=green, O at pos3=gray
                                               → max_count['o'] = 1
                                               Rejects BROOD, BROOK etc (two O's)

    RETURNS:
        candidates (list of str) : Words still consistent with all constraints
                                   C++ equivalent: std::vector<std::string>

    PYTHON SYNTAX NOTES:
        dict.get('key', default)  Safe key lookup with fallback value
                                  Like: map.count(key) ? map[key] : default
                                  Prevents KeyError if key doesn't exist

        set()                     Empty set — like std::unordered_set
                                  Note: {} creates empty DICT not set!
                                  Must use set() for empty set.

        any(condition for x in y) Returns True if condition is True for
                                  ANY element — like std::any_of in C++
                                  Short-circuits on first True (efficient)

        continue                  Skip to next loop iteration — same as C++

        .items()                  Returns (key, value) pairs from a dict
                                  Like iterating std::unordered_map entries
                                  for pos, letter in green.items():
                                  gives you both key and value each iteration
    """

    # .get() safely retrieves each constraint with a sensible default
    # if the key doesn't exist in the dict
    green        = constraints.get('green', {})         # {} = empty dict
    yellow       = constraints.get('yellow', {})
    gray         = constraints.get('gray', set())       # set() = empty set
    must_contain = constraints.get('must_contain', set())
    max_count    = constraints.get('max_count', {})     # upper bounds on letter counts
    min_count    = constraints.get('min_count', {})     # lower bounds on letter counts

    candidates = []                     # will hold our filtered results

    for w in all_words:

        # ── RULE 1: Reject if word contains any gray letter ──
        # any() returns True if ANY letter in gray appears in w
        # Short-circuits — stops checking as soon as it finds one
        if any(c in w for c in gray):
            continue                    # skip this word

        # ── RULE 2: Reject if green letters aren't in correct positions ──
        # .items() gives (position, letter) pairs from the green dict
        # any() returns True if ANY green position doesn't match
        if any(w[pos] != letter for pos, letter in green.items()):
            continue

        # ── RULE 3: Reject if yellow constraints are violated ──
        # Yellow means: letter IS in word, but NOT at this position.
        # Split into two independent sub-checks:
        #
        # Sub-check A: POSITION check
        #   Letter must NOT be at its yellow position
        #   e.g. yellow={2:'e'} means w[2] must NOT be 'e'
        #
        # Sub-check B: COUNT check (fixes double-letter bug!)
        #   Word must contain AT LEAST as many of each letter
        #   as the number of times it appeared yellow.
        #   e.g. yellow={2:'e',3:'e'} means answer has 2+ E's
        #        Counter(yellow.values()) = {'e':2}
        #        word needs w.count('e') >= 2
        #   Fixes: single-E words incorrectly passing when answer has two E's
        #
        #   NOTE: 'letter not in w' check removed from Sub-check A
        #   Counter Sub-check B covers it: w.count(letter) < 1 catches absence
        #
        #   C++ equivalent:
        #   unordered_map<char,int> yellow_counts;
        #   for(auto& [pos,letter] : yellow) yellow_counts[letter]++;
        #   for(auto& [letter,min_count] : yellow_counts)
        #       if(count(w.begin(),w.end(),letter) < min_count) skip=true;

        skip = False

        # ── Sub-check A: Position check ──
        # Letter must NOT be sitting at its yellow position
        for pos, letter in yellow.items():
            if w[pos] == letter:            # letter IS at yellow pos → reject
                skip = True
                break

        # ── Sub-check B: Count check ──
        # Word must have AT LEAST as many of each letter as min_count requires.
        # min_count is set by update_constraints from each individual guess —
        # it takes the MAX confirmed count seen in any single guess.
        # This replaces the old Counter(yellow.values()) approach which was
        # WRONG across multiple guesses: R yellow in guess1 AND guess2 gave
        # Counter={'r':2}, incorrectly demanding 2 R's in the answer.
        if not skip:
            for letter, min_required in min_count.items():
                if w.count(letter) < min_required:
                    skip = True
                    break

        if skip:
            continue

        # ── RULE 4: Reject if required letters are missing ──
        if any(letter not in w for letter in must_contain):
            continue

        # ── RULE 5: Reject if word exceeds max letter count ──
        # Enforces upper bounds set by duplicate-letter gray results.
        # Example: max_count={'o':1} rejects BROOD (two O's) after
        # CLOOT returned O(pos2)=green, O(pos3)=gray.
        # w.count(letter) counts occurrences — like std::count() in C++
        if any(w.count(letter) > limit for letter, limit in max_count.items()):
            continue

        # ── All rules passed — this word is still a valid candidate ──
        candidates.append(w)

    return candidates


# ═════════════════════════════════════════════════════════════════
# SECTION 5: MINMAX RANKING & ANALYSIS
# ═════════════════════════════════════════════════════════════════

def rank_guesses(guess_pool, answer_pool, top_n=15):
    """
    The main optimizer. Tests every word in guess_pool and ranks
    them by worst-case performance against answer_pool.
    This is true minimax — not heuristics.

    THE TWO POOLS — critical distinction!
        guess_pool  = WHERE to search for the best word to TYPE
                      Changes based on user choice:
                        Default:       answer_list  (~2315 words)
                        Burner search: allowed_list (~10638 words)

        answer_pool = WHAT the answer could still BE
                      NEVER changes — always filtered answer list!
                      Produced by filter_candidates(answer_list, constraints)

    For each word in guess_pool, we ask:
        "What is the WORST possible outcome if I play this word
         against the remaining answer_pool?"
    Then we rank by that worst case — lowest worst case wins.

    PARAMETERS:
        guess_pool  (list of str) : Words to evaluate as potential guesses
                                    C++ equivalent: const std::vector<std::string>&
                                    Default call:  pass answer_list here
                                    Burner call:   pass allowed_list here
                                    NOTE: Does NOT need to match answer_pool!
                                    Burner words are in allowed_list but NOT
                                    in answer_list — that's the whole point!

        answer_pool (list of str) : Current pool of possible answers
                                    C++ equivalent: const std::vector<std::string>&
                                    ALWAYS the output of filter_candidates()
                                    NEVER changes between default and burner call!
                                    These are the words we're trying to distinguish.

        top_n       (int)         : How many results to return
                                    Default: 15
                                    Like a LIMIT clause in SQL

    RETURNS:
        results (list of tuples) : Top N guesses sorted best → worst
                                   C++ equivalent:
                                   std::vector<std::tuple<int,int,int,std::string>>
                                   Each tuple: (worst_case, num_buckets, num_unique, word)

                                   SORT ORDER (most important first):
                                   1. worst_case  ASCENDING  (lower = better)
                                   2. num_buckets DESCENDING (more buckets = better split)
                                   3. num_unique  DESCENDING (more singletons = better)

                                   NEW COLUMNS added to each tuple:
                                   (worst_case, num_buckets, num_unique,
                                    solve_pct, gt5_pct, num_worst_buckets, word)

                                   solve_pct        = num_buckets / total_candidates
                                                      Probability the pattern uniquely
                                                      identifies the answer next turn.
                                                      Stored as float 0.0–100.0

                                   gt5_pct          = fraction of candidates in buckets
                                                      of size > 5, as a percentage.
                                                      Higher = more likely to be stuck
                                                      with many candidates remaining.

                                   num_worst_buckets = count of buckets that tie for
                                                      the worst-case size.
                                                      1 = only one bucket hits worst case
                                                      2+ ❌ = multiple buckets are equally bad

    EXAMPLE CALLS:
        # Default — search answer list:
        ranking = rank_guesses(
            guess_pool  = answer_list,    # search here for best guess
            answer_pool = answer_pool,    # possible answers (unchanged!)
        )

        # Burner search — search allowed list:
        ranking = rank_guesses(
            guess_pool  = allowed_list,   # search here instead
            answer_pool = answer_pool,    # same possible answers!
        )

    PYTHON SYNTAX — The negative sort trick:
        results.append((wc, -nb, -nu, w))
        We store num_buckets and num_unique as NEGATIVE numbers.
        Why? Python's sort() always sorts ascending (low→high).
        By negating, we flip the order for those columns:
            -nb ascending = nb descending (more buckets first)
        C++ equivalent: custom comparator with std::sort()

        After sorting, we negate back for display:
        formatted = [(wc, -nb, -nu, sp, gp, nwb, w) for ...]

    PYTHON SYNTAX — sum() with generator:
        sum(1 for v in buckets.values() if len(v) == 1)
        Counts buckets with exactly 1 word (unique identifications)
        Like std::count_if() in C++
    """

    total   = len(answer_pool)                          # denominator for percentages
    results = []
    for w in guess_pool:
        buckets = get_buckets(w, answer_pool)
        wc  = max(len(v) for v in buckets.values())     # worst case bucket size
        nb  = len(buckets)                              # number of distinct buckets
        nu  = sum(1 for v in buckets.values() if len(v) == 1)   # singleton buckets
        nwb = sum(1 for v in buckets.values() if len(v) == wc)  # # of worst buckets
        sp  = nb / total * 100                          # Solve% = buckets/candidates
        gp  = sum(len(v) for v in buckets.values()
                  if len(v) > 5) / total * 100          # P(>5) = words in big buckets
        results.append((wc, -nb, -nu, w, sp, gp, nwb)) # negative for desc sort

    results.sort()                                      # sorts by tuple left→right

    # Reformat: undo the negation, reorder for clean return tuple
    # Return: (worst, buckets, unique, solve_pct, gt5_pct, num_worst_buckets, word)
    formatted = [(wc, -nb, -nu, sp, gp, nwb, w)
                 for wc, nb, nu, w, sp, gp, nwb in results]
    return formatted[:top_n]                            # slice — like first top_n elements


def _run_and_display_ranking(guess_pool, answer_pool, answer_list, label):
    """
    Internal helper — runs rank_guesses and displays results.
    Extracted to avoid duplicating ranking display logic.
    Not called directly — used by the CLI game loop.

    PARAMETERS:
        guess_pool  (list of str) : Pool to search for best guess
        answer_pool (list of str) : Current possible answers
        answer_list (list of str) : Full answer list (for ✅ candidate marker)
        label       (str)         : Table header label
    """
    ranking = rank_guesses(guess_pool, answer_pool, top_n=10)
    print_ranking(ranking, answer_pool, label)


def bucket_distribution(guess, candidates):
    """
    Returns the full bucket breakdown for a guess, sorted largest→smallest.
    Used for detailed analysis of how a guess splits the candidate pool.

    PARAMETERS:
        guess      (str)         : Word to analyze
        candidates (list of str) : Current candidate pool

    RETURNS:
        (list of tuples) : [(pattern_tuple, [word_list]), ...]
                           Sorted by bucket size, largest first

    PYTHON SYNTAX — sorted() with key and lambda:
        sorted(buckets.items(), key=lambda x: -len(x[1]))

        .items()     Returns (key, value) pairs — here (pattern, word_list)
        sorted()     Returns NEW sorted list (doesn't modify original)
                     Like std::sort() but non-destructive
        key=         Function that extracts the sort value from each item
                     Like a comparator in C++ but returns the value to compare
        lambda x:    Anonymous function — like a C++ lambda [](auto x){ }
                     x is each (pattern, word_list) tuple
                     x[1] is the word_list  (second element of tuple)
                     len(x[1]) is the bucket size
                     -len(x[1]) negates it → sorts largest first
    """

    buckets = get_buckets(guess, candidates)
    sorted_buckets = sorted(buckets.items(), key=lambda x: -len(x[1]))
    return sorted_buckets


def union_analysis(guess1, guess2, candidates):
    """
    Compares two potential guesses side by side — which words does each
    uniquely identify, which do both identify, and which does neither crack?
    Used to find complementary burner word pairs.

    PARAMETERS:
        guess1     (str)         : First guess to compare
        guess2     (str)         : Second guess to compare
        candidates (list of str) : Current candidate pool

    RETURNS:
        (dict) : Analysis results with 4 keys:
                 'unique_to_1' → words only guess1 identifies (not guess2)
                 'unique_to_2' → words only guess2 identifies (not guess1)
                 'both_unique' → words both guesses identify
                 'neither'     → words neither guess can crack

    PYTHON SYNTAX — Sets and set operations:
        Sets are like std::unordered_set — unordered, no duplicates.
        Python set operations use mathematical symbols:
            A - B   = difference  (in A but not B)  like std::set_difference
            A & B   = intersection (in both)         like std::set_intersection
            A | B   = union        (in either)       like std::set_union

        set(w for v in b1.values() if len(v)==1 for w in v)
        This is a SET COMPREHENSION — like list comprehension but builds a set.
        Reads: "give me each word w, for each bucket v in b1 that has
                exactly 1 word, for each word w in that bucket"
        Result: all words that are uniquely identified by guess1
    """

    b1 = get_buckets(guess1, candidates)
    b2 = get_buckets(guess2, candidates)

    # Words in singleton buckets = uniquely identified by that guess
    unique1 = set(w for v in b1.values() if len(v) == 1 for w in v)
    unique2 = set(w for v in b2.values() if len(v) == 1 for w in v)

    # Words in multi-word buckets = NOT uniquely identified
    stuck1  = set(w for v in b1.values() if len(v) > 1 for w in v)
    stuck2  = set(w for v in b2.values() if len(v) > 1 for w in v)

    return {
        'unique_to_1': sorted(unique1 - unique2),   # set difference
        'unique_to_2': sorted(unique2 - unique1),   # set difference
        'both_unique': sorted(unique1 & unique2),   # set intersection
        'neither':     sorted(stuck1  & stuck2),    # set intersection
    }


def hard_core_splitters(all_words, hard_core, candidates, top_n=10):
    """
    Finds words that PERFECTLY separate a stubborn group — every word
    in hard_core gets its own unique pattern. Used when a small group
    of words resists normal burner words.

    PARAMETERS:
        all_words  (list of str) : Full word list to search for splitters
        hard_core  (list of str) : The stubborn group to perfectly separate
                                   Example: ["batch","catch","hatch","latch","match","patch"]
        candidates (list of str) : Full candidate pool (for worst_case scoring)
        top_n      (int)         : How many results to return. Default: 10

    RETURNS:
        perfect (list of tuples) : [(worst_case, word), ...] sorted best first
                                   Only words that give every hard_core word
                                   a UNIQUE pattern are included

    PYTHON SYNTAX — len(set(...)) trick:
        patterns = [get_pattern(w, answer) for answer in hard_core]
        if len(set(patterns)) == len(hard_core):

        get_pattern returns a tuple (hashable, so usable in a set)
        set(patterns) removes duplicates
        If all patterns are unique → set size equals original list size
        This is a clean Pythonic way to check "are all values distinct?"
        C++ equivalent: put patterns in unordered_set, check size matches
    """

    perfect = []
    for w in all_words:
        # Get the pattern this word produces against each hard_core word
        patterns = [get_pattern(w, answer) for answer in hard_core]

        # If all patterns are unique, this word perfectly separates hard_core
        if len(set(patterns)) == len(hard_core):
            wc = worst_case(w, candidates)
            perfect.append((wc, w))

    perfect.sort()                      # sort by worst_case ascending
    return perfect[:top_n]


# ═════════════════════════════════════════════════════════════════
# SECTION 6: DISPLAY / PRINT HELPERS
# ═════════════════════════════════════════════════════════════════

def print_candidates(candidates, columns=5):
    """
    Prints the FULL candidate word list in a clean box format.
    No truncation — always shows ALL words regardless of count.
    Solves the WordleWise bug where it clips at 50 words despite
    reporting higher counts.

    PARAMETERS:
        candidates (list of str) : Current possible answer words
                                   Example: ["ladle","maple","fable","cable"]

        columns    (int)         : Words per row. Default: 5
                                   Increase for large lists (try 8 or 10)
                                   Decrease for narrow terminal windows

    RETURNS:
        None — prints to console (void function in C++ terms)

    EXAMPLE OUTPUT:
        ┌──────────────────────────────────────────┐
        │  42 Possible Candidates                  │
        ├──────────────────────────────────────────┤
        │  ABIDE   ABODE   ANODE   ASIDE   ATONE   │
        │  BEIGE   BLOKE   BROKE   CHOKE   CHOSE   │
        └──────────────────────────────────────────┘

    PYTHON SYNTAX — f-string format specifiers:
        f"{w:<8}"    Left-align w, pad to 8 chars wide
                     C equivalent: printf("%-8s", w)
        f"{n:>6}"    Right-align n, pad to 6 chars wide
                     C equivalent: printf("%6d", n)
        f"{'─'*40}"  Repeat '─' character 40 times
                     C equivalent: memset(buf, '-', 40)

        range(0, count, columns)  Like for(i=0; i<count; i+=columns)
                                  Third argument is the step size
    """

    count = len(candidates)
    words = sorted([w.upper() for w in candidates])    # alphabetical, uppercase

    width = columns * 8                                # total box width
    print(f"\n┌{'─' * (width + 2)}┐")
    print(f"│  {f'{count} Possible Candidates':<{width}}│")
    print(f"├{'─' * (width + 2)}┤")

    for i in range(0, count, columns):                 # step by columns each row
        row     = words[i:i + columns]                 # slice next N words
        row_str = ''.join(f"{w:<8}" for w in row)     # pad each word to 8 chars
        print(f"│  {row_str:<{width}}│")

    print(f"└{'─' * (width + 2)}┘")


def print_ranking(ranking, candidates, label="Top guesses"):
    """
    Prints the minmax ranking table in formatted columns.

    PARAMETERS:
        ranking    (list of tuples) : Output from rank_guesses()
                                      Each tuple:
                                      (worst, buckets, unique,
                                       solve_pct, gt5_pct, num_worst_buckets, word)
        candidates (list of str)    : Current candidate pool
                                      Used to mark which guesses are also candidates
        label      (str)            : Table header text. Default: "Top guesses"

    RETURNS:
        None — prints to console

    EXAMPLE OUTPUT:
        Top guesses:
          Word     Worst  #Worst  Buckets  Solve%  P(>5)  Unique  Candidate?
          -------------------------------------------------------------------
          CLOOT       11       1       38   36.9%  37.9%      19  ✅
          COOPT       11    2 ❌       33   32.0%  35.9%      17  ✅

    COLUMN MEANINGS:
        Worst  = worst-case bucket size (lower is better)
        #Worst = how many buckets tie for worst case
                 flagged ❌ if > 1 (multiple equally bad outcomes)
        Buckets = total distinct patterns produced
        Solve%  = Buckets / total_candidates — prob of unique ID next turn
        P(>5)   = fraction of candidates in buckets of size > 5
                  flagged ❌ if >= 50% (more than half stuck in big groups)
        Unique  = number of singleton buckets (certain identification)

    PYTHON SYNTAX — f-string column formatting:
        f"{'Word':<8}"   Left-align string 'Word' in 8-char column
        f"{wc:>6}"       Right-align integer wc in 6-char column
        Same as printf(\"%-8s %6d\", \"Word\", wc) in C
    """

    print(f"\n{label}:")
    print(f"  {'Word':<8} {'Worst':>6}  {'#Worst':<8}{'Buckets':>7}  "
          f"{'Solve%':>6}  {'P(>5)':<11}{'Unique':>6}  {'Candidate?'}")
    print(f"  {'-' * 67}")

    for wc, nb, nu, sp, gp, nwb, w in ranking:
        # ── Emoji alignment fix ──
        # ❌ is 2 terminal columns wide but len() counts it as 1.
        # This means a cell containing ❌ always prints 1 column wider
        # than the same cell without it — no f-string width trick can fix
        # this, because the width spec uses len(), not display width.
        #
        # Solution: always produce the SAME visual width by compensating
        # non-flag rows with an extra trailing space.
        #   "2 ❌"  → len=4, displays as 5 cols → use as-is
        #   "1  "   → len=3, displays as 3 cols → add 2 spaces → 5 cols ✓
        # Both cells now occupy 5 display columns, so the next column
        # always starts at the same position regardless of flag presence.
        tag     = "✅" if w in candidates else ""
        nwb_str = f"{nwb} ❌ " if nwb > 1 else f"{nwb}    "   # both → 5 display cols
        gt5_str = f"{gp:5.1f}% ❌ " if gp >= 50.0 else f"{gp:5.1f}%    "
        print(f"  {w.upper():<8} {wc:>6}  {nwb_str}{nb:>7}  "
              f"  {sp:5.1f}%  {gt5_str}{nu:>6}  {tag}")


def print_bucket_distribution(guess, candidates):
    """
    Prints the full bucket breakdown for a single guess — every pattern,
    how many words fall into it, and what the guess-3 odds are.
    Buckets are sorted largest → smallest (worst case first).

    PARAMETERS:
        guess      (str)         : Word to analyze
        candidates (list of str) : Current candidate pool

    RETURNS:
        None — prints to console

    EXAMPLE OUTPUT:
        CLOOT — 19 buckets, worst-case=11, unique=7
        Solve%=18.4%  P(>5)=37.9%
          Pattern        Size  Odds        Words
          ─────────────────────────────────────────────────────
          ⬛⬛⬛⬛⬛      11  1-in-11     BRAND CRIMP DRINK ...
          🟨⬛⬛⬛⬛       6  1-in-6      BRAVE BRAWN GROAN ...
          ⬛⬛🟩⬛⬛       1  certain!    BROWN
          ...
    """

    buckets = bucket_distribution(guess, candidates)
    total   = len(candidates)
    wc      = max(len(v) for _, v in buckets)
    unique  = sum(1 for _, v in buckets if len(v) == 1)
    nb      = len(buckets)
    sp      = nb / total * 100
    gp      = sum(len(v) for _, v in buckets if len(v) > 5) / total * 100

    print(f"\n{guess.upper()} — {nb} buckets, worst-case={wc}, unique={unique}")
    print(f"  Solve%={sp:.1f}%   P(>5)={gp:.1f}%")
    print(f"  {'Pattern':<12} {'Size':>5}  {'Odds':<12}  Words")
    print(f"  {'─' * 65}")

    for p, words in buckets:
        ps      = pattern_str(p)
        size    = len(words)
        odds    = "certain!" if size == 1 else f"1-in-{size}"
        # Format word list — wrap at ~60 chars so long buckets stay readable
        # First line is inline with the pattern; continuation lines are indented
        word_tokens = [w.upper() for w in sorted(words)]
        line_width  = 50                            # characters before wrapping
        lines       = []
        current     = []
        current_len = 0
        for tok in word_tokens:
            if current_len + len(tok) + 1 > line_width and current:
                lines.append(' '.join(current))
                current     = [tok]
                current_len = len(tok)
            else:
                current.append(tok)
                current_len += len(tok) + 1
        if current:
            lines.append(' '.join(current))

        indent = f"  {' ' * 12}  {' ' * 5}  {' ' * 12}  "  # align continuation
        print(f"  {ps}  {size:>5}  {odds:<12}  {lines[0]}")
        for continuation in lines[1:]:
            print(f"{indent}{continuation}")


def print_union_analysis(guess1, guess2, candidates):
    """
    Prints the union analysis comparison between two guesses.
    Shows which words each guess uniquely cracks and which neither can handle.

    PARAMETERS:
        guess1     (str)         : First guess to compare
        guess2     (str)         : Second guess to compare
        candidates (list of str) : Current candidate pool

    RETURNS:
        None — prints to console
    """

    result = union_analysis(guess1, guess2, candidates)
    print(f"\nUnion analysis: {guess1.upper()} vs {guess2.upper()}")
    print(f"  Words only {guess1.upper()} identifies : {[w.upper() for w in result['unique_to_1']]}")
    print(f"  Words only {guess2.upper()} identifies : {[w.upper() for w in result['unique_to_2']]}")
    print(f"  Both identify                    : {[w.upper() for w in result['both_unique']]}")
    print(f"  Neither identifies ({len(result['neither'])} words)  : {[w.upper() for w in result['neither']]}")


# ═════════════════════════════════════════════════════════════════
# SECTION 7: INPUT PARSING
# ═════════════════════════════════════════════════════════════════

def parse_guess_input(user_input):
    """
    Parses a combined GUESS:PATTERN input string into components.
    Called once per guess in the CLI game loop.

    PARAMETERS:
        user_input (str) : Raw string typed by user
                           Format: "GUESS:PATTERN"
                           Example: "SLATE:BOOGB"
                           - GUESS   = 5-letter word (case insensitive)
                           - PATTERN = 5 chars, each must be G, O, or B
                             G = Green  (right letter, right position)
                             O = Orange (right letter, wrong position)
                             B = Black  (letter not in word)

    RETURNS:
        guess   (str)        : Lowercase 5-letter word  e.g. "slate"
        pattern (tuple)      : 5-tuple of ints          e.g. (0,2,1,0,0)
                               2=green, 1=orange, 0=black
                               Matches get_pattern() return format

    RAISES:
        ValueError : Descriptive error message if input is malformed
                     Caught in CLI loop — user gets to retry, not crash
                     Like throwing a descriptive exception in C++

    PYTHON SYNTAX — str methods:
        .strip()   removes leading/trailing whitespace — like trim() in many langs
        .upper()   converts to uppercase — like toupper() in C
        .split(':') splits on delimiter → list of strings
                   Like strtok() in C but safer and returns a list
        len(parts) != 2  checks the split produced exactly 2 pieces

    VALID PATTERN CHARS:
        G = Green  → stored as 2 (matches get_pattern convention)
        O = Orange → stored as 1
        B = Black  → stored as 0
    """

    # ── Basic format check ──
    if ':' not in user_input:
        raise ValueError(
            "Missing ':' separator.\n"
            "  Format must be GUESS:PATTERN\n"
            "  Example: SLATE:BOOGB"
        )

    parts = user_input.strip().upper().split(':')

    if len(parts) != 2:
        raise ValueError(
            "Too many ':' separators.\n"
            "  Format must be GUESS:PATTERN\n"
            "  Example: SLATE:BOOGB"
        )

    guess   = parts[0]
    pattern = parts[1]

    # ── Validate guess ──
    if len(guess) != 5:
        raise ValueError(
            f"Guess '{guess}' must be exactly 5 letters (got {len(guess)})"
        )

    if not guess.isalpha():             # isalpha() = all characters are letters
        raise ValueError(               # like checking isalpha() in C for each char
            f"Guess '{guess}' must contain only letters (no numbers or symbols)"
        )

    # ── Validate pattern ──
    if len(pattern) != 5:
        raise ValueError(
            f"Pattern '{pattern}' must be exactly 5 characters (got {len(pattern)})"
        )

    valid_chars = {'G', 'O', 'B'}       # Python set literal — like a lookup table
    for ch in pattern:
        if ch not in valid_chars:
            raise ValueError(
                f"Invalid pattern character '{ch}'.\n"
                f"  Each character must be G (green), O (orange), or B (black)\n"
                f"  Example: SLATE:BOOGB"
            )

    # ── Convert pattern string to tuple of ints ──
    # Dictionary maps each letter to its numeric value
    # C++ equivalent: std::unordered_map<char,int>
    color_map = {'G': 2, 'O': 1, 'B': 0}
    pattern_tuple = tuple(color_map[ch] for ch in pattern)

    return guess.lower(), pattern_tuple  # always return lowercase guess


def update_constraints(constraints, guess, pattern_tuple):
    """
    Updates the running constraint state after each guess.
    Merges new information from this guess into existing constraints.

    This is the stateful part of the CLI — we accumulate knowledge
    across multiple guesses, narrowing down candidates each round.

    PARAMETERS:
        constraints   (dict)        : Current constraint state (modified IN PLACE)
                                      C++ equivalent: pass by reference —
                                      struct Constraints& constraints
                                      Python dicts are passed by reference
                                      automatically — no & needed!

        guess         (str)         : Lowercase 5-letter guess  e.g. "slate"

        pattern_tuple (tuple of int): 5-tuple from parse_guess_input()
                                      e.g. (0, 2, 1, 0, 0)

    RETURNS:
        None — modifies constraints dict IN PLACE
               C++ equivalent: void function with reference parameter

    PYTHON SYNTAX — dict.setdefault():
        constraints.setdefault('green', {})
        If 'green' key doesn't exist, creates it with value {}
        If 'green' key already exists, leaves it alone
        Like: if(map.find('green') == map.end()) map['green'] = {}

    PYTHON SYNTAX — dict update with |= :
        constraints['green'] |= {pos: letter}
        |= merges one dict into another (Python 3.9+)
        Like: existing_map.insert(new_map.begin(), new_map.end())
        Older alternative: constraints['green'].update({pos: letter})

    THE DUPLICATE-LETTER MAX_COUNT FIX:
        When a letter appears multiple times in a guess and at least one
        copy comes back gray, Wordle is telling us the answer contains
        EXACTLY as many of that letter as the non-gray copies.

        Example: CLOOT vs answer BROWN
          C=gray  L=gray  O(pos2)=green  O(pos3)=gray  T=gray
          The gray O at pos3 means: answer has exactly 1 O.
          Without this fix, filter_candidates only enforces min counts
          (from green/yellow), so BROOD, BROOK etc. (two O's) survive.

        Fix: after processing all five positions, for every letter that
        had at least one gray AND at least one green/yellow, record the
        confirmed count as an UPPER BOUND in 'max_count'.

        'max_count' → dict {letter: int}
          Answer must have AT MOST this many of this letter.
          C++ equivalent: std::unordered_map<char,int>

    THE CROSS-GUESS YELLOW OVERCOUNT FIX:
        The yellow dict maps position→letter across ALL guesses.
        If R appears yellow in guess 1 (pos 0) AND yellow in guess 2
        (pos 3), yellow = {0:'r', 3:'r'}.
        Counter(yellow.values()) = {'r': 2} — WRONG!
        This incorrectly demands the answer has 2+ R's.
        R appearing yellow in two separate guesses just means R is
        somewhere in the word — we confirmed the same fact twice.

        Fix: track 'min_count' explicitly in update_constraints.
        Each guess contributes its own confirmed count for each letter
        (green + yellow occurrences in THAT guess). We take the MAX
        across all guesses — the tightest lower bound wins.

        'min_count' → dict {letter: int}
          Answer must have AT LEAST this many of this letter.
          C++ equivalent: std::unordered_map<char,int>
          Replaces Counter(yellow.values()) in filter_candidates.
    """

    # Ensure all constraint keys exist before we try to update them
    # setdefault() is safe — won't overwrite existing data
    constraints.setdefault('green', {})
    constraints.setdefault('yellow', {})
    constraints.setdefault('gray', set())
    constraints.setdefault('must_contain', set())
    constraints.setdefault('max_count', {})
    constraints.setdefault('min_count', {})

    for i, (letter, color) in enumerate(zip(guess, pattern_tuple)):
        # zip(guess, pattern_tuple) pairs each letter with its color
        # enumerate() adds the index i
        # C++ equivalent: for(int i=0; i<5; i++) { letter=guess[i]; color=pattern[i]; }

        if color == 2:                          # Green — right letter, right position
            constraints['green'][i] = letter   # record position → letter mapping
            constraints['must_contain'].add(letter)

        elif color == 1:                        # Orange — right letter, wrong position
            constraints['yellow'][i] = letter  # record position to AVOID
            constraints['must_contain'].add(letter)

        else:                                   # Black — letter not in word
            # Only add to gray if letter isn't confirmed elsewhere
            # Edge case: SPEED vs ABODE — 'E' gray in one position
            # but green/orange in another is valid!
            if letter not in constraints['must_contain']:
                constraints['gray'].add(letter)

    # ── MAX_COUNT: detect duplicate-letter gray situations ──
    # For each unique letter in this guess, count how many copies
    # were green/yellow vs gray. If any were gray AND any were
    # green/yellow, the answer has EXACTLY the green/yellow count.
    #
    # Counter(guess) counts each letter's appearances in the guess.
    # C++ equivalent: unordered_map<char,int>
    guess_letter_counts = Counter(guess)

    for letter, total_in_guess in guess_letter_counts.items():
        if total_in_guess < 2:
            continue                            # single occurrence — no duplicate issue

        # Count how many of this letter were green or yellow (confirmed)
        confirmed = sum(
            1 for i, (ch, color) in enumerate(zip(guess, pattern_tuple))
            if ch == letter and color in (1, 2)
        )
        # Count how many were gray
        grayed = sum(
            1 for i, (ch, color) in enumerate(zip(guess, pattern_tuple))
            if ch == letter and color == 0
        )

        if confirmed >= 1 and grayed >= 1:
            # Answer has EXACTLY 'confirmed' copies of this letter.
            # Record as upper bound — take the minimum if we already
            # have a bound (tighter constraint wins).
            # C++ equivalent: min(existing_bound, confirmed)
            existing = constraints['max_count'].get(letter, confirmed)
            constraints['max_count'][letter] = min(existing, confirmed)

    # ── MIN_COUNT: compute confirmed lower bound per letter from THIS guess ──
    # Count green + yellow occurrences of each letter in this single guess.
    # That number is the minimum times this letter appears in the answer
    # (based on this guess alone). We take the MAX across all guesses —
    # the highest lower bound we've ever seen is the tightest constraint.
    #
    # This replaces Counter(yellow.values()) in filter_candidates, which
    # was wrong because it counted the same yellow letter across multiple
    # guesses, incorrectly inflating the required count.
    #
    # Example: R yellow at pos0 in guess1, R yellow at pos3 in guess2
    #   Counter(yellow.values()) = {'r': 2}  ← WRONG (demands 2+ R's)
    #   min_count approach: each guess saw 1 confirmed R → max(1,1) = 1 ✅
    #
    # Example: SPEED with E yellow at pos2 AND E yellow at pos3
    #   This single guess confirmed 2 E's → min_count['e'] = max(old, 2) ✅
    this_guess_confirmed = Counter(
        ch for ch, color in zip(guess, pattern_tuple) if color in (1, 2)
    )
    for letter, count in this_guess_confirmed.items():
        existing = constraints['min_count'].get(letter, 0)
        constraints['min_count'][letter] = max(existing, count)


# ═════════════════════════════════════════════════════════════════
# SECTION 8: MAIN ENTRY POINT — INTERACTIVE CLI GAME LOOP
#
# if __name__ == '__main__':
#     Python's equivalent of int main() in C++.
#     ONLY runs when you launch this file directly:
#         python wordle_minmax.py       ← runs this block
#     SKIPPED when imported as a module:
#         import wordle_minmax          ← skips entirely
#
# Why does this matter?
#     The future Streamlit UI will import this file and call
#     functions directly. We don't want the CLI loop to run
#     automatically when Streamlit imports us!
# ═════════════════════════════════════════════════════════════════

if __name__ == '__main__':

    # ── Load answer list at startup — always needed immediately ──
    # Allowed list loaded on demand later (cached after first load)
    try:
        answer_list  = load_answer_list()   # ~2315 words — possible answers
    except RuntimeError as e:
        print(e)
        sys.exit(1)

    allowed_list = None                     # None = not loaded yet
                                            # C++ equivalent: vector<string>* = nullptr
                                            # Loaded and cached on first Y response

    # ── Game loop state ──
    # These variables persist across all guesses in one game session
    constraints = {}                        # accumulates knowledge from each guess
    answer_pool = answer_list[:]            # current possible answers
                                            # starts as full answer list
                                            # shrinks after each guess
                                            # [:] = copy — like memcpy in C
    guess_number = 1                        # track which guess we're on

    # ── Print welcome header ──
    print("\n" + "═" * 55)
    print("  🍦 Jeni's Wordle Minmax Analyzer")
    print("═" * 55)
    print("  Format : GUESS:PATTERN  e.g. SLATE:BOOGB")
    print("  Pattern: G=Green  O=Orange  B=Black(gray)")
    print("  Commands: Q=quit  R=restart  ?=candidates  D=detail")
    print("═" * 55)

    # ── Main game loop ──
    # Runs until solved, quit, or 6 guesses used
    # C++ equivalent: while(true) { ... break; }
    while guess_number <= 6:

        print(f"\nGuess {guess_number} of 6 — {len(answer_pool)} candidates remaining")

        # ── Get input from user ──
        # input() prints a prompt and waits for user to type + hit Enter
        # C++ equivalent: std::cout << prompt; std::cin >> user_input;
        try:
            user_input = input("  Enter guess:pattern > ").strip()
        except EOFError:                # handles Ctrl+D / piped input ending
            print("\nGoodbye!")
            break

        # ── Handle special commands ──
        if user_input.upper() == 'Q':
            print("Goodbye! 🍦")
            break

        if user_input.upper() == 'R':
            # Restart — reset all state and loop back to top
            constraints  = {}
            answer_pool  = answer_list[:]   # reset to full answer list
            guess_number = 1
            print("\n" + "═" * 55)
            print("  🔄 Restarted! New game.")
            print("═" * 55)
            continue                        # jump back to top of while loop

        if user_input.upper() == '?':
            print_candidates(answer_pool)
            continue                        # show candidates, don't count as guess

        # ── D: Detailed bucket analysis for a single word ──
        # Calls print_bucket_distribution() against the current answer_pool.
        # Does NOT count as a guess — guess_number is NOT incremented.
        # Accepts any valid 5-letter word (no strict list validation —
        # burner words from the allowed list are fine here too).
        if user_input.upper() == 'D':
            try:
                detail_input = input("  Word to analyse > ").strip().lower()
            except EOFError:
                continue

            # Basic format check only — no list validation, no auto-load
            if len(detail_input) != 5 or not detail_input.isalpha():
                print("  ❌ Must be exactly 5 letters.")
                continue

            # Run the full bucket breakdown against the current candidate pool
            print_bucket_distribution(detail_input, answer_pool)
            continue                        # D does NOT count as a guess

        # ── Parse the input — retry on bad format ──
        try:
            guess, pattern_tuple = parse_guess_input(user_input)
        except ValueError as e:
            # Bad input — show error and let user try again
            # Does NOT increment guess_number — bad input doesn't cost a guess!
            print(f"\n  ❌ Input error: {e}")
            continue                        # loop back, ask again

        # ── Check for solved! ──
        if all(c == 2 for c in pattern_tuple):  # all greens = GGGGG = solved!
            print(f"\n  🎉 Solved in {guess_number} guess{'es' if guess_number > 1 else ''}!")
            print(f"  The word was: {guess.upper()}")
            print("\n  Play again? (R to restart, Q to quit)")
            continue

        # ── Update constraints with this guess result ──
        update_constraints(constraints, guess, pattern_tuple)

        # ── Filter answer_pool — ALWAYS from answer_list only! ──
        # Never use allowed_list here — those words can't be answers!
        answer_pool = filter_candidates(answer_list, constraints)

        # ── Show results ──
        if len(answer_pool) == 0:
            print("\n  ⚠️  No candidates remaining!")
            print("  Check your pattern input — something may be wrong.")
            print("  (R to restart)")

        elif len(answer_pool) == 1:
            print(f"\n  🎯 Only one word left: {answer_pool[0].upper()}")
            print(f"  That's your answer!")

        else:
            # ── Show candidates ──
            print_candidates(answer_pool)

            # ── Default ranking — search answer list for best guess ──
            print(f"\n  ⏳ Ranking from answer list...")
            ranking = rank_guesses(
                guess_pool  = answer_list,  # search answer list for best guess
                answer_pool = answer_pool,  # possible answers (unchanged!)
                top_n       = 20
            )
            print_ranking(ranking, answer_pool,
                          f"Top 20 guesses (answer list) for guess {guess_number + 1}")

            # ── Burner search from allowed list ──
            # If already loaded (e.g. from a previous guess or D command),
            # run automatically — no need to ask again.
            # If not yet loaded, prompt once and cache for the rest of the game.
            print()
            if allowed_list is not None:
                run_burner = True           # already in memory — just use it
            else:
                try:
                    burner_input = input("  Search allowed guesses for better burner? (Y/N) > ").strip().upper()
                except EOFError:
                    burner_input = 'N'

                if burner_input == 'Y':
                    print("  ⏳ Loading allowed guesses list (one time only)...")
                    try:
                        allowed_list = load_allowed_list()
                        run_burner   = True
                    except RuntimeError as e:
                        print(f"  ❌ Could not load allowed list: {e}")
                        run_burner = False
                else:
                    run_burner = False

            if run_burner and allowed_list is not None:
                print(f"  ⏳ Searching {len(allowed_list)} allowed guesses...")
                ranking = rank_guesses(
                    guess_pool  = allowed_list,  # search allowed list instead!
                    answer_pool = answer_pool,   # same possible answers!
                    top_n       = 20
                )
                print_ranking(ranking, answer_pool,
                              f"Top 20 burners (allowed list) for guess {guess_number + 1}")

        guess_number += 1               # increment AFTER processing — like i++ at end of loop

    # ── Game over — used all 6 guesses ──
    if guess_number > 6:
        print(f"\n  😔 Used all 6 guesses. Remaining candidates were:")
        print_candidates(answer_pool)
        print("  (R to restart, Q to quit)")
