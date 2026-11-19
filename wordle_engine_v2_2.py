"""
Wordle Minmax Engine — v2.2 (STREAMLIT DEPLOYMENT BUILD, BUCKETS-FIRST)
=========================================================================
A tool for computing optimal Wordle guesses by exhaustive bucket analysis.
Built for use with the cfreshman Wordle answer list.
(Ranking order: buckets-first since v2.2 — see the v2.2 changelog entry.)

WHAT THIS FILE IS:
    A Python "module" — think of it like a .cpp file containing a library
    of functions. Each function does one specific job. The bottom section
    (if __name__ == '__main__') is the equivalent of int main() and only
    runs when you launch this file directly.

DEPLOYMENT BUILD NOTE:
    This file is the v2.2 engine as deployed for the Streamlit web app.
    It uses the NYT 3-6-26 modified allowed-guesses list (~14855 words)
    — the SAME list as the local CLI build, so both tools now agree.
    HISTORY: the web app originally used the OG cfreshman allowed list
    because the NYT file is not mutually exclusive with the answers and
    caused duplicate rows in the merged web table. That rationale is
    obsolete: wordle_app.py dedups the merged table by word (the _key
    drop-duplicates block), so the overlap is handled in the UI layer.
    NYT chosen for freshness — it includes newer valid guess words the
    OG list lacks. Code identical to wordle_minmax_CLI_v2_2_bucketsfirst.py
    (only this header differs).

HOW TO RUN (standalone CLI still works):
    python wordle_engine_v2_2.py

HOW TO IMPORT (future Streamlit UI):
    import wordle_engine_v2_2 as engine
    engine.load_answer_list()      # call any function by name
    (Underscores instead of dots in the filename keep it a valid
    Python module name, so a plain import statement works.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE (v2.0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    THE GAME STATE IS THE RAW TRANSCRIPT — nothing else.

        history = [(guess, pattern), (guess, pattern), ...]

    One append-only list of (guess, pattern) 2-tuples, one entry per
    guess played. C++: vector<pair<string, array<int,5>>>.

    Candidate filtering is "the audition": a word survives if and only
    if, had it been the secret answer, it would have produced EXACTLY
    the observed pattern for EVERY guess in the transcript:

        all(get_pattern(g, w) == p for g, p in history)

    get_pattern() — the function that defines Wordle scoring, duplicate
    consumption and all — is the SINGLE source of truth. There is no
    constraint dictionary, no rules, no counters. Every implication of
    an observation (position exclusions, count caps, duplicate-letter
    interactions, cross-guess accumulation) is enforced automatically,
    because violating any implication necessarily changes at least one
    tile of the recomputed pattern.

    The v1.x architecture (update_constraints + a 6-key rules dict) was
    retired after five bugs of the same class — see v2.0 changelog
    entry. The v1.x changelog is retained below as the historical
    record of WHY this architecture exists.

DOCUMENTATION INDEXING CONVENTION:
    Code is 0-indexed (arrays start at zero — never changing that).
    PROSE (changelog, docstrings, bug reports) describes tile positions
    1-indexed the way a player reads the board, with the 0-indexed
    tuple slot in brackets when the code-level view matters:
    e.g. "E gray at position 4 [tuple index 3]".

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

v1.4 — New CLI command: D (Detailed bucket analysis)
    NEW FEATURE: At the guess prompt, typing D triggers a detailed
    bucket breakdown for any word against the current candidate pool.

    WORKFLOW:
      1. User types D at the guess prompt
      2. Prompted: "Word to analyse >"  (accepts any valid 5-letter word,
         including allowed-list burners not in the answer list)
      3. Optionally prompted: "Search allowed guesses list too? (Y/N)"
         If Y and allowed list is loaded, runs the analysis against the
         allowed list as well (same candidate pool, different guess word)
      4. print_bucket_distribution() is called — prints every distinct
         pattern with emoji tiles, the bucket size, the word list, and
         the guess-3 odds for each pattern
      5. Does NOT count as a guess — guess_number is NOT incremented

    WHY USEFUL:
      After the ranking table suggests a top guess, this command lets you
      drill into exactly how that word splits the candidate pool before
      committing. You can see whether the worst-case bucket is a realistic
      outcome or a rare edge case, and which specific words land together.

    EXAMPLE:
      Guess 2 of 6 — 38 candidates remaining
        Enter guess:pattern > D
        Word to analyse > CLOOT
        CLOOT — 19 buckets, worst-case=11, unique=7
          Pattern       Size  Words → Guess 3 odds
          ─────────────────────────────────────────
          ⬛⬛⬛⬛⬛     11   ['BRAND','CRIMP',...] → 1-in-11
          🟨⬛⬛⬛⬛      6   ['BRAVE','BRAWN',...] → 1-in-6
          ⬛⬛🟩⬛⬛      1   ['BROWN'] → certain!
          ...

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

v1.5 — New metric: P(>3) column added to ranking table
    MOTIVATION: Jeni's Wordle awards the daily stamp within 3 guesses
    (no store visit required). After guess 2, any bucket with 4+ candidates
    means guess 3 is not guaranteed to win — the player is choosing blind
    among 4+ options with only 1 shot remaining. P(>5) exists but is too
    permissive for this constraint: a bucket of 4 or 5 words still means
    failure is likely. P(>3) directly measures what matters for Jeni's:
    the fraction of candidates that would leave you in a losing position
    after guess 2.

    P(>3) is added ALONGSIDE the existing P(>5) — not replacing it.
    P(>5) remains useful when the candidate pool is large and you are
    planning two guesses ahead; P(>3) is the more actionable metric
    for the final-guess pressure unique to Jeni's 3-guess format.

    NEW METRIC — added to rank_guesses() return tuple and print_ranking():
      P(>3)   = words_in_buckets_larger_than_3 / total_candidates × 100
                The probability of being left with more than 3 candidates
                after this guess — a losing position in Jeni's 3-guess game.
                Flagged with ❌ if >= 50% (majority of candidates at risk).

    RETURN TUPLE change (rank_guesses):
        Before: (worst, buckets, unique, solve_pct, gt5_pct, num_worst, word)
        After:  (worst, buckets, unique, solve_pct, gt5_pct, gt3_pct, num_worst, word)

    CHANGES:
      rank_guesses()   — added g3 / gt3_pct calculation parallel to gp / gt5_pct.
                         Inserted into sort tuple (after gp, before nwb) and
                         into formatted return tuple.
      print_ranking()  — added P(>3) column to header and each data row,
                         following the same emoji-alignment pattern as P(>5).
                         Updated docstring tuple reference and example output.
                         Column order: Worst / #Worst / Buckets / Solve% /
                         P(>5) / P(>3) / Unique / Candidate?

v1.6 — Bug fix: duplicate-letter gray/green ordering in update_constraints()
    PROBLEM DISCOVERED: Playing LEVEL after RAISE(E orange) → DENET(both Es
    green) returned 0 candidates. The correct answer was JEWEL. After LEVEL
    (L gray at pos0, E green, V gray, E green, L green at pos4), the engine
    recorded L in the gray set AND in the green set simultaneously. Rule 1 of
    filter_candidates rejects any word containing a gray letter, so JEWEL
    (which contains L) was rejected — leaving 0 survivors.

    ROOT CAUSE: update_constraints() processed all five positions in a single
    left-to-right pass. When a letter appeared twice in the same guess with
    one copy gray (earlier position) and one copy green (later position),
    the gray copy was encountered first. At that moment L was not yet in
    must_contain (the green at pos4 hadn't been processed yet), so L was
    incorrectly added to gray. The green at pos4 was then correctly added
    to green/must_contain — but gray already contained L. This is the same
    ordering hazard that get_pattern() avoids with its own two-pass design.

    TRIGGER CONDITION: guess has letter X at position i (gray) AND letter X
    at position j > i (green or yellow). Single-pass processes i before j,
    graying X before confirming it. Reversed order (green first) worked fine,
    which is why this went undetected until LEVEL surfaced it.

    FIX: Split the single loop into two explicit passes — mirrors get_pattern():
      Pass 1: iterate all five positions, process greens and yellows only.
              This fully populates must_contain for every confirmed letter
              in this guess before any gray decision is made.
      Pass 2: iterate all five positions, process grays only.
              By now must_contain is complete, so the check
              'if letter not in must_contain' is always correct regardless
              of which position the gray copy occupies relative to green.

    VERIFIED: RAISE(E orange) → DENET(both Es green) → LEVEL(pos0-L gray,
    pos1-E green, pos2-V gray, pos3-E green, pos4-L green) now correctly
    returns ['bezel', 'jewel'] — both legitimately satisfy every constraint.

v1.7 — Bug fix: duplicate-letter position exclusion for confirmed+gray copies
    PROBLEM DISCOVERED (game play, May 17 2026): RAISE(E orange, rest gray)
    → DENET(E at pos2 orange [1-indexed; pos1 0-indexed], rest gray, including
    the SECOND E at pos4 1-indexed / pos3 0-indexed) reported 13 candidates.
    The correct count was 7 — confirmed via bucket_distribution() on the same
    guess, which correctly placed it in a 7-word bucket. 6 extra words
    (BOWEL, COVEY, GOLEM, GOOEY, HOVEL, VOWEL) were wrongly surviving.

    ROOT CAUSE: When DENET's duplicate E split confirmed(yellow)/gray, the
    existing v1.1 max_count fix correctly capped total E's in the answer to 1
    (the confirmed count). But max_count only restricts the TOTAL count of a
    letter — it says nothing about WHERE that single confirmed copy may sit.
    A word with exactly one E could still place it at the gray position
    (pos3 0-indexed) without violating max_count or any other existing rule.
    That placement is impossible: if the real answer had E at pos3, get_pattern()
    would have scored that copy GREEN there, not gray — a gray result on a
    duplicate letter is proof the word does NOT have that letter at that
    specific position, exactly like an ordinary yellow exclusion.

    WHY THIS DIDN'T AFFECT THE v1.1 (CLOOT) CASE: When the confirmed copy is
    GREEN rather than yellow, the green constraint already pins the letter to
    one exact position, and combined with max_count, no other position can
    hold a second copy without exceeding the count cap — the position
    exclusion is automatically implied. It is only the YELLOW+gray duplicate
    case that leaves a gap, because yellow confirms presence without pinning
    a position, so the single counted copy is otherwise free to land anywhere
    — including the gray position — unless explicitly forbidden.

    FIX: In the existing MAX_COUNT detection block (update_constraints), once
    a letter is confirmed to be duplicate with at least one gray copy, also
    record each gray-position index of that letter into the 'yellow' dict
    (which filter_candidates' Sub-check A already treats as "must NOT be at
    this position"). This is additive and harmless for the green+gray case
    (already implied, so it just adds a redundant but correct constraint) and
    closes the gap for the yellow+gray case.

    VERIFIED: RAISE(E orange@pos4) → DENET(E orange@pos1, E gray@pos3, rest
    gray) now correctly returns 7 candidates, matching bucket_distribution()'s
    independently computed bucket for the same pattern. BOWEL, COVEY, GOLEM,
    GOOEY, HOVEL, VOWEL (all with E at the gray position) are now correctly
    excluded.

v1.8 — Bug fix: yellow position exclusions overwritten across guesses
    PROBLEM DISCOVERED (game play): RAISE(R orange@pos1, E orange@pos5, rest
    gray) → OUTED(U orange, E orange, D orange, rest gray) reported 3
    candidates: CRUDE, DEMUR, PRUDE. Only DEMUR is valid — CRUDE and PRUDE
    both have E at pos5 (1-indexed), which RAISE's orange E already ruled
    out. The detailed bucket view for OUTED (computed independently by
    get_buckets) correctly showed DEMUR as a singleton for that pattern.

    ROOT CAUSE: The 'yellow' dict mapped position → A SINGLE letter:
        constraints['yellow'][i] = letter
    Within one guess this is fine (each position has one letter). But across
    MULTIPLE guesses, different letters can be excluded from the SAME
    position. Here:
        After RAISE:  yellow = {0:'r', 4:'e'}     E excluded from pos4 ✓
        After OUTED:  D orange at pos4 executed yellow[4]='d'
                      → OVERWROTE the 'e' exclusion at pos4!
    The constraint "E is not at pos4" was silently forgotten, so CRUDE and
    PRUDE (single E, sitting at pos4) slipped back in. Note this is a
    CROSS-GUESS accumulation bug, same family as v1.2's min_count bug —
    and it explains why the v1.7 exhaustive stress test missed it: that
    test covered every possible SINGLE guess (where one position can only
    ever receive one yellow letter), never sequences of guesses.

    FIX: 'yellow' values are now SETS of letters:
        constraints['yellow'].setdefault(i, set()).add(letter)
        C++ equivalent: unordered_map<int, unordered_set<char>>,
        yellow[i].insert(letter)
    Changed in three places:
      update_constraints() Pass 1  — ordinary yellow recording
      update_constraints() v1.7 block — gray-position exclusion recording
      filter_candidates() Sub-check A — membership test:
        old: if w[pos] == letter     new: if w[pos] in letters
    Docstrings describing the yellow structure updated accordingly.
    min_count logic is unaffected — it never read the yellow dict (v1.2).

    VERIFIED: RAISE(R,E orange) → OUTED(U,E,D orange) now returns exactly
    ['demur'], matching get_buckets' independent computation. Additionally,
    a new MULTI-GUESS randomized stress test (random answer, 3-4 random
    guesses, constraints accumulated across all of them, compared against
    the brute-force intersection of buckets) passes with zero mismatches —
    closing the single-guess-only blind spot in the previous test.

v2.0 — ARCHITECTURAL REFACTOR: pattern-history replaces the constraint dict
    MOTIVATION: Five bugs (v1.1, v1.2, v1.6, v1.7, v1.8) shared one root
    cause. The engine maintained two parallel implementations of Wordle
    semantics: get_pattern() (the definition of scoring — correct in every
    bug report; the bucket views were always right) and the constraint
    dictionary (update_constraints + rule-based filter_candidates), which
    COMPRESSED observations into rules and re-derived membership from the
    compression. Every bug was a spot where the compression was lossy —
    an implication of the raw observation the rule system failed to encode.
    Serializer/deserializer analogy: get_pattern was the serializer;
    the dict engine was a hand-written parallel deserializer that had to
    stay semantically in sync forever. It never fully did.

    THE CHANGE:
      DELETED : update_constraints() and the 6-key constraints dict
                (green/yellow/gray/must_contain/max_count/min_count) —
                the entire rules engine (~200 lines).
      STATE   : history = [(guess, pattern), ...] — the raw transcript,
                append-only, one entry per guess. Recording a guess is:
                    history.append((guess, pattern_tuple))
      FILTER  : filter_candidates(all_words, history) — "the audition":
                    [w for w in all_words
                       if all(get_pattern(g, w) == p for g, p in history)]
                A word survives iff it would have produced EXACTLY the
                observed board for EVERY guess played. This is the same
                expression used as ground truth in the v1.7/v1.8 stress
                tests (0 mismatches across ~5.3M single-guess cases and
                20,000 multi-guess trials) — promoted to be the
                implementation.

    WHY IT'S CORRECT BY CONSTRUCTION: every implication of an observation
    — position exclusions, count caps, duplicate-letter consumption
    cascades, cross-guess accumulation — is a consequence of pattern
    equality, not a rule to be encoded. A word violating any implication
    necessarily paints at least one tile the wrong color in the
    recomputed pattern. The v1.x bug class is not fixed; it is
    UNREPRESENTABLE — the code that could contain it no longer exists.

    UNCHANGED: get_pattern(), get_buckets(), rank_guesses(),
    bucket_distribution(), union_analysis(), hard_core_splitters(),
    all print/display functions, all metrics (Worst, #Worst, Buckets,
    Solve%, P(>5), P(>3), Unique), word-list loading, menu structure.
    CLI behavior is identical to v1.8 (verified by differential test).

    PERFORMANCE: full-replay filtering costs ~len(answers) × len(history)
    get_pattern calls per turn (~10K) — negligible next to rank_guesses'
    millions. A provably-equivalent incremental variant (screen only the
    newest guess against previous survivors; valid because candidacy is
    a pure conjunction over history) is DEFERRED as a back-pocket
    optimization — see SPEC_v2.0_pattern_history_refactor.md.

    FREE WIN: undo is now trivial (history.pop() + re-filter) — not yet
    exposed in the UI, noted for a future session.

    The v1.x changelog entries above are retained verbatim as the
    historical record of why this architecture exists.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GAME STATE REFERENCE (v2.0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The entire game state is one variable:

    history : list of (guess, pattern) 2-tuples, in play order
        guess   : 5-char lowercase string
        pattern : tuple of 5 ints — 0=gray, 1=orange, 2=green,
                  tiles left to right [tuple index 0 = position 1]
        C++ equivalent: vector<pair<string, array<int,5>>>

    Example after two guesses:
        [('raise', (0, 0, 0, 0, 1)),    # E orange at position 5 [index 4]
         ('denet', (0, 1, 0, 0, 0))]    # E orange at position 2 [index 1]

    Properties:
      - Append-only: each guess adds one entry; nothing is merged,
        summarized, or overwritten. push_back, never update.
      - Entries are immutable tuples — recorded observations cannot be
        corrupted after the fact (like const members).
      - answer_pool INVARIANT: always exactly
        filter_candidates(answer_list, history).
      - Undo = history.pop() + re-filter (future feature, free).

HISTORICAL NOTE — the v1.x constraint dict (DELETED in v2.0):
    v1.x compressed each guess into a 6-key rules dict (green, yellow,
    gray, must_contain, min_count, max_count) and filtered by applying
    the rules. The v1.1–v1.8 changelog entries above document, bug by
    bug, why that compression kept losing information. Kept here only
    so those entries remain intelligible.

v2.1 — Reporting refactor: GuessStats record + threshold-driven P columns
    MOTIVATION: Adding a metric (P(>2) was the trigger) required ~6
    coordinated edits: the computation, two positional tuples (sort-shape
    and return-shape), the docstring tuple table, print_ranking's header,
    and its row unpacking — a 9-element anonymous tuple where every
    producer/consumer had to agree on positions. Same parallel-bookkeeping
    disease v2.0 cured in the filter engine, living on in the reporting
    layer. Bonus wart removed: num_buckets/num_unique were stored NEGATED
    to fake a descending sort, then un-negated for display.

    THE CHANGE (reporting layer only — game state and filtering untouched):
      NEW  P_THRESHOLDS = (5, 3, 2) — module constant, the single source
           of truth for which P(>N) risk columns exist. rank_guesses()
           computes one percentage per entry; print_ranking() derives its
           header, cells, and ≥50% ❌ flags by iterating the same constant.
           Adding/removing/reordering a P column = editing this one line.
      NEW  GuessStats namedtuple — immutable named record replacing the
           anonymous 8-tuple. Fields: word, worst, num_worst, num_buckets,
           num_unique, solve_pct, p_gt (dict {threshold: pct}).
           C++: a struct replacing std::tuple accessed via std::get<N>.
      rank_guesses()  — builds GuessStats; sorts with an explicit key
           (worst ASC, num_buckets DESC, num_unique DESC) — negation now
           appears only inside the sort key, data is never mangled.
           Sort semantics IDENTICAL to v2.0 (verified by test).
      print_ranking() — field access by NAME; P columns generated by loop.

    NEW METRIC delivered by the above: P(>2) — % of candidates in buckets
    of size > 2; the sharpest Jeni's 3-guess risk metric (any bucket of 3+
    after guess 2 makes guess 3 a coin flip or worse). Validated in live
    play before implementation (SHEEP-over-SHEER decision, July 2026).
    CAVEAT: on large pools (guess 1) P(>2) runs near 100% for every guess
    — read comparatively; the ❌ will light up across the board early.
    Flag threshold ≥50% kept uniform for now; retune if noisy in play.

    VERIFIED: ranking order and all shared metrics numerically identical
    to v2.0 across randomized game states; P(>2) spot-checked against the
    hand-computed SHEEP-game numbers (SHEEP/SHEER/WHEEL 22.2%, SEWER/SWEET
    50.0%); scripted CLI smoke test for column alignment with/without ❌.

v2.2 — Buckets-first ranking (Solve% is the 3-guess objective) + S sort toggle
    MOTIVATION: Jeni's allows 3 guesses. After guess 2, every bucket is
    worth exactly ONE expected win on guess 3:
        chance of landing in a bucket   = size / total
        chance of guessing right in it  = 1 / size
        product                         = 1 / total   (size cancels!)
    Summed over all buckets:
        P(win by guess 3) = num_buckets / total = Solve%
    — exactly, IF every remaining answer is equally likely. Worst-case
    bucket size does not appear in that formula at all. A 15-word bucket
    and a 9-word bucket are each worth one expected win.

    The v2.1 sort (worst ASC first) therefore pushed the best second
    guesses below the top-20 cut. Example — RAISE:OOBBB (R and A orange,
    78 candidates), searching the 14855-word allowed list:
        TRONC  29 buckets  worst  9  Solve% 37.2%   ← v2.1 row 1
        BROND  35 buckets  worst 15  Solve% 44.9%   ← v2.1 row 85 (hidden)
    BROND wins 35 of the 78; TRONC wins 29.
    (Background: Nov 2026 opener study — exhaustive two-guess-deep scoring
    of all 14855 openers against the 2315 answers.)

    THE CHANGE (ranking/reporting layer only — game state, filtering,
    get_pattern(), GuessStats and the table columns are all untouched):
      NEW  SORT_MODES — module constant (Section 5), the single source of
           truth for the available sort orders:
             'buckets' : num_buckets DESC → worst ASC → num_unique DESC
                         → word ASC                       (NEW DEFAULT)
             'worst'   : worst ASC → num_buckets DESC → num_unique DESC
                         → word ASC                (identical to v2.1)
      NEW  DEFAULT_SORT_MODE = 'buckets'
      NEW  compute_guess_stats() — the EXPENSIVE half of the old
           rank_guesses(): one GuessStats per guess word, unsorted.
      NEW  sort_guess_stats()    — the CHEAP half: sort + top_n slice.
      rank_guesses() — now just compute + sort. Gains a sort_mode
           parameter (default 'buckets'). Pass sort_mode='worst' to get
           the exact v2.1 ordering.
      NEW  print_sorted_ranking() — sorts a stats list and prints the
           table with the active sort order shown in the header.
      NEW  CLI command S — toggles the sort order and instantly reprints
           the current table(s). The CLI caches the full stats lists
           after each guess, so S re-sorts without recomputing anything.

    WHEN WORST-FIRST IS STILL THE RIGHT VIEW (press S):
      (a) Bonus-guess days — with a 4th guess, a large leftover bucket
          can still be split again, so its size matters once more.
      (b) If answers are NOT equally likely, the formula above is only
          approximate. (Bucket count is still the better guide than
          worst case; the real hedge is picking the most ordinary word
          in the bucket on the final guess.)
    The Worst column is always on screen and is the first tie-breaker in
    buckets mode, so the trade-off is visible on every row.

    NOT INCLUDED (considered, deferred): a "tolerance" rule — prefer the
    smallest worst case among words within N buckets of the best. The
    top-20 table already shows those alternatives side by side.

    VERIFIED: sort_mode='worst' output identical (order and every field)
    to v2.1 rank_guesses() in 21 comparisons — two real RAISE pools and
    five random pools, each against the full answer list and a random
    1500-word slice of the allowed list; 'buckets' ordering checked
    against an independent implementation on the RAISE:OOBBB pool with
    the full allowed list (BROND row 1, row 85 in 'worst' mode); scripted
    CLI smoke test of the S toggle before a game, with and without a
    burner table, and after R.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GUESSSTATS REFERENCE  (output of rank_guesses(), v2.1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

rank_guesses() returns a list of GuessStats — an immutable namedtuple
(a struct with named fields; defined at module scope in Section 5,
right next to P_THRESHOLDS):

    Field         Type   Meaning
    ──────────────────────────────────────────────────────────
    .word         str    The guess word (lowercase)
    .worst        int    Largest bucket size (lower = better)
    .num_worst    int    How many buckets tie for worst size
    .num_buckets  int    Total distinct patterns produced
    .num_unique   int    Singleton buckets (certain ID)
    .solve_pct    float  num_buckets / total_candidates × 100
    .p_gt         dict   {threshold: pct} — one entry per value in
                         P_THRESHOLDS, e.g. {5: 0.0, 3: 22.2, 2: 22.2}
                         pct = % of candidates in buckets LARGER than
                         the threshold (risk of a bad split)

Sort order (v2.2) — chosen by sort_mode, defined in SORT_MODES (Section 5):
    'buckets' (default): num_buckets DESC → worst ASC → num_unique DESC
                         → word ASC
    'worst'   (v2.1)   : worst ASC → num_buckets DESC → num_unique DESC
                         → word ASC
(explicit sort keys; fields are never stored negated; word is the
deterministic alphabetical tie-breaker in both modes)

To change which P(>N) columns exist: edit P_THRESHOLDS in Section 5.
Computation and display both iterate it — nothing else to touch.
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
from collections import defaultdict, Counter, namedtuple


# ═════════════════════════════════════════════════════════════════
# SECTION 1: WORD LIST LOADING
#
# TWO SEPARATE LISTS — different purposes, never mixed!
#
#   answer_list  (~2315 words) — what Wordle will actually pick
#                                Used ONLY for candidate filtering
#                                "Could this BE the answer?"
#
#   allowed_list (~10638 words) — words Wordle accepts as guesses
#                                 but will NEVER pick as answers
#                                 Used ONLY for burner word search
#                                 "What should I TYPE to best split?"
#
# The lists are MUTUALLY EXCLUSIVE — cfreshman confirmed no overlap!
# Total valid Wordle words = answer_list + allowed_list (~12953)
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


def load_allowed_list(local_path='nyt-wordle-allowed-guesses-2026-03-06.txt'):
    """
    Load the cfreshman allowed GUESSES list — words Wordle accepts
    as guesses but will NEVER pick as answers.
    Uses fallback chain: GitHub → local file → RuntimeError.
    Called ON DEMAND — only when user requests burner word search.

    THIS LIST IS USED FOR:
        ✅ Burner word search (guess_pool parameter in rank_guesses)
        ❌ NEVER used for filter_candidates() — would create false candidates!
        ❌ NEVER used as answer_pool — these words can't be answers!

    MUTUALLY EXCLUSIVE with answer list — cfreshman confirmed no overlap.
    Total valid Wordle words = answer_list + allowed_list (~12953)

    PARAMETERS:
        local_path (str) : Local backup filename
                           Default: 'nyt-wordle-allowed-guesses-2026-03-06.txt'
                           Download from cfreshman GitHub to create backup

    RETURNS:
        words (list of str) : ~10638 allowed guess words, lowercase

    RAISES:
        RuntimeError : If both GitHub and local file fail
    """
    url = "https://gist.githubusercontent.com/cfreshman/8b92bc418b43096094cf5d1b0eea8f84/raw/2519c8c22e3274b7a665fe11ab233a96416defc2/nyt-wordle-allowed-guesses-2026-03-06.txt"
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

def filter_candidates(all_words, history):
    """
    Filters the full word list down to only words that are still
    possible given every guess played so far this game.
    Called after each real game guess to eliminate impossible words.

    ═══ v2.0 ARCHITECTURE — THE AUDITION ═══
    A word is a candidate if and only if it would have produced EXACTLY
    the observed color pattern for EVERY guess played so far.

    For each dictionary word, we "audition" it: pretend it is the secret
    answer, replay each recorded guess against it with get_pattern(),
    and compare the imagined board to the board actually observed.
    One mismatched tile on any guess → the word is out.

    There are NO rules here — no green/yellow/gray sets, no letter
    counts, no position exclusions. Every implication of an observation
    (first-order, second-order, duplicate-letter interactions, cross-
    guess accumulation) is enforced automatically, because any word
    violating any implication necessarily paints at least one tile the
    wrong color somewhere. get_pattern() is the single source of truth
    for Wordle scoring; this function simply tests equality against it.

    This replaces the v1.x constraint-dictionary engine
    (update_constraints + rule-based filtering), which produced five
    corner-case bugs (v1.1, v1.2, v1.6, v1.7, v1.8) — all of them
    places where compressing observations into rules lost information.
    See the v2.0 changelog entry for the full architectural rationale.

    PARAMETERS:
        all_words (list of str)  : Full Wordle answer list (~2315 words)
                                   C++ equivalent: const std::vector<std::string>&

        history   (list of tuple): The complete game transcript, in play
                                   order. Each entry is a 2-tuple:
                                     (guess, pattern)
                                   guess   = 5-char lowercase string
                                   pattern = tuple of five ints,
                                             0=gray 1=orange 2=green,
                                             tiles left to right
                                             [tuple index 0 = position 1]
                                   Example after two guesses:
                                     [('raise', (0,0,0,0,1)),
                                      ('denet', (0,1,0,0,0))]
                                   C++ equivalent:
                                     const std::vector<std::pair<
                                       std::string, std::array<int,5>>>&

    RETURNS:
        list of str : Words consistent with the entire transcript.
                      With an empty history, returns a copy of all_words
                      (every word passes an empty audition).

    PYTHON SYNTAX NOTES:
        - List comprehension with a compound condition:
            [w for w in all_words if all(...)]
          C++ equivalent: std::copy_if into a result vector.
        - all(...) over a generator short-circuits on first False —
          like std::all_of; the first mismatched guess ejects the word
          without checking the remaining history entries.
        - Tuple equality (==) compares element-wise — effectively a
          memcmp of the five tiles.

    PERFORMANCE:
        Full replay: len(all_words) × len(history) get_pattern calls
        (~2315 × 4 ≈ 10K on a typical turn) — negligible next to
        rank_guesses(), which makes millions of the same calls.
        A provably-equivalent incremental variant (test only the newest
        guess against the previous survivors) is documented in the v2.0
        spec as a deferred back-pocket optimization.
    """
    return [w for w in all_words
            if all(get_pattern(g, w) == p for g, p in history)]


# ═════════════════════════════════════════════════════════════════
# SECTION 5: MINMAX RANKING & ANALYSIS
# ═════════════════════════════════════════════════════════════════

# ── P(>N) columns shown in the ranking table, in display order (v2.1) ──
# THE single source of truth for which risk columns exist. Both
# rank_guesses() (computation) and print_ranking() (header + cells)
# iterate this constant — neither hard-codes any threshold, so adding,
# removing, or reordering a P(>N) column is a one-line edit right here.
# C++ equivalent: constexpr int P_THRESHOLDS[] = {5, 3, 2};
P_THRESHOLDS = (5, 3, 2)

# ── GuessStats — the record rank_guesses() returns (v2.1) ──
# Replaces the v1.x/v2.0 anonymous 8-tuple, which required every
# producer/consumer to agree on element positions (the same
# parallel-bookkeeping disease v2.0 cured in the filter engine).
# A namedtuple is an immutable struct with named fields — like a C++
# struct replacing std::tuple<...> accessed via std::get<N>.
# Fields still unpack positionally if ever needed, but print_ranking()
# uses names (s.worst, s.p_gt[3]) so field order can never bite us.
GuessStats = namedtuple('GuessStats', [
    'word',         # str   — the guess (lowercase)
    'worst',        # int   — largest bucket size (lower = better)
    'num_worst',    # int   — how many buckets tie for worst size
    'num_buckets',  # int   — total distinct patterns produced
    'num_unique',   # int   — singleton buckets (certain identification)
    'solve_pct',    # float — num_buckets / total_candidates × 100
    'p_gt',         # dict  — {threshold: pct} for each P_THRESHOLDS entry
                    #         e.g. {5: 0.0, 3: 22.2, 2: 22.2}
])

# ── SORT_MODES — the available ranking orders (v2.2) ──
# THE single source of truth for how the ranking table is ordered.
# Each entry maps a mode name to:
#   'label' : text shown in the table header and the S-command message
#   'key'   : the sort key — a function taking one GuessStats and
#             returning the tuple to compare (smaller tuple sorts first).
#             A minus sign flips that field to DESCENDING order.
#
#   'buckets' — most buckets first. With ONE guess left after this one,
#               P(win) = num_buckets / candidates = Solve%, so this is
#               the exact objective for guess 2 of a 3-guess game.
#               Worst case is the first tie-breaker (smaller = better).
#   'worst'   — smallest worst-case bucket first (classic minimax, the
#               v2.1 order). The better view when MORE than one guess
#               remains after this one — e.g. bonus-guess days.
#
# C++ equivalent: a std::map<std::string, Comparator> of named
# comparators handed to std::sort().
SORT_MODES = {
    'buckets': {
        'label': 'buckets-first (Solve%)',
        'key'  : lambda s: (-s.num_buckets, s.worst, -s.num_unique, s.word),
    },
    'worst': {
        'label': 'worst-first (minimax)',
        'key'  : lambda s: (s.worst, -s.num_buckets, -s.num_unique, s.word),
    },
}

# Which order the tool starts in (and what rank_guesses() uses when the
# caller does not say). The CLI's S command flips between the two.
DEFAULT_SORT_MODE = 'buckets'


def rank_guesses(guess_pool, answer_pool, top_n=15,
                 sort_mode=DEFAULT_SORT_MODE):
    """
    The main optimizer. Tests every word in guess_pool against
    answer_pool and ranks them in the order chosen by sort_mode.
    Exhaustive — every guess is scored, no heuristics.

    v2.2: this is now a thin wrapper around two steps —
        compute_guess_stats()  the expensive part (millions of
                               get_pattern calls)
        sort_guess_stats()     the cheap part (one sort + a slice)
    The split lets the CLI re-sort a table instantly (S command)
    without recomputing anything.

    THE TWO POOLS — critical distinction!
        guess_pool  = WHERE to search for the best word to TYPE
                      Changes based on user choice:
                        Default:       answer_list  (~2315 words)
                        Burner search: allowed_list (~10638 words)

        answer_pool = WHAT the answer could still BE
                      NEVER changes — always filtered answer list!
                      Produced by filter_candidates(answer_list, constraints)

    For each word in guess_pool, we ask:
        "How does this word split the remaining answer_pool into
         buckets — how many buckets, and how big is the worst one?"
    Then we rank by sort_mode:
        'buckets' (default) — most buckets wins (highest Solve%)
        'worst'             — smallest worst case wins (v2.1 order)

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

        sort_mode   (str)         : A key of SORT_MODES — 'buckets' or
                                    'worst'. Default: DEFAULT_SORT_MODE
                                    ('buckets'). Pass 'worst' for the
                                    exact v2.1 ordering.

    RETURNS:
        results (list of GuessStats) : Top N guesses sorted best → worst.
                                   GuessStats is a namedtuple (see its
                                   definition just above this function) —
                                   an immutable struct with NAMED fields:

                                   .word         str   the guess (lowercase)
                                   .worst        int   largest bucket size
                                   .num_worst    int   buckets tying for worst
                                                       (2+ flagged ❌ in table)
                                   .num_buckets  int   distinct patterns
                                   .num_unique   int   singleton buckets
                                   .solve_pct    float num_buckets/total × 100
                                   .p_gt         dict  {threshold: pct} — one
                                                       entry per P_THRESHOLDS
                                                       value, e.g.
                                                       {5: 0.0, 3: 22.2, 2: 22.2}
                                                       pct = % of answer_pool in
                                                       buckets LARGER than the
                                                       threshold (risk metrics)

                                   SORT ORDER — sort_mode='buckets' (default):
                                   1. num_buckets DESCENDING (higher Solve%)
                                   2. worst       ASCENDING  (lower = better)
                                   3. num_unique  DESCENDING (more singletons)
                                   4. word        ASCENDING  (alphabetical
                                      tie-breaker — deterministic order)

                                   SORT ORDER — sort_mode='worst' (v2.1):
                                   1. worst       ASCENDING
                                   2. num_buckets DESCENDING
                                   3. num_unique  DESCENDING
                                   4. word        ASCENDING

                                   C++ equivalent: std::vector<GuessStats>
                                   where GuessStats is a plain struct and
                                   p_gt is a std::map<int, double>.

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

        # v2.1 ordering (worst case first) — e.g. bonus-guess days:
        ranking = rank_guesses(
            guess_pool  = allowed_list,
            answer_pool = answer_pool,
            sort_mode   = 'worst',
        )
    """
    stats = compute_guess_stats(guess_pool, answer_pool)    # expensive
    return sort_guess_stats(stats, sort_mode, top_n)        # cheap


def compute_guess_stats(guess_pool, answer_pool):
    """
    The EXPENSIVE half of ranking (v2.2 — extracted from rank_guesses).
    Scores every word in guess_pool against answer_pool and returns one
    GuessStats record per word, UNSORTED (same order as guess_pool).

    Nothing here depends on the sort order, so the CLI computes this
    once per guess, keeps the list, and re-sorts it as often as it likes.

    PARAMETERS:
        guess_pool  (list of str) : Words to evaluate as potential guesses
        answer_pool (list of str) : Current pool of possible answers

    RETURNS:
        stats (list of GuessStats) : One record per guess word, unsorted.
                                     Hand it to sort_guess_stats().

    COST:
        len(guess_pool) × len(answer_pool) get_pattern calls.
        C++ equivalent: the nested for-loops that fill a
        std::vector<GuessStats> before any std::sort() runs.

    PYTHON SYNTAX — dict comprehension over P_THRESHOLDS:
        {t: ... for t in P_THRESHOLDS}
        Builds one {threshold: percentage} dict per guess. Each threshold
        costs one sweep over the bucket sizes (a few dozen ints) — cheap.
        C++ equivalent: for (int t : P_THRESHOLDS) p_gt[t] = ...;
    """

    total   = len(answer_pool)                          # denominator for percentages
    results = []
    for w in guess_pool:
        buckets = get_buckets(w, answer_pool)
        sizes = [len(v) for v in buckets.values()]      # bucket sizes, computed once
        wc = max(sizes)                                 # worst case bucket size
        results.append(GuessStats(
            word        = w,
            worst       = wc,
            num_worst   = sum(1 for s in sizes if s == wc),
            num_buckets = len(sizes),
            num_unique  = sum(1 for s in sizes if s == 1),
            solve_pct   = len(sizes) / total * 100,
            # One risk percentage per threshold in P_THRESHOLDS —
            # % of the answer pool landing in buckets LARGER than t.
            p_gt        = {t: sum(s for s in sizes if s > t) / total * 100
                           for t in P_THRESHOLDS},
        ))

    return results                                      # unsorted — one per guess word


def sort_guess_stats(stats, sort_mode=DEFAULT_SORT_MODE, top_n=None):
    """
    The CHEAP half of ranking (v2.2). Sorts a list of GuessStats in the
    order named by sort_mode and returns the first top_n records.

    PARAMETERS:
        stats     (list of GuessStats) : Output of compute_guess_stats().
                                         NOT modified — a new list is
                                         returned (like sorting a copy).
        sort_mode (str)                : A key of SORT_MODES:
                                           'buckets' — most buckets first
                                           'worst'   — smallest worst first
        top_n     (int or None)        : How many records to return.
                                         None = all of them.

    RETURNS:
        (list of GuessStats) : Sorted best → worst, at most top_n long.

    RAISES:
        ValueError : If sort_mode is not a key of SORT_MODES.

    PYTHON SYNTAX — sort with an explicit key:
        sorted(stats, key=SORT_MODES[sort_mode]['key'])
        The key function returns the tuple to compare for each record —
        like std::sort() with a custom comparator. Negation appears ONLY
        inside the key (to get descending order for those fields); the
        stored data itself is never mangled. The word is the last key
        element, so ties always break alphabetically and the order is
        deterministic.

    PYTHON SYNTAX — slicing with None:
        some_list[:None] is the same as some_list[:] — the whole list.
        So top_n=None needs no special case.
    """
    if sort_mode not in SORT_MODES:
        raise ValueError(
            f"Unknown sort_mode '{sort_mode}'. "
            f"Valid choices: {', '.join(SORT_MODES)}"
        )
    ordered = sorted(stats, key=SORT_MODES[sort_mode]['key'])
    return ordered[:top_n]                              # slice — first top_n records


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
        ranking    (list of GuessStats) : Output from rank_guesses().
                                      Fields accessed BY NAME (s.worst,
                                      s.p_gt[t], ...) — never by position,
                                      so field order can never bite us.
        candidates (list of str)    : Current candidate pool
                                      Used to mark which guesses are also candidates
        label      (str)            : Table header text. Default: "Top guesses"

    RETURNS:
        None — prints to console

    EXAMPLE OUTPUT (with P_THRESHOLDS = (5, 3, 2)):
        Top guesses:
          Word     Worst  #Worst  Buckets  Solve%  P(>5)       P(>3)       P(>2)       Unique  Candidate?
          ------------------------------------------------------------------------------------------
          SHEEP         4       1       13    72.2%   0.0%       22.2%       22.2%        10
          SHEER         4       1       11    61.1%   0.0%       22.2%       22.2%         6  ✅

    COLUMN MEANINGS:
        Worst   = worst-case bucket size (lower is better)
        #Worst  = how many buckets tie for worst case
                  flagged ❌ if > 1 (multiple equally bad outcomes)
        Buckets = total distinct patterns produced
        Solve%  = Buckets / total_candidates — prob of unique ID next turn
        P(>N)   = one column PER P_THRESHOLDS entry — the fraction of
                  candidates in buckets of size > N, flagged ❌ if >= 50%.
                  P(>2) is the sharpest 3-guess risk metric: any bucket of
                  3+ after guess 2 makes guess 3 a coin flip or worse.
                  NOTE: on large pools (early game) P(>2) runs near 100%
                  for every guess — read it comparatively, and expect the
                  ❌ to light up across the board on guess 1.
        Unique  = number of singleton buckets (certain identification)

    ADDING/REMOVING P COLUMNS:
        Edit P_THRESHOLDS (module scope, Section 5). Header, cells, and
        flags below all iterate that constant — nothing here changes.

    PYTHON SYNTAX — f-string column formatting:
        f"{'Word':<8}"   Left-align string 'Word' in 8-char column
        f"{s.worst:>6}"  Right-align integer in 6-char column
        Same as printf(\"%-8s %6d\", \"Word\", wc) in C
    """

    # ── Header: fixed columns + one P(>N) column per threshold ──
    p_headers = "".join(f"{f'P(>{t})':<11}" for t in P_THRESHOLDS)
    print(f"\n{label}:")
    print(f"  {'Word':<8} {'Worst':>6}  {'#Worst':<8}{'Buckets':>7}  "
          f"{'Solve%':>6}  {p_headers}{'Unique':>6}  {'Candidate?'}")
    print(f"  {'-' * (68 + 11 * len(P_THRESHOLDS))}")

    for s in ranking:
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
        tag     = "✅" if s.word in candidates else ""
        nwb_str = (f"{s.num_worst} ❌ " if s.num_worst > 1
                   else f"{s.num_worst}    ")            # both → 5 display cols

        # ── One risk cell per threshold, same flag rule for all ──
        p_cells = "".join(
            f"{s.p_gt[t]:5.1f}% ❌ " if s.p_gt[t] >= 50.0
            else f"{s.p_gt[t]:5.1f}%    "
            for t in P_THRESHOLDS
        )

        print(f"  {s.word.upper():<8} {s.worst:>6}  {nwb_str}{s.num_buckets:>7}  "
              f"  {s.solve_pct:5.1f}%  {p_cells}{s.num_unique:>6}  {tag}")


