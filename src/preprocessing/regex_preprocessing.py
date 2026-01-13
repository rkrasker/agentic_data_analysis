# -*- coding: utf-8 -*-
"""
WW2 roster extractor — pandas-only, fully vectorized, Unicode-safe (no \b), case-insensitive matching.
Outputs are ALWAYS ALL CAPS. Column names are Title Case. Includes optional timing and graceful failure.

Public API
----------
compile_patterns(gloss_df, *, stem_threshold=3, max_suffix_len=12,
                 num_min_len=1, num_max_len=3,
                 alpha_letters=("A","B","C","D","E","F","G"),
                 alpha_tokens=(),
                 special_num_lengths=None,
                 case_insensitive=True)

extract_roster_fields(df, gloss_df, *,
                      stem_threshold=3, max_suffix_len=12,
                      num_min_len=1, num_max_len=3,
                      alpha_letters=("A","B","C","D","E","F","G"),
                      alpha_tokens=(),
                      special_num_lengths=None,
                      case_insensitive=True,
                      keep_canonical=False,
                      enable_timing=False, return_timing=False,
                      on_error="sentinel",
                      sentinel_template=None)

Input expectations
------------------
- df          : pandas.DataFrame with at least 'Name' (required) and 'Notes' (optional).
- gloss_df    : DataFrame with columns:
                'full term' (str), 'abbreviations' (array-like or delimited str),
                'term type' in {'Organization Term','Unit Term','Role Term'}.

Key features
------------
- Regex alternations are built from the glossary.
  - Short forms (len ≤ stem_threshold) => LITERAL (must NOT be followed by a letter).
  - Long forms (len > stem_threshold)  => STEM/PREFIX (may be followed by up to max_suffix_len letters).
- Numeric tokens respect your digit-length bounds:
  - NUM := \d{num_min_len,num_max_len}(?:st|nd|rd|th)?
  - e.g., with num_max_len=3, "1944" is NOT matched in numeric-bearing categories.
- Alpha tokens:
  - alpha_letters: single letters you accept (e.g., A–G).
  - alpha_tokens : multi-character tokens (e.g., Roman numerals like II, VII, X).
  - We match longest-first; all outputs are UPPERCASE.
- Special numbers (optional):
  - Extract exact-length numbers, non-digit bounded (e.g., 4 or 6), into a separate column.
- Paired categories return colon-delimited strings for easy post-processing, e.g.:
  - UNIT: DIGIT => "PIR:506"
  - UNIT: ALPHA => "COMPANY:E"
  - ORG : DIGIT => "COUNTERINTELLIGENCE:75"
  - ALPHA: DIGIT => "C:5"
  Then we also provide split list-columns for each pair type.
- Factorize+take:
  - Parse each unique "Name ¶ Notes" string once; broadcast back to all rows.
- Timing (optional):
  - capture per-category wall times; return them if return_timing=True.
- Graceful error handling:
  - If a category fails, we still create its output columns filled with a visible sentinel like
    ["<EXTRACT_FAIL:UNIT_TERM_ALPHA>"], and we record the exception text.

Outputs (Title Case column names; ALL CAPS token strings)
---------------------------------------------------------
Core list columns:
  Org_Term_Numeric, Unit_Term_Numeric, Unit_Term_Alpha, Alpha_Numeric_Pairs,
  Unchar_Alpha, Unchar_Digits, Org_Terms, Unit_Terms, Role_Terms
Optional:
  Special_Numbers

Paired columns + derived splits:
  Org_Term_Digit_Term:Pair, Org_Term_Digit_Term:Org,   Org_Term_Digit_Digit
  Unit_Term_Digit_Term:Pair, Unit_Term_Digit_Term:Unit, Unit_Term_Digit_Digit
  Unit_Term_Alpha_Term:Pair, Unit_Term_Alpha_Term:Unit, Unit_Term_Alpha_Term:Alpha
  Alpha_Digit:Pair,          Alpha_Digit:Alpha,          Alpha_Digit:Digit
"""

from __future__ import annotations

import ast
import re
import time
import traceback
from typing import Iterable, Optional, Callable, Dict, List, Tuple

import numpy as np
import pandas as pd


# --------------------------- Utility / formatting helpers ---------------------------

