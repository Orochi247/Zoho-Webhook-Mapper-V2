"""
Zoho Forms Webhook Mapper v2 — maps BOTH sides of each webhook row, in your order.

Difference from v1 (webhook_mapper.py in Orochi247/Zoho-Webhook-Mapper):
  v1 renamed the LEFT Parameter Name of rows that Auto-Map had already created,
  so the row order (and therefore the payload / output PDF order) stayed in
  Zoho form order. v2 builds the rows itself, in the order of your input file:
    1. click the + (plus) icon to add a row,
    2. type the Parameter Name into the left input,
    3. open the right dropdown and select the Zoho form field by its label.
  Because rows are created in input order, an input file in official MLS PDF
  order (sections + sequence) produces a webhook in MLS PDF order.

Two modes (--mode):
  automap (default): use Zoho's own "Auto-Map Fields" to create one row per
    form field, then rewrite each row in sequence — left Parameter Name from
    the input, right dropdown changed to the input's Zoho label. Row i of the
    page becomes pair i of your file, so the sequence is yours, not Zoho's.
    This mode does not need the + button at all.
  add: the flow above — click + for each new row, then set both sides.
    Use it if Auto-Map is unavailable or you only want a subset of rows
    created from scratch.

Hidden fields:
  Fields whose Zoho label is a hidden field (orange / yellow eye-slash icon in
  the form builder) are SKIPPED by default. See HIDDEN_ZOHO_LABELS below and
  the --include-hidden flag. The 9 common fields are NOT added unless you pass
  --include-common (most of them are hidden/system fields; the screenshot
  mapping for them is kept in COMMON_MAP).

Setup:
    python -m pip install playwright

Run:
    python webhook_mapper_v2.py pairs.json --dry-run     # preview what will be mapped, no browser
    python webhook_mapper_v2.py pairs.json --inspect     # dump row/dropdown HTML to inspect.txt, no filling
    python webhook_mapper_v2.py pairs.json --limit 3     # test on 3 rows first
    python webhook_mapper_v2.py pairs.json               # full run
    python webhook_mapper_v2.py pairs.json --url <form integrate URL>

IMPORTANT: Zoho's page structure is not fully known from screenshots alone.
If the + button or the right dropdown is not found, run --inspect once and
share inspect.txt — the selectors at the top of this file are the only thing
that should need adjusting. The script never clicks Save; you review and save.
"""

import argparse
import json
import sys
from pathlib import Path

# Playwright is imported lazily in main() so that --dry-run and the
# input-loading logic work on machines without Playwright installed.

# --------------------------------------------------------------------------
# Config — edit these if your form / Zoho layout differs
# --------------------------------------------------------------------------

WEBHOOK_URL = (
    "https://forms.zoho.com/houzeo/form/"
    "testARNorthwestArkansasBoardofRealtorsNABORMLSData/integrate"
    # v1's hardcoded form. Pass --url for any other form, e.g. NABOR.
)

BROWSER_CHANNEL = "chrome"          # "chrome" or "msedge" (uses the browser already installed)
PROFILE_DIR = "./zoho_profile"      # keeps your login/MFA session between runs
FAILED_LOG = Path("failed_rows.txt")
SKIPPED_LOG = Path("skipped_fields.txt")

TYPE_DELAY_MS = 5                   # per-keystroke delay; raise if Zoho misses key events
SETTLE_MS = 350                     # wait after each action so Zoho can update the row

# One webhook row (same container v1 used) and the left input inside it.
ROW = "div[elname='webhookPayloadParam']"
LEFT_INPUT = "div[elname='webhookPayloadParam'] input[elname='param_name']"

# Candidate selectors for the + (add row) button, tried in order.
# The screenshot shows a green + icon at the right end of a row.
PLUS_SELECTORS = [
    "div[elname='webhookPayloadParam'] [elname='addParam']",
    "div[elname='webhookPayloadParam'] .addIcon",
    "div[elname='webhookPayloadParam'] a[title*='Add' i]",
    "div[elname='webhookPayloadParam'] span[title*='Add' i]",
    "[elname='addWebhookParam']",
    ".webhookAddRow",
]