def print_sorted_ranking(stats, candidates, label, sort_mode, top_n=20):
    """
    Sorts a full stats list in the requested order and prints the top
    rows, with the sort order named in the table header (v2.2).

    Used by the CLI both right after a guess and when the S command
    re-sorts the same cached stats — one code path for both, so the two
    tables can never drift apart.

    PARAMETERS:
        stats      (list of GuessStats) : Output of compute_guess_stats()
        candidates (list of str)        : Current candidate pool (✅ marker)
        label      (str)                : Table header text, e.g.
                                          "Top 20 burners (allowed list) for guess 2"
        sort_mode  (str)                : A key of SORT_MODES
        top_n      (int)                : Rows to show. Default: 20

    RETURNS:
        None — prints to console
    """
    ranking = sort_guess_stats(stats, sort_mode, top_n)
    print_ranking(ranking, candidates,
                  f"{label} — sorted {SORT_MODES[sort_mode]['label']}")


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


# ─────────────────────────────────────────────────────────────────
# update_constraints() DELETED in v2.0.
# The constraint dictionary (green/yellow/gray/must_contain/max_count/
# min_count) no longer exists. Game state is the raw transcript:
#     history.append((guess, pattern_tuple))
# done directly in the main loop. See the v2.0 changelog entry and
# filter_candidates() for the architectural rationale.
# ─────────────────────────────────────────────────────────────────


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
    history = []                            # v2.0: the complete game transcript
                                            # list of (guess, pattern) tuples,
                                            # append-only — one entry per guess.
                                            # This IS the game state; everything
                                            # else is derived from it.
                                            # C++ equivalent:
                                            # vector<pair<string, array<int,5>>>
    answer_pool = answer_list[:]            # current possible answers
                                            # INVARIANT: always exactly
                                            # filter_candidates(answer_list, history)
                                            # starts as full answer list
                                            # shrinks after each guess
                                            # [:] = copy — like memcpy in C
    guess_number = 1                        # track which guess we're on

    # ── Ranking display state (v2.2) ──
    sort_mode = DEFAULT_SORT_MODE           # 'buckets' or 'worst' — S toggles
    last_answer_stats = None                # full unsorted stats behind the
    last_burner_stats = None                # tables currently on screen.
                                            # None = no table shown yet.
                                            # Kept so S can re-sort and
                                            # reprint without recomputing.

    # ── Print welcome header ──
    print("\n" + "═" * 55)
    print("  🍦 Jeni's Wordle Minmax Analyzer")
    print("═" * 55)
    print("  Format : GUESS:PATTERN  e.g. SLATE:BOOGB")
    print("  Pattern: G=Green  O=Orange  B=Black(gray)")
    print("  Commands: Q=quit  R=restart  ?=candidates  D=detail")
    print("            S=switch sort order (buckets ↔ worst)")
    print(f"  Sort   : {SORT_MODES[sort_mode]['label']}")
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
            history      = []               # empty transcript = new game
            answer_pool  = answer_list[:]   # reset to full answer list
            guess_number = 1
            last_answer_stats = None        # no tables on screen any more
            last_burner_stats = None        # (sort_mode deliberately kept)
            print("\n" + "═" * 55)
            print("  🔄 Restarted! New game.")
            print("═" * 55)
            continue                        # jump back to top of while loop

        if user_input.upper() == '?':
            print_candidates(answer_pool)
            continue                        # show candidates, don't count as guess

        # ── S: Switch sort order (v2.2) ──
        # Flips between 'buckets' and 'worst', then reprints whatever
        # ranking tables are currently on screen from the cached stats.
        # No get_pattern calls happen here — it is only a re-sort.
        # Does NOT count as a guess.
        if user_input.upper() == 'S':
            sort_mode = 'worst' if sort_mode == 'buckets' else 'buckets'
            print(f"\n  🔀 Sort order is now: {SORT_MODES[sort_mode]['label']}")
            if last_answer_stats is not None:
                print_sorted_ranking(
                    last_answer_stats, answer_pool,
                    f"Top 20 guesses (answer list) for guess {guess_number}",
                    sort_mode)
            if last_burner_stats is not None:
                print_sorted_ranking(
                    last_burner_stats, answer_pool,
                    f"Top 20 burners (allowed list) for guess {guess_number}",
                    sort_mode)
            continue                        # S does NOT count as a guess

        # ── D: Detailed bucket analysis for a single word ──
        # Calls print_bucket_distribution() against the current answer_pool.
        # Does NOT count as a guess — guess_number is NOT incremented.
        # Accepts any valid 5-letter Wordle word (answer list OR allowed list).
        if user_input.upper() == 'D':
            try:
                detail_input = input("  Word to analyse > ").strip().lower()
            except EOFError:
                continue

            # Basic format check
            if len(detail_input) != 5 or not detail_input.isalpha():
                print("  ❌ Must be exactly 5 letters.")
                continue

            # Validate against known word lists
            # Load allowed list now if not yet loaded (needed for validation)
            if allowed_list is None:
                print("  ⏳ Loading allowed guesses list for validation...")
                try:
                    allowed_list = load_allowed_list()
                except RuntimeError as e:
                    print(f"  ⚠️  Could not load allowed list: {e}")
                    print(f"  ⚠️  Proceeding — validation against answer list only.")

            combined = set(answer_list) | (set(allowed_list) if allowed_list else set())
            if detail_input not in combined:
                print(f"  ⚠️  '{detail_input.upper()}' is not a recognised Wordle word. "
                      f"Proceeding anyway.")

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

        # ── Record this guess in the transcript (v2.0) ──
        # This one append IS the entire state update. No rules derived,
        # no dictionaries merged — the raw observation is stored intact.
        # C++ equivalent: history.push_back({guess, pattern_tuple});
        history.append((guess, pattern_tuple))

        # ── Filter answer_pool — ALWAYS from answer_list only! ──
        # Never use allowed_list here — those words can't be answers!
        # Replays the FULL transcript: every surviving word is consistent
        # with every guess played this game, not just the latest.
        answer_pool = filter_candidates(answer_list, history)

        # The pool just changed, so any cached tables are stale (v2.2).
        last_answer_stats = None
        last_burner_stats = None

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
            # v2.2: compute once, keep the full list, sort for display.
            print(f"\n  ⏳ Ranking from answer list...")
            last_answer_stats = compute_guess_stats(
                guess_pool  = answer_list,  # search answer list for best guess
                answer_pool = answer_pool,  # possible answers (unchanged!)
            )
            print_sorted_ranking(
                last_answer_stats, answer_pool,
                f"Top 20 guesses (answer list) for guess {guess_number + 1}",
                sort_mode)

            # ── Offer burner search from allowed list ──
            print()
            try:
                burner_input = input("  Search allowed guesses for better burner? (Y/N) > ").strip().upper()
            except EOFError:
                burner_input = 'N'

            if burner_input == 'Y':
                # Load allowed list on demand — cache after first load
                # C++ equivalent: if(allowed_list == nullptr) load it
                if allowed_list is None:
                    print("  ⏳ Loading allowed guesses list (one time only)...")
                    try:
                        allowed_list = load_allowed_list()
                    except RuntimeError as e:
                        print(f"  ❌ Could not load allowed list: {e}")
                        allowed_list = None   # reset so we try again next time

                if allowed_list is not None:
                    print(f"  ⏳ Searching {len(allowed_list)} allowed guesses...")
                    last_burner_stats = compute_guess_stats(
                        guess_pool  = allowed_list,  # search allowed list instead!
                        answer_pool = answer_pool,   # same possible answers!
                    )
                    print_sorted_ranking(
                        last_burner_stats, answer_pool,
                        f"Top 20 burners (allowed list) for guess {guess_number + 1}",
                        sort_mode)

        guess_number += 1               # increment AFTER processing — like i++ at end of loop

    # ── Game over — used all 6 guesses ──
    if guess_number > 6:
        print(f"\n  😔 Used all 6 guesses. Remaining candidates were:")
        print_candidates(answer_pool)
        print("  (R to restart, Q to quit)")