def _normalize_series(s: pd.Series, lower: bool = True) -> pd.Series:
    """
    Lightweight, vectorized normalization for robust matching.
    - Normalizes curly quotes/dashes, collapses whitespace, strips ends.
    - casefold() if lower=True (for Unicode-safe, case-insensitive matching).
    """
    s = s.fillna("").astype("string")
    s = (s.str.replace(r"[\u2018\u2019]", "'", regex=True)
           .str.replace(r'[\u201C\u201D]', '"', regex=True)
           .str.replace(r'[\u2013\u2014]', '-', regex=True)
           .str.replace(r'\s+', ' ', regex=True)
           .str.strip())
    if lower:
        s = s.str.casefold()
    return s


def _listify_abbrev(x) -> List[str]:
    """
    Convert a cell from 'abbreviations' into a list[str].
    Accepts lists/tuples, JSON/python literals, or delimited strings.
    """
    if isinstance(x, (list, tuple)):
        return [str(v) for v in x if pd.notna(v)]
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return []
    s = str(x).strip()
    # Try to parse python/JSON list literal
    if s.startswith("[") and s.endswith("]"):
        try:
            li = ast.literal_eval(s)
            return [str(v) for v in li if pd.notna(v)]
        except Exception:
            pass
    # Fallback: split by common delimiters
    return [t for t in re.split(r"\s*[;,|]\s*", s) if t]


def _token_regexize(token: str) -> str:
    """
    Escape a surface form for regex, then allow flexible whitespace (\s+) for spaces.
    """
    esc = re.escape(token)
    return esc.replace(r"\ ", r"\s+")


def _strip_ordinal(num: str) -> str:
    """
    Remove English ordinal suffixes (st/nd/rd/th) after digits.
    """
    return re.sub(r"(?i)^(?P<n>\d+)(?:st|nd|rd|th)$", r"\g<n>", num)


def _sanitize_term_for_pair(term: str) -> str:
    """
    Ensure colon-delimited pairs split unambiguously: replace any ':' in term with '∶'.
    """
    return term.replace(":", "∶")


def _to_upper_display(s: str) -> str:
    """
    Your spec: all parsed text should be ALL CAPS.
    """
    return s.upper()


# --------------------------- Glossary → Alternations ---------------------------

def _build_alt_from_gloss(
    gloss_df: pd.DataFrame,
    stem_threshold: int,
    max_suffix_len: int
) -> Dict[str, str]:
    """
    From the glossary, build alternations for Organization/Unit/Role with
    literal-vs-stem behavior based on length. Return dict with keys 'ORG','UNIT','ROLE'
    and a 'surface_to_canonical' mapping for optional canonicalization.
    """
    g = gloss_df.copy()
    g["full term"] = _normalize_series(g["full term"])
    g["term type"] = _normalize_series(g["term type"])
    g["abbreviations"] = g["abbreviations"].map(_listify_abbrev)

    buckets = {
        "organization term": set(),
        "unit term": set(),
        "role term": set(),
    }
    surface_to_canonical: Dict[str, Tuple[str, str]] = {}

    for _, row in g.iterrows():
        canonical = row["full term"]
        ttype = row["term type"]
        # Combine canonical + all surface/abbrev forms
        forms = [canonical] + [
            _normalize_series(pd.Series([a])).iloc[0] for a in row["abbreviations"]
        ]
        for f in forms:
            if not f:
                continue
            buckets[ttype].add(f)
            # store canonical + type for optional mapping
            surface_to_canonical[f] = (canonical, ttype)

    def split_short_long(forms: Iterable[str]) -> Tuple[List[str], List[str]]:
        # Order longest-first within each bucket to prefer specific matches
        forms = sorted(set(forms), key=len, reverse=True)
        short, long_ = [], []
        for f in forms:
            if len(f) <= stem_threshold:
                short.append(_token_regexize(f))
            else:
                # STEM: allow up to max_suffix_len of trailing letters (Unicode-safe)
                long_.append(_token_regexize(f) + rf"[^\W\d_]{{0,{max_suffix_len}}}")
        return short, long_

    ORG_s, ORG_l = split_short_long(buckets["organization term"])
    UNIT_s, UNIT_l = split_short_long(buckets["unit term"])
    ROLE_s, ROLE_l = split_short_long(buckets["role term"])

    def alt(short: List[str], long_: List[str]) -> str:
        # Build "(short(?!letter) | long)" alternation;
        # if empty, use a never-match to keep grouping layout stable.
        alt_short = "|".join(short) if short else r"(?!x)x"
        alt_long  = "|".join(long_) if long_ else r"(?!x)x"
        return rf"(?:{alt_short}(?![^\W\d_])|{alt_long})"

    return {
        "ORG": alt(ORG_s, ORG_l),
        "UNIT": alt(UNIT_s, UNIT_l),
        "ROLE": alt(ROLE_s, ROLE_l),
        "surface_to_canonical": surface_to_canonical,
    }