# The right-hand field control INSIDE one row. Confirmed from Zoho's actual
# DOM (DevTools screenshot, 2026-11-19):
#   row  = div.webhook_Payload[elname='webhookPayloadParam']
#   left = div[elname='paramNameDiv'] > input[elname='param_name']
#   right= div[elname='paramValueDiv'] > div[elname='selectParentDiv']
#          > select[elname='param_fld_select']  (a native <select> that
#          Select2 hides: class 'select2-hidden-accessible')
#   Each <option> has value/link_name = Zoho's internal field ID
#   (SingleLine, SingleLine2, Radio2, Dropdown26, ...) and its TEXT is the
#   field label shown to users (Address, County, List Price, ...).
# So the dropdown is matched by option TEXT, never by value.
FIELD_SELECT = "select[elname='param_fld_select']"

# Fallback selectors if a Zoho variant ever renders something else.
RIGHT_CONTROL_SELECTORS = [
    FIELD_SELECT,
    "select",
    "[elname='param_value']",
    "[elname='field_name']",
    "[elname='webhookField']",
    "input[readonly]",
    "input:not([elname='param_name'])",
    ".zf-select",
    "[class*='dropdown']",
]

# The "Auto-Map Fields" link at the top right of the Payload Mapping page
# (visible in the screenshot). Tried by exact text first.
AUTOMAP_TEXT = "Auto-Map Fields"

# Candidate selectors for the - (remove row) button, tried in order.
# The screenshot shows a red - icon next to the + icon at the end of a row.
MINUS_SELECTORS = [
    "div[elname='webhookPayloadParam'] [elname='removeParam']",
    "div[elname='webhookPayloadParam'] .removeIcon",
    "div[elname='webhookPayloadParam'] a[title*='Remove' i]",
    "div[elname='webhookPayloadParam'] span[title*='Remove' i]",
    "div[elname='webhookPayloadParam'] a[title*='Delete' i]",
]

EXTRA_LOG = Path("extra_rows.txt")

# Candidate selectors for a visible option inside an opened custom dropdown.
OPTION_SELECTORS = [
    "[role='listbox'] [role='option']",
    "[role='option']",
    ".dropdown-menu li",
    ".select2-results__option",
    "ul[class*='dropdown'] li",
    "div[class*='option']",
]

# Zoho labels of hidden fields (orange/yellow eye-slash in the builder).
# This set is from the NABOR builder print, Page 10 hidden block.
# Add/remove labels for other MLS forms, or mark a field "hidden": true
# in the input file — both are honoured.
HIDDEN_ZOHO_LABELS = {
    "Time",
    "Exempted Name Prospects",
    "Allow Virtual Office Website",
    "Internet OK",
    "Allow Blogging",
    "Allow Address Display",
    "Allow Auto Valuation",
    "live_key",
    "task_id",
    "Unique ID",
    "env",
    "Listing Date",
    "Plan End Date",
    "Listing Term",
    "Private Agent Remark",
    "house_id",
}

# The 9 common fields and the right-dropdown label seen for each in the
# webhook screenshot. Only used with --include-common. They bypass the
# hidden-field filter on purpose: the server expects them first.
COMMON_MAP = [
    ("task_id", "task_id"),
    ("FormID", "Unique ID"),
    ("UniqueID", "Unique ID"),
    ("Date_Created", "Date-Time"),
    ("Address", "Address"),
    ("env", "env"),
    ("added_time", "Added Time"),
    ("ip_address", "IP Address"),
    ("house_id", "house_id"),
]

# --------------------------------------------------------------------------
# Input loading — returns a list of dicts:
#   {"parameter_name": str, "zoho_label": str | None, "candidates": [str]}
# --------------------------------------------------------------------------