# --------------------------- Pattern compiler ---------------------------

def compile_patterns(
    gloss_df: pd.DataFrame,
    *,
    stem_threshold: int = 3,
    max_suffix_len: int = 12,
    num_min_len: int = 1,
    num_max_len: int = 3,
    alpha_letters: Iterable[str] = ("A", "B", "C", "D", "E", "F", "G"),
    alpha_tokens: Iterable[str] = (),
    special_num_lengths: Optional[Iterable[int]] = None,
    case_insensitive: bool = True,
) -> Dict[str, object]:
    """
    Build and compile all category regex patterns with Unicode-safe boundaries.
    Returns a dict of compiled patterns plus helpers and maps.
    """
    alts = _build_alt_from_gloss(gloss_df, stem_threshold, max_suffix_len)

    # ---------- Alpha tokens matcher (letters OR explicit tokens like 'II','VII') ----------
    # Normalize inputs consistently with matching behavior
    alpha_letters = [c.strip() for c in alpha_letters if c and isinstance(c, str)]
    alpha_letters = sorted({c.upper() for c in alpha_letters})  # we will run IGNORECASE anyway
    # Longest-first for multi-char tokens (e.g., 'VIII' before 'VI' before 'V')
    alpha_tokens = [t.strip() for t in alpha_tokens if t and isinstance(t, str)]
    alpha_tokens = sorted({t.upper() for t in alpha_tokens}, key=len, reverse=True)

    # Character class for single letters (if provided)
    LETTER_CLASS = ""
    if alpha_letters:
        LETTER_CLASS = "[" + "".join(alpha_letters) + "]"

    # Alternation for explicit tokens, e.g., (VIII|VII|VI|V|IV|III|II|I)
    TOKENS_ALT = "|".join(map(re.escape, alpha_tokens)) if alpha_tokens else ""

    if LETTER_CLASS and TOKENS_ALT:
        ALPHA_TOKEN = rf"(?:{TOKENS_ALT}|{LETTER_CLASS})"
    elif TOKENS_ALT:
        ALPHA_TOKEN = rf"(?:{TOKENS_ALT})"
    elif LETTER_CLASS:
        ALPHA_TOKEN = LETTER_CLASS
    else:
        # If neither provided, make a never-match pattern to keep structure intact
        ALPHA_TOKEN = r"(?!x)x"

    # ---------- Boundaries, separators, numbers ----------
    # Unicode-safe: LB/RB are "previous/next is NOT a letter"
    LB  = r"(?<![^\W\d_])"
    RB  = r"(?![^\W\d_])"
    # Flexible separators allowed between components
    SEP = r"""[\s"“”'‘’:/\^\-,\u2013\u2014]*"""
    # Digit bounds with optional ordinal suffix
    NUM = rf"\d{{{num_min_len},{num_max_len}}}(?:st|nd|rd|th)?"

    # Inject alternations
    ORG  = rf"(?:{alts['ORG']})"
    UNIT = rf"(?:{alts['UNIT']})"
    ROLE = rf"(?:{alts['ROLE']})"

    flags = re.UNICODE | (re.IGNORECASE if case_insensitive else 0)

    patterns: Dict[str, object] = {
        # 1) Org_Term ↔ Digit (either order)  ➜  "ORG:DIGIT"
        "org_term_numeric": re.compile(
            rf"{LB}(?:(?P<num1>{NUM}){SEP}(?P<org1>{ORG})|(?P<org2>{ORG}){SEP}(?P<num2>{NUM})){RB}",
            flags,
        ),
        # 2) Unit_Term ↔ Digit (either order) ➜  "UNIT:DIGIT"
        "unit_term_numeric": re.compile(
            rf"{LB}(?:(?P<num1>{NUM}){SEP}(?P<unit1>{UNIT})|(?P<unit2>{UNIT}){SEP}(?P<num2>{NUM})){RB}",
            flags,
        ),
        # 3) Unit_Term ↔ Alpha (either order) ➜  "UNIT:ALPHA"
        "unit_term_alpha": re.compile(
            rf"{LB}(?:(?P<unitA>{UNIT}){SEP}(?P<alphaA>{ALPHA_TOKEN})|(?P<alphaB>{ALPHA_TOKEN}){SEP}(?P<unitB>{UNIT})){RB}",
            flags,
        ),
        # 4) Alpha ↔ Digit (either order)     ➜  "ALPHA:DIGIT"
        "alpha_numeric_pairs": re.compile(
            rf"{LB}(?:(?P<alpha1>{ALPHA_TOKEN}){SEP}(?P<num1>{NUM})|(?P<num2>{NUM}){SEP}(?P<alpha2>{ALPHA_TOKEN})){RB}",
            flags,
        ),
        # 5) Uncharacterized Alpha (standalone; not adjacent to digits)
        "unchar_alpha": re.compile(
            rf"(?<!\d){LB}(?P<alpha>{ALPHA_TOKEN})(?!\d){RB}",
            flags,
        ),
        # 6) Uncharacterized Digits (standalone number tokens)
        "unchar_digits": re.compile(
            rf"{LB}(?P<num>{NUM}){RB}",
            flags,
        ),
        # 7) Org Terms (standalone)
        "org_terms": re.compile(
            rf"{LB}(?P<org>{ORG}){RB}",
            flags,
        ),
        # 8) Unit Terms (standalone)
        "unit_terms": re.compile(
            rf"{LB}(?P<unit>{UNIT}){RB}",
            flags,
        ),
        # 9) Role Terms (standalone)
        "role_terms": re.compile(
            rf"{LB}(?P<role>{ROLE}){RB}",
            flags,
        ),
        # Optional: special numbers (exact length, non-digit bounded)
        "_specials": None,  # will be compiled below if requested
        "_surface_to_canonical": alts["surface_to_canonical"],
        "_config": {
            "num_min_len": num_min_len,
            "num_max_len": num_max_len,
            "alpha_letters": alpha_letters,
            "alpha_tokens": alpha_tokens,
            "special_num_lengths": list(special_num_lengths) if special_num_lengths else None,
        },
    }

    if special_num_lengths:
        lens = sorted(set(int(L) for L in special_num_lengths if int(L) > 0), reverse=True)
        # Alternation of exact-length non-digit-bounded numbers: (?<!\d)\d{L}(?!\d)
        parts = [rf"(?<!\d)(?P<s{L}>\d{{{L}}})(?!\d)" for L in lens]
        patterns["_specials"] = re.compile("|".join(parts), flags)

    return patterns