def label_candidates(parameter_name, zoho_label):
    """Dropdown labels to try, best first.

    With an explicit zoho_label (master / pairs input) that is the only
    serious candidate. For a legacy flat list we fall back to suffixes of
    the parameter name: Address_Information_Parcel_Number ->
    'Information Parcel Number', 'Parcel Number', 'Number' (longest first).
    """
    candidates = []
    if zoho_label:
        candidates.append(zoho_label)
    words = parameter_name.split("_")
    for start in range(1, len(words)):
        cand = " ".join(words[start:])
        if cand and cand not in candidates:
            candidates.append(cand)
    return candidates


def _pair(parameter_name, zoho_label=None, hidden=False, match=None):
    return {
        "parameter_name": str(parameter_name),
        "zoho_label": zoho_label,
        "candidates": label_candidates(str(parameter_name), zoho_label),
        "hidden_flag": bool(hidden),
        "match": match,
    }


def load_pairs(path):
    """Accepts, in order of preference:
    1. Master JSON: {"sections": [{"fields": [{"parameter_name", "zoho_label",
       "match", "hidden"?}, ...]}, ...], "hidden_zoho_labels"?: [...]}
       Fields with match == "pdf_only" or no zoho_label are counted, not mapped.
    2. Pairs list:  [{"parameter_name": ..., "zoho_label": ...}, ...]
       (also accepts {"parameter"/"name"} and {"field"/"label"} keys)
    3. Object:      {"Parameter_Name": "Zoho Label", ...}  (values = labels)
    4. Legacy list: ["Parameter_Name", ...]  (label guessed from the name)
    Returns (pairs, stats_dict).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    stats = {"pdf_only_skipped": 0, "total_in_file": 0}

    if isinstance(data, dict) and "hidden_zoho_labels" in data:
        HIDDEN_ZOHO_LABELS.update(str(x) for x in data["hidden_zoho_labels"])

    # 1. Master JSON
    if isinstance(data, dict) and isinstance(data.get("sections"), list):
        pairs = []
        for section in data["sections"]:
            for field in section.get("fields", []):
                stats["total_in_file"] += 1
                zoho = field.get("zoho_label")
                if field.get("match") == "pdf_only" or not zoho:
                    stats["pdf_only_skipped"] += 1
                    continue
                pairs.append(_pair(field["parameter_name"], zoho,
                                   hidden=field.get("hidden", False),
                                   match=field.get("match")))
        return pairs, stats

    # 2. Pairs list
    if isinstance(data, list) and data and isinstance(data[0], dict):
        pairs = []
        for item in data:
            stats["total_in_file"] += 1
            param = item.get("parameter_name") or item.get("parameter") or item.get("name")
            zoho = item.get("zoho_label") or item.get("field") or item.get("label")
            if not param:
                continue
            pairs.append(_pair(param, zoho, hidden=item.get("hidden", False),
                               match=item.get("match")))
        return pairs, stats

    # 3. Object mapping
    if isinstance(data, dict):
        pairs = []
        for param, zoho in data.items():
            stats["total_in_file"] += 1
            pairs.append(_pair(param, zoho if isinstance(zoho, str) else None))
        return pairs, stats

    # 4. Legacy flat list
    if isinstance(data, list):
        pairs = []
        for item in data:
            stats["total_in_file"] += 1
            pairs.append(_pair(item, None))
        return pairs, stats

    raise ValueError("JSON must be a master object, a pairs list, an object, or a flat list")


def split_hidden(pairs, include_hidden):
    """Returns (to_map, skipped_hidden)."""
    if include_hidden:
        return pairs, []
    to_map, skipped = [], []
    for p in pairs:
        if p["hidden_flag"] or (p["zoho_label"] in HIDDEN_ZOHO_LABELS):
            skipped.append(p)
        else:
            to_map.append(p)
    return to_map, skipped

# --------------------------------------------------------------------------
# Page actions
# --------------------------------------------------------------------------

def fill_left(row, parameter_name):
    box = row.locator("input[elname='param_name']").first
    box.scroll_into_view_if_needed()
    box.click()
    box.press("Control+A")
    box.press("Delete")
    box.press_sequentially(parameter_name, delay=TYPE_DELAY_MS)  # real key events
    box.press("Tab")
    if box.input_value() != parameter_name:
        raise RuntimeError(f"left value mismatch, got {box.input_value()!r}")


def _visible_option(page, candidate):
    """Find a visible dropdown option whose text is exactly `candidate`."""
    for selector in OPTION_SELECTORS:
        options = page.locator(selector)
        for i in range(options.count()):
            opt = options.nth(i)
            try:
                if opt.is_visible() and opt.inner_text().strip() == candidate:
                    return opt
            except Exception:
                continue
    # Last resort: exact text anywhere visible (Zoho renders options as plain items)
    try:
        opt = page.get_by_text(candidate, exact=True).last
        if opt.is_visible():
            return opt
    except Exception:
        pass
    return None


_SET_SELECT_BY_TEXT_JS = """
(el, label) => {
  const opts = Array.from(el.options).filter(o => o.text.trim() === label);
  if (opts.length === 0) return {found: false, count: 0};
  el.value = opts[0].value;
  // Notify Select2 (jQuery) and native listeners that the value changed,
  // so Zoho's visible Select2 box and its save/preview state stay in sync.
  if (window.jQuery) { window.jQuery(el).trigger('change'); }
  el.dispatchEvent(new Event('change', {bubbles: true}));
  el.dispatchEvent(new Event('input', {bubbles: true}));
  const sel = el.options[el.selectedIndex];
  return {found: true, count: opts.length, value: el.value,
          text: sel ? sel.text.trim() : ''};
}
"""


def _select_via_select2_ui(page, row, candidates):
    """Fallback: click the visible Select2 box in this row, type the label
    in its search box if one appears, and click the matching result."""
    box = row.locator(".select2-selection, .select2-container").first
    if box.count() == 0:
        return None
    try:
        box.scroll_into_view_if_needed()
        box.click()
        page.wait_for_timeout(SETTLE_MS)
    except Exception:
        return None
    for cand in candidates:
        # Select2 often shows a search input at the top of the open dropdown.
        try:
            search = page.locator(".select2-search__field").first
            if search.count() > 0 and search.is_visible():
                search.fill(cand)
                page.wait_for_timeout(SETTLE_MS)
        except Exception:
            pass
        opt = _visible_option(page, cand)
        if opt is not None:
            opt.click()
            page.wait_for_timeout(SETTLE_MS)
            return cand
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    return None


def select_right(page, row, candidates):
    """Select the Zoho field in this row's right dropdown. Returns the
    candidate that worked, or raises RuntimeError listing what was tried.

    Primary path (confirmed DOM): the row contains a native
    select[elname='param_fld_select'] hidden by Select2. Playwright's
    select_option() can refuse hidden elements, so the value is set by
    exact option TEXT in JS and a change event is fired for Select2.
    If several options share the same text, the first is used and a
    warning is printed — check those rows manually.
    """
    select = row.locator(FIELD_SELECT).first
    if select.count() > 0:
        for cand in candidates:
            try:
                result = select.evaluate(_SET_SELECT_BY_TEXT_JS, cand)
            except Exception:
                result = None
            if result and result.get("found"):
                if result.get("count", 1) > 1:
                    print(f"    [warn] label {cand!r} matches {result['count']} dropdown options; used the first (value={result.get('value')})")
                page.wait_for_timeout(SETTLE_MS)
                return cand
            # Belt and braces: try Playwright's own select_option too.
            try:
                select.select_option(label=cand, force=True)
                page.wait_for_timeout(SETTLE_MS)
                return cand
            except Exception:
                continue
        used = _select_via_select2_ui(page, row, candidates)
        if used:
            return used
        raise RuntimeError(f"no <option> with exact text matched; tried {candidates}")
    # No native select in this row (unexpected Zoho variant): custom dropdown.
    used = _select_via_select2_ui(page, row, candidates)
    if used:
        return used
    raise RuntimeError(f"no {FIELD_SELECT} found in row and Select2 UI fallback failed; tried {candidates}")


def click_plus(page):
    """Click the + (add row) button. Returns True if a selector matched."""
    for selector in PLUS_SELECTORS:
        btn = page.locator(selector).last
        if btn.count() > 0:
            try:
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(SETTLE_MS)
                return True
            except Exception:
                continue
    # Fallback: the green + icon sits right after the last row in the
    # screenshot; try any visible element whose text is exactly '+' near rows.
    try:
        btn = page.locator(ROW).last.locator("xpath=following-sibling::*//*[normalize-space(text())='+']").first
        if btn.count() > 0:
            btn.click()
            page.wait_for_timeout(SETTLE_MS)
            return True
    except Exception:
        pass
    return False


def click_automap(page):
    """Click Zoho's 'Auto-Map Fields' link. Returns True if clicked."""
    try:
        link = page.get_by_text(AUTOMAP_TEXT, exact=True).first
        if link.count() > 0 and link.is_visible():
            link.click()
            page.wait_for_timeout(SETTLE_MS * 4)  # automap can take a moment
            return True
    except Exception:
        pass
    for selector in ("a:has-text('Auto-Map')", "span:has-text('Auto-Map')", "[title*='Auto-Map' i]"):
        try:
            el = page.locator(selector).first
            if el.count() > 0 and el.is_visible():
                el.click()
                page.wait_for_timeout(SETTLE_MS * 4)
                return True
        except Exception:
            continue
    return False


def read_right_text(row):
    """Best-effort read of a row's current right-dropdown value, for logging."""
    for selector in RIGHT_CONTROL_SELECTORS:
        control = row.locator(selector).first
        if control.count() == 0:
            continue
        try:
            tag = control.evaluate("el => el.tagName.toLowerCase()")
            if tag == "select":
                return control.evaluate("el => el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : ''").strip()
            if tag == "input":
                return control.input_value().strip()
            return control.inner_text().strip()
        except Exception:
            continue
    return ""


def delete_row_at(page, index):
    """Click the - (remove) button for the row at `index`. Returns True if
    the row count went down."""
    rows = page.locator(ROW)
    before = rows.count()
    if index >= before:
        return False
    row = rows.nth(index)
    for selector in MINUS_SELECTORS:
        # MINUS_SELECTORS are page-scoped; scope them to this row's position
        # by taking the nth match on the page (one - button per row).
        btn = page.locator(selector).nth(index)
        if btn.count() > 0:
            try:
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(SETTLE_MS)
                if page.locator(ROW).count() < before:
                    return True
            except Exception:
                continue
    # Fallback: a '-' control inside the row container itself.
    try:
        btn = row.locator("xpath=.//*[normalize-space(text())='-']").first
        if btn.count() > 0:
            btn.click()
            page.wait_for_timeout(SETTLE_MS)
            return page.locator(ROW).count() < before
    except Exception:
        pass
    return False