# --------------------------- Timing & error wrappers ---------------------------

def _timed(enable_timing: bool, timing_dict: dict, key: str):
    """
    Context manager to time a block and record its duration into timing_dict[key] (seconds).
    Does nothing when enable_timing=False.
    """
    class _Timer:
        def __enter__(self_inner):
            if enable_timing:
                self_inner.t0 = time.perf_counter()
            return self_inner
        def __exit__(self_inner, exc_type, exc, tb):
            if enable_timing:
                timing_dict[key] = timing_dict.get(key, 0.0) + (time.perf_counter() - self_inner.t0)
    return _Timer()


def _safe_extract(
    series_text: pd.Series,
    pattern: Optional[re.Pattern],
    maker: Optional[Callable[[pd.DataFrame], pd.Series]],
    enable_timing: bool,
    timing: dict,
    errors: dict,
    error_key: str,
    sentinel_factory: Callable[[str], List[str]],
) -> pd.Series:
    """
    Run one extraction category safely:
      - time it (optional),
      - return a list-valued Series aligned to series_text.index,
      - on error, return a Series of sentinel lists and record the exception.
    """
    col_len = len(series_text)
    if pattern is None:
        # For disabled/optional categories (like specials when not requested), return empty lists
        return pd.Series([[]] * col_len, index=series_text.index, dtype="object")

    try:
        with _timed(enable_timing, timing, error_key):
            ext = series_text.str.extractall(pattern)
            if ext.empty:
                return pd.Series([[]] * col_len, index=series_text.index, dtype="object")

            if maker is None:
                # Single captured group: first column is the token
                tok = ext.iloc[:, 0].astype("string")
            else:
                tok = maker(ext)

            # Group back matches per original row (level 0 of MultiIndex),
            # preserving match order (sort=False).
            lists = tok.groupby(level=0, sort=False).agg(list)
            out = pd.Series([[]] * col_len, index=series_text.index, dtype="object")
            out.update(lists)
            return out

    except Exception as e:
        # Graceful failure: fill with a per-category sentinel
        errors[error_key] = "".join(traceback.format_exception_only(type(e), e)).strip()
        sentinel = sentinel_factory(error_key)
        return pd.Series([sentinel] * col_len, index=series_text.index, dtype="object")