def ensure_row(page, index, always_plus):
    """Make sure a row exists for `index` and return its row locator.

    Default flow: reuse an existing blank row if one is available
    (the page usually loads with one), otherwise click + for a new row.
    With always_plus=True, click + for every field after the first row
    is known to be blank-free — use this if your page loads with no rows.
    """
    rows = page.locator(ROW)
    count = rows.count()
    if index < count and not always_plus:
        return rows.nth(index)
    before = count
    if not click_plus(page):
        raise RuntimeError("could not find the + (add row) button — run with --inspect and share inspect.txt")
    rows = page.locator(ROW)
    if rows.count() <= before:
        raise RuntimeError("clicked +, but no new row appeared")
    return rows.nth(rows.count() - 1)


def inspect_page(page):
    """Dump the HTML we need to fix selectors, without filling anything."""
    out = []
    rows = page.locator(ROW)
    out.append(f"ROW count: {rows.count()}")
    for i in range(min(rows.count(), 3)):
        try:
            out.append(f"\n--- ROW {i} outerHTML ---\n" + rows.nth(i).evaluate("el => el.outerHTML")[:6000])
        except Exception as e:
            out.append(f"ROW {i}: could not read HTML ({e})")
    try:
        parent_html = page.locator(ROW).first.locator("xpath=..").evaluate("el => el.outerHTML")
        out.append("\n--- ROW PARENT outerHTML (first 8000 chars) ---\n" + parent_html[:8000])
    except Exception as e:
        out.append(f"Parent HTML unavailable ({e})")
    # First row's dropdown: option count + a sample of option texts/values.
    try:
        info = page.locator(ROW).first.locator(FIELD_SELECT).evaluate(
            """el => ({count: el.options.length,
                       sample: Array.from(el.options).slice(0, 15).map(o => o.value + ' :: ' + o.text)})"""
        )
        out.append(f"\n--- FIRST ROW DROPDOWN ---\noptions: {info['count']}\n" + "\n".join(info["sample"]))
    except Exception as e:
        out.append(f"Dropdown info unavailable ({e})")
    # Hunt for the + / - controls anywhere near the rows: they are not inside
    # the row element itself (a row contains only paramNameDiv + paramValueDiv).
    try:
        found = page.evaluate(
            """() => Array.from(document.querySelectorAll('*'))
              .filter(el => {
                const s = ((el.getAttribute('elname') || '') + ' ' + (el.className && el.className.baseVal !== undefined ? '' : (el.className || '')) + ' ' + (el.getAttribute('title') || '')).toLowerCase();
                return /add|remove|delete|plus|minus/.test(s) && el.children.length <= 2;
              })
              .slice(0, 40)
              .map(el => el.tagName + ' elname=' + (el.getAttribute('elname') || '') +
                         ' class=' + (el.getAttribute('class') || '') +
                         ' title=' + (el.getAttribute('title') || '') +
                         ' text=' + (el.innerText || '').trim().slice(0, 30))"""
        )
        out.append("\n--- POSSIBLE + / - CONTROLS ---\n" + ("\n".join(found) if found else "none found"))
    except Exception as e:
        out.append(f"+/- hunt unavailable ({e})")
    Path("inspect.txt").write_text("\n".join(out), encoding="utf-8")
    print("Wrote inspect.txt — share it if the + button or dropdown selectors need fixing.")

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Zoho webhook mapper v2 — sets both sides, in input order.")
    ap.add_argument("json_file")
    ap.add_argument("--url", default=WEBHOOK_URL)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--include-hidden", action="store_true",
                    help="also map hidden (orange eye) fields instead of skipping them")
    ap.add_argument("--include-common", action="store_true",
                    help="prepend the 9 common fields (see COMMON_MAP) before the file's fields")
    ap.add_argument("--mode", choices=["automap", "add"], default="automap",
                    help="automap: Auto-Map all fields, then rewrite rows in sequence (default, no + needed). "
                         "add: click + for each new row, then set both sides")
    ap.add_argument("--delete-extra", action="store_true",
                    help="automap mode: delete rows beyond the input length (hidden/unused fields) "
                         "using the - button, from the bottom up. Default: leave and report them")
    ap.add_argument("--always-plus", action="store_true",
                    help="add mode: click + for every row, even if blank rows already exist")
    ap.add_argument("--inspect", action="store_true",
                    help="open the page, dump row/dropdown HTML to inspect.txt, and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the pairs that would be mapped (after hidden filtering) and exit")
    args = ap.parse_args()

    pairs, stats = load_pairs(args.json_file)
    pairs, skipped = split_hidden(pairs, args.include_hidden)

    if args.include_common:
        common = [_pair(p, z) for p, z in COMMON_MAP]
        pairs = common + pairs

    if skipped:
        with SKIPPED_LOG.open("w", encoding="utf-8") as f:
            for p in skipped:
                f.write(f"{p['parameter_name']}\t{p['zoho_label']}\n")
        print(f"Skipped {len(skipped)} hidden field(s) — see {SKIPPED_LOG}. Use --include-hidden to map them.")
    if stats["pdf_only_skipped"]:
        print(f"Skipped {stats['pdf_only_skipped']} field(s) with no Zoho counterpart (pdf_only in the master).")

    pairs = pairs[args.start:]
    if args.limit:
        pairs = pairs[: args.limit]

    print(f"Ready to map {len(pairs)} row(s), starting at index {args.start}.")
    for i, p in enumerate(pairs[:10]):
        print(f"  {args.start + i}: {p['parameter_name']}  ->  {p['zoho_label'] or '(guess from name)'}")
    if len(pairs) > 10:
        print(f"  ... and {len(pairs) - 10} more")

    if args.dry_run:
        for i, p in enumerate(pairs):
            print(f"{args.start + i}\t{p['parameter_name']}\t{p['zoho_label'] or ''}\tcandidates={p['candidates']}")
        return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright is not installed. Run: python -m pip install playwright")

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            PROFILE_DIR, channel=BROWSER_CHANNEL, headless=False
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(args.url)

        input("Log in if needed, open the Webhooks configuration (Payload Mapping), then press Enter...")

        if args.inspect:
            inspect_page(page)
            ctx.close()
            return

        def process_row(index, row, pair):
            fill_left(row, pair["parameter_name"])
            used = select_right(page, row, pair["candidates"])
            print(f"[ok]   {index}: {pair['parameter_name']} -> {used}")

        def log_fail(index, pair, e):
            print(f"[FAIL] {index}: {pair['parameter_name']} -> {pair['zoho_label']} ({e})")
            with FAILED_LOG.open("a", encoding="utf-8") as f:
                f.write(f"{index}\t{pair['parameter_name']}\t{pair['zoho_label']}\t{e}\n")

        if args.mode == "automap":
            # --- Auto-Map mode: rows come from Zoho, sequence comes from us ---
            rows_now = page.locator(ROW).count()
            print(f"Rows on page before Auto-Map: {rows_now}")
            if click_automap(page):
                print("Clicked 'Auto-Map Fields'.")
            else:
                print("Could not click 'Auto-Map Fields' automatically.")
                input("Click 'Auto-Map Fields' at the top right of Payload Mapping yourself, then press Enter...")
            total_rows = page.locator(ROW).count()
            print(f"Rows on page after Auto-Map: {total_rows}, pairs to place: {len(pairs)}")
            if total_rows == 0:
                print("No rows found — check you are on the Payload Mapping page. Nothing was filled.")
                ctx.close()
                return

            for offset, pair in enumerate(pairs):
                index = args.start + offset
                try:
                    if index < page.locator(ROW).count():
                        row = page.locator(ROW).nth(index)
                    else:
                        # More pairs than Auto-Map rows: fall back to + for the overflow.
                        row = ensure_row(page, index, always_plus=True)
                    process_row(index, row, pair)
                except Exception as e:
                    log_fail(index, pair, e)

            # --- Extra rows: fields Auto-Map created that the input does not use
            # (hidden fields, other property types, system fields). They sit
            # after the last mapped row. Report them; delete only if asked. ---
            total_rows = page.locator(ROW).count()
            used_rows = args.start + len(pairs)
            if total_rows > used_rows:
                extras = []
                for idx in range(used_rows, total_rows):
                    extras.append((idx, read_right_text(page.locator(ROW).nth(idx))))
                with EXTRA_LOG.open("w", encoding="utf-8") as f:
                    for idx, txt in extras:
                        f.write(f"{idx}\t{txt}\n")
                print(f"{len(extras)} extra row(s) beyond the input (indexes {used_rows}-{total_rows - 1}) — listed in {EXTRA_LOG}.")
                if args.delete_extra:
                    # Delete from the bottom up so indexes do not shift.
                    for idx in range(total_rows - 1, used_rows - 1, -1):
                        if delete_row_at(page, idx):
                            print(f"[del]  {idx}: removed extra row")
                        else:
                            print(f"[del?] {idx}: could not remove — remove it manually before saving")
                else:
                    print("Leaving extra rows in place. Delete them in Zoho before saving, "
                          "or re-run with --delete-extra. (They would otherwise be sent with "
                          "their Auto-Map names.)")
        else:
            # --- Add mode: + for each row, then set both sides ---
            for offset, pair in enumerate(pairs):
                index = args.start + offset
                try:
                    row = ensure_row(page, index, args.always_plus)
                    process_row(index, row, pair)
                except Exception as e:
                    log_fail(index, pair, e)

        input("Review the page, SAVE the webhook manually, then press Enter to close...")
        ctx.close()


if __name__ == "__main__":
    main()