# --------------------------- Token constructors (ALL CAPS, colon pairs) ---------------------------

def _mk_pair_org_num(dfm: pd.DataFrame) -> pd.Series:
    # Either NUM + ORG or ORG + NUM → "ORG:DIGIT"
    left = dfm["num1"].notna()
    numL = dfm["num1"].where(left, dfm["num2"]).astype("string")
    orgL = dfm["org1"].where(left, dfm["org2"]).astype("string")
    num = numL.str.replace(r"(?i)(?:st|nd|rd|th)$", "", regex=True)
    org = orgL.map(lambda s: _to_upper_display(_sanitize_term_for_pair(str(s))))
    return (org + ":" + num).astype("string")


def _mk_pair_unit_num(dfm: pd.DataFrame) -> pd.Series:
    # Either NUM + UNIT or UNIT + NUM → "UNIT:DIGIT"
    left = dfm["num1"].notna()
    numL = dfm["num1"].where(left, dfm["num2"]).astype("string")
    unitL = dfm["unit1"].where(left, dfm["unit2"]).astype("string")
    num = numL.str.replace(r"(?i)(?:st|nd|rd|th)$", "", regex=True)
    unit = unitL.map(lambda s: _to_upper_display(_sanitize_term_for_pair(str(s))))
    return (unit + ":" + num).astype("string")


def _mk_pair_unit_alpha(dfm: pd.DataFrame) -> pd.Series:
    # Either UNIT + ALPHA or ALPHA + UNIT → "UNIT:ALPHA"
    # Normalize order so UNIT is always left, ALPHA right.
    left = dfm["unitA"].notna()
    unitL = dfm["unitA"].where(left, dfm["unitB"]).astype("string")
    alphaL = dfm["alphaA"].where(left, dfm["alphaB"]).astype("string")
    unit = unitL.map(lambda s: _to_upper_display(_sanitize_term_for_pair(str(s))))
    alpha = alphaL.map(lambda s: _to_upper_display(str(s)))
    return (unit + ":" + alpha).astype("string")


def _mk_pair_alpha_num(dfm: pd.DataFrame) -> pd.Series:
    # Either ALPHA + NUM or NUM + ALPHA → "ALPHA:DIGIT"
    left = dfm["alpha1"].notna()
    alphaL = dfm["alpha1"].where(left, dfm["alpha2"]).astype("string")
    numL = dfm["num1"].where(left, dfm["num2"]).astype("string")
    num = numL.str.replace(r"(?i)(?:st|nd|rd|th)$", "", regex=True)
    alpha = alphaL.map(lambda s: _to_upper_display(str(s)))
    return (alpha + ":" + num).astype("string")


def _mk_upper_single(dfm: pd.DataFrame, colname: str) -> pd.Series:
    # Convert a single captured group to ALL CAPS strings.
    return dfm[colname].astype("string").map(lambda s: _to_upper_display(str(s)))


# --------------------------- Vectorized extraction core (unique text only) ---------------------------

def _extract_unique_texts(
    su: pd.Series,
    pats: Dict[str, object],
    *,
    enable_timing: bool,
    on_error: str,
    sentinel_factory: Callable[[str], List[str]],
) -> Dict[str, pd.Series]:
    """
    Run all extractors on a Series of UNIQUE combined texts (Name ¶ Notes).
    Returns dict of list-valued Series aligned to su.index.
    """
    timing: Dict[str, float] = {}
    errors: Dict[str, str] = {}

    # 1) Paired categories → colon-delimited tokens (lists)
    org_num  = _safe_extract(su, pats["org_term_numeric"],  _mk_pair_org_num,
                             enable_timing, timing, errors, "org_term_numeric",  sentinel_factory)
    unit_num = _safe_extract(su, pats["unit_term_numeric"], _mk_pair_unit_num,
                             enable_timing, timing, errors, "unit_term_numeric", sentinel_factory)
    unit_alp = _safe_extract(su, pats["unit_term_alpha"],   _mk_pair_unit_alpha,
                             enable_timing, timing, errors, "unit_term_alpha",   sentinel_factory)
    an_pairs = _safe_extract(su, pats["alpha_numeric_pairs"], _mk_pair_alpha_num,
                             enable_timing, timing, errors, "alpha_numeric_pairs", sentinel_factory)

    # 2) Standalone categories
    unchar_alpha = _safe_extract(su, pats["unchar_alpha"],
                                 lambda dfm: _mk_upper_single(dfm, "alpha"),
                                 enable_timing, timing, errors, "unchar_alpha", sentinel_factory)
    unchar_digits = _safe_extract(su, pats["unchar_digits"],
                                  lambda dfm: dfm["num"].astype("string").map(lambda s: _strip_ordinal(str(s))),
                                  enable_timing, timing, errors, "unchar_digits", sentinel_factory)
    org_terms = _safe_extract(su, pats["org_terms"],
                              lambda dfm: _mk_upper_single(dfm, "org"),
                              enable_timing, timing, errors, "org_terms", sentinel_factory)
    unit_terms = _safe_extract(su, pats["unit_terms"],
                               lambda dfm: _mk_upper_single(dfm, "unit"),
                               enable_timing, timing, errors, "unit_terms", sentinel_factory)
    role_terms = _safe_extract(su, pats["role_terms"],
                               lambda dfm: _mk_upper_single(dfm, "role"),
                               enable_timing, timing, errors, "role_terms", sentinel_factory)

    # 3) Optional specials (exact-length numbers)
    specials = _safe_extract(su, pats.get("_specials"), None,
                             enable_timing, timing, errors, "special_numbers", sentinel_factory)

    # Return all outputs plus timing/errors packaged for caller (we attach timing/errors via closure)
    outputs = {
        "Org_Term_Digit_Term:Pair": org_num,
        "Unit_Term_Digit_Term:Pair": unit_num,
        "Unit_Term_Alpha_Term:Pair": unit_alp,
        "Alpha_Digit:Pair": an_pairs,
        "Unchar_Alpha": unchar_alpha,
        "Unchar_Digits": unchar_digits,
        "Org_Terms": org_terms,
        "Unit_Terms": unit_terms,
        "Role_Terms": role_terms,
        "Special_Numbers": specials,  # may be all empty lists if specials disabled
        "_timing": timing,
        "_errors": errors,
    }
    return outputs


# --------------------------- Pair split (explode → split → agg(list)) ---------------------------

def _split_pair_list_column(df: pd.DataFrame, pair_col: str, left_name: str, right_name: str,
                            enable_timing: bool, timing: dict, errors: dict,
                            sentinel_factory: Callable[[str], List[str]]) -> Tuple[pd.Series, pd.Series]:
    """
    Given a list-valued column of "LEFT:RIGHT" strings, build two aligned list-valued columns
    for LEFT and RIGHT via a vectorized explode/split/agg(list) pattern.
    On error, return sentinel lists and record the exception.
    """
    key = f"_split::{pair_col}"
    try:
        with _timed(enable_timing, timing, key):
            # Fast path: empty column (all []): just return empty lists
            if df[pair_col].map(len).sum() == 0:
                n = len(df)
                return (pd.Series([[]]*n, index=df.index, dtype="object"),
                        pd.Series([[]]*n, index=df.index, dtype="object"))

            long = df[[pair_col]].explode(pair_col, ignore_index=False)
            parts = long[pair_col].str.split(":", n=1, expand=True)
            parts.columns = [left_name, right_name]
            # Group back per original row
            left_lists  = parts.groupby(level=0, sort=False)[left_name].agg(list)
            right_lists = parts.groupby(level=0, sort=False)[right_name].agg(list)

            # Prepare full-length outputs (fill missing with empty lists)
            n = len(df)
            left_out  = pd.Series([[]]*n, index=df.index, dtype="object")
            right_out = pd.Series([[]]*n, index=df.index, dtype="object")
            left_out.update(left_lists)
            right_out.update(right_lists)
            return left_out, right_out

    except Exception as e:
        errors[key] = "".join(traceback.format_exception_only(type(e), e)).strip()
        sentinel = sentinel_factory(pair_col)
        n = len(df)
        return (pd.Series([sentinel]*n, index=df.index, dtype="object"),
                pd.Series([sentinel]*n, index=df.index, dtype="object"))


# --------------------------- Public API: main extractor ---------------------------

def extract_roster_fields(
    df: pd.DataFrame,
    gloss_df: pd.DataFrame,
    *,
    stem_threshold: int = 3,
    max_suffix_len: int = 12,
    num_min_len: int = 1,
    num_max_len: int = 3,
    alpha_letters: Iterable[str] = ("A", "B", "C", "D", "E", "F", "G"),
    alpha_tokens: Iterable[str] = (),
    special_num_lengths: Optional[Iterable[int]] = None,
    case_insensitive: bool = True,
    keep_canonical: bool = False,   # (kept for parity; we uppercase outputs regardless)
    enable_timing: bool = False,
    return_timing: bool = False,
    on_error: str = "sentinel",     # or "raise"
    sentinel_template: Optional[Callable[[str], List[str]]] = None,
):
    """
    Run all extraction categories on df['Name'] and df['Notes'] (combined).
    - Fully vectorized; parses each unique "Name ¶ Notes" exactly once.
    - Returns df copy with list-valued columns (Title Case names); ALL CAPS tokens.
    - If return_timing=True, returns (df_out, timing_dict) with per-step durations and any captured errors.
    """
    if "Name" not in df.columns:
        raise ValueError("Input DataFrame must contain a 'Name' column.")
    if sentinel_template is None:
        sentinel_template = lambda cat: [f"<EXTRACT_FAIL:{cat.upper()}>"]

    # 0) Compile patterns once
    timing: Dict[str, float] = {}
    with _timed(enable_timing, timing, "compile_patterns"):
        pats = compile_patterns(
            gloss_df,
            stem_threshold=stem_threshold,
            max_suffix_len=max_suffix_len,
            num_min_len=num_min_len,
            num_max_len=num_max_len,
            alpha_letters=alpha_letters,
            alpha_tokens=alpha_tokens,
            special_num_lengths=special_num_lengths,
            case_insensitive=case_insensitive,
        )

    # 1) Build combined, normalized text ("Name ¶ Notes")
    name_norm  = _normalize_series(df["Name"], lower=True)
    notes_norm = _normalize_series(df["Notes"], lower=True) if "Notes" in df.columns else pd.Series([""]*len(df), index=df.index, dtype="string")
    with _timed(enable_timing, timing, "combine_text"):
        text = (name_norm + " ¶ " + notes_norm).astype("string")

    # 2) Factorize to avoid re-parsing repeated strings
    with _timed(enable_timing, timing, "factorize"):
        codes, uniques = pd.factorize(text, sort=False)
        su = pd.Series(uniques, name="text").astype("string")

    # 3) Extract on UNIQUE texts only
    outputs = _extract_unique_texts(
        su, pats,
        enable_timing=enable_timing,
        on_error=on_error,
        sentinel_factory=sentinel_template,
    )

    # 4) Broadcast UNIQUE outputs back to all rows via Index.take (fast, no merge)
    df_out = df.copy()
    idxer = pd.Index(range(len(su)))  # aligns with Series.take
    for k in [
        "Org_Term_Digit_Term:Pair",
        "Unit_Term_Digit_Term:Pair",
        "Unit_Term_Alpha_Term:Pair",
        "Alpha_Digit:Pair",
        "Unchar_Alpha",
        "Unchar_Digits",
        "Org_Terms",
        "Unit_Terms",
        "Role_Terms",
        "Special_Numbers",
    ]:
        s_uni = outputs[k]
        df_out[k] = pd.Series(s_uni.values).take(codes)

    # 5) Split colon-pair columns into their derived left/right list columns
    #    (still vectorized via explode/split/agg(list) and timed)
    errors = outputs["_errors"]
    timing_local = outputs["_timing"]

    # Org_Term ↔ Digit
    L, R = _split_pair_list_column(df_out, "Org_Term_Digit_Term:Pair",
                                   "Org_Term_Digit_Term:Org", "Org_Term_Digit_Digit",
                                   enable_timing, timing_local, errors, sentinel_template)
    df_out["Org_Term_Digit_Term:Org"] = L
    df_out["Org_Term_Digit_Digit"]    = R

    # Unit_Term ↔ Digit
    L, R = _split_pair_list_column(df_out, "Unit_Term_Digit_Term:Pair",
                                   "Unit_Term_Digit_Term:Unit", "Unit_Term_Digit_Digit",
                                   enable_timing, timing_local, errors, sentinel_template)
    df_out["Unit_Term_Digit_Term:Unit"] = L
    df_out["Unit_Term_Digit_Digit"]     = R

    # Unit_Term ↔ Alpha
    L, R = _split_pair_list_column(df_out, "Unit_Term_Alpha_Term:Pair",
                                   "Unit_Term_Alpha_Term:Unit", "Unit_Term_Alpha_Term:Alpha",
                                   enable_timing, timing_local, errors, sentinel_template)
    df_out["Unit_Term_Alpha_Term:Unit"]  = L
    df_out["Unit_Term_Alpha_Term:Alpha"] = R

    # Alpha ↔ Digit
    L, R = _split_pair_list_column(df_out, "Alpha_Digit:Pair",
                                   "Alpha_Digit:Alpha", "Alpha_Digit:Digit",
                                   enable_timing, timing_local, errors, sentinel_template)
    df_out["Alpha_Digit:Alpha"] = L
    df_out["Alpha_Digit:Digit"] = R

    # 6) (Optional) Canonicalization of term sides BEFORE uppercasing could be added here.
    #     Your current spec asks only for ALL CAPS outputs; leave keep_canonical=False by default.
    #     If you want canonicals, we can map the LEFT side of each pair (and standalone *_Terms)
    #     via pats["_surface_to_canonical"] prior to uppercasing (or map then uppercase).

    # 7) Return with timing if requested
    if return_timing:
        # Merge top-level timing with inner timing stages and include any errors captured
        timing_all = {**timing, **timing_local}
        if errors:
            timing_all["errors"] = errors  # convey which components failed and why
        return df_out, timing_all
    return df_out


# --------------------------------- Example usage (comment) ---------------------------------
#
# import pandas as pd
#
# # df must contain 'Name' (required) and 'Notes' (optional)
# df = pd.DataFrame({
#     "Soldier ID": ["S1","S2","S3"],
#     "Name": [
#         'Smith, John A. "Jack" — Medic; Co E; 2/506th PIR — 3rd Plt; attached to 75th Counterintelligence.',
#         'García, Miguel L. (Cpl) — Company A; 1-505 PIR; XO: Co A.',
#         'Tanaka, Hiroshi — 2nd Marine Raider Bn; Co F; Battery B, 10th FA; to VMF-214.',
#     ],
#     "Notes": [
#         "Reassigned to HQ Co, 2/506 PIR; 15th AF.",
#         '"Black Sheep"; patrol on 06-06-44; 5 A.',
#         "Crew Chief; promoted Capt.",
#     ]
# })
#
# gloss = pd.DataFrame({
#     "full term": ["Counterintelligence","Parachute Infantry Regiment","Division","Battalion","Company","Platoon","Headquarters Squadron","Marine Fighting Squadron","Air Forces","Medic","Executive Officer","Captain","Battery"],
#     "abbreviations": [[],["PIR"],["Div"],["Bn"],["Co"],["Plt"],["HQ Sq"],["VMF"],["AF"],["Aid Man"],["XO"],["Capt"],["Bty"]],
#     "term type": ["Organization Term","Unit Term","Unit Term","Unit Term","Unit Term","Unit Term","Unit Term","Unit Term","Organization Term","Role Term","Role Term","Role Term","Unit Term"]
# })
#
# cfg = dict(
#     stem_threshold=3,
#     max_suffix_len=12,
#     num_min_len=1, num_max_len=3,            # e.g., exclude 4-digit years from numeric categories
#     alpha_letters=list("ABCDEFG"),
#     alpha_tokens=["II","III","IV","V","VI","VII","VIII","IX","X"],  # Roman numerals
#     special_num_lengths=[4],                  # (optional) collect exact 4-digit numbers (e.g., years)
#     case_insensitive=True,
#     enable_timing=True, return_timing=True,   # get timing breakdown
# )
#
# parsed_df, timing = extract_roster_fields(df, gloss, **cfg)
# print(parsed_df.columns)
# print(timing)
