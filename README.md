# Zoho Webhook Mapper — Simple Guide for the Team

**No coding needed.** Just follow the steps in order.

---

## What does this tool do?

When we set up a webhook in Zoho Forms, we have to fill the **Payload Mapping** table — one row for every field. Doing this by hand takes a long time and it is easy to make mistakes.

This tool fills that table **automatically**:

- It writes the correct **Parameter Name** on the left side of each row.
- It selects the correct **field** in the dropdown on the right side.
- It fills the rows in the **correct MLS PDF order**, which is why we use it.
- The JSON file already contains the **standard fields**: **Property Type** and **Address** at the top, and **task_id, FormID, UniqueID, Date_Created, env, added_time, ip_address, house_id** and **live_key** at the bottom. If a JSON file is missing them, the tool adds them by itself — either way, they are mapped exactly once.

**The tool never clicks Save.** You always check the table yourself and click Save in Zoho. If something looks wrong, just don't save — nothing is changed permanently.

---

## What you need before you start

1. A **Windows** computer with **Google Chrome** installed.
2. **Python** installed. (If your computer does not have it, ask Shreyan — do not skip this.)
3. Access to the **Zoho Form** you are working on.
4. These two files from this GitHub repo, kept together in **one folder** (for example, a folder on your Desktop called `Webhook Mapper`):
   - `app.py` — the tool itself
   - The **JSON file for your form** — this is the list of fields for that MLS/form, for example `keys.json`

   ⚠️ **Use the JSON file made for your form only.** Every MLS/form has a different JSON file. If you are not sure which file to use, ask Shreyan before starting.

---

## One-time setup (only the first time on your computer)

1. Open the folder where you kept the files.
2. Click on the **address bar** at the top of the folder window, type `cmd` and press **Enter**. A black window (Command Prompt) will open.
3. Copy this line, paste it in the black window, and press **Enter**:

```
python -m pip install playwright
```

4. Wait till it finishes. You will see the word "Successfully installed". You never have to do this again on this computer.

**Quick check:** type `python --version` and press Enter. If you see something like `Python 3.12`, you are fine. If you see an error, ask Shreyan.

---

## Step-by-step: running the mapper

### Step 1 — Start from a clean mapping
Open your form in Zoho Forms and go to **Integrations → Webhooks → Payload Mapping**.
If old mapping rows are already there, **remove all of them first** (use the − button on each row). The tool works best from an empty table.

### Step 2 — Run a small test first (3 rows only)
In the black window, copy this line, paste it, and press **Enter**.
Replace the JSON file name and the link with your form's details:

```
python app.py keys.json --limit 3 --url PASTE_YOUR_FORM_LINK_HERE
```

- The part after `--url` is your form's **Integrate page link** (the same Zoho page link you normally open for the webhook).
- `--limit 3` means "do only 3 rows" — this is just a test.

### Step 3 — Log in and open the right page
Chrome will open by itself.

1. **Log in to Zoho** if it asks. (First time only — it remembers you after that.)
2. Open the form's **Integrations → Webhooks → Payload Mapping** page.
3. Go back to the black window and press **Enter**.

### Step 4 — Let the tool work
- The tool will click **Auto-Map Fields** by itself. If it cannot, it will ask you to click **Auto-Map Fields** (top right of the table) and then press Enter in the black window.
- It will then fill row by row. In the black window you will see lines like:

```
[ok]   0: General_Information_County -> County
[ok]   1: General_Information_List_Price -> List Price
```

- `[ok]` means that row is done. **Do not use the mouse or keyboard in Chrome while it is running.** Just wait.

### Step 5 — Check the test, then run the full file
- Look at the 3 rows in Zoho. The left name and the right dropdown should match what the black window showed.
- If the test looks correct, run the **full file** — same command, but **without** `--limit 3`:

```
python app.py keys.json --url PASTE_YOUR_FORM_LINK_HERE
```

- If Zoho asks / the page already has the test rows filled, remove all rows again first (Step 1) so the full run starts clean.

### Step 6 — Remove the extra rows
Zoho's Auto-Map creates a row for **every** field in the form, but our JSON file does not use all of them (for example, fields that belong to other property types). So after filling, there will be some **extra rows at the end**.

The tool will tell you how many extra rows there are and will save their names in a file called `extra_rows.txt`.

You have two choices:
- **Easy way:** delete the extra rows yourself in Zoho using the − button, starting from the **last row** and going up. Only delete the rows the tool listed.
- **Automatic way:** run the full command with `--delete-extra` at the end, and the tool will delete them for you:

```
python app.py keys.json --url PASTE_YOUR_FORM_LINK_HERE --delete-extra
```

### Step 7 — Check everything and Save
1. Scroll through the full table in Zoho and check a few rows from the start, middle and end.
2. If everything looks right, click **Save** in Zoho yourself.
3. Go back to the black window and press **Enter** to close the tool.

✅ **Done.**

---

## Files the tool creates — what they mean

| File | What it means |
|---|---|
| `failed_rows.txt` | Rows the tool could **not** fill. If this file has anything in it, those rows need to be filled by hand, or ask Shreyan. |
| `extra_rows.txt` | The extra Auto-Map rows at the end that are **not** in our list. Delete these in Zoho before saving (see Step 6). |
| `zoho_profile` (folder) | This folder remembers your Zoho login. **Do not delete it, do not share it with anyone.** It contains your login session. |

---

## Common problems and simple fixes

| Problem | What to do |
|---|---|
| `python is not recognized` | Python is not installed or not set up on this computer. Ask Shreyan. |
| `Playwright is not installed` | Do the **One-time setup** above, then try again. |
| Chrome does not open, or says the profile is in use | Close all Chrome windows opened by the tool, then run the command again. |
| Zoho asks you to log in every time | Always use the **same folder**. The login is saved in the `zoho_profile` folder inside it. |
| A row shows `[FAIL]` in the black window | Note the row number. Finish the run, then fill that row by hand in Zoho — or check `failed_rows.txt`. If many rows fail, stop and ask Shreyan. |
| The dropdown value looks wrong on some rows | Do **not** save. Note the row numbers and ask Shreyan. |
| The tool says there are fewer rows than fields | Make sure you clicked / allowed **Auto-Map Fields**, and that you removed old rows before starting. Then run again from Step 1. |
| You ran the tool on the wrong form or wrong JSON file | Do **not** save in Zoho. Just close the page — because you did not save, nothing is changed. Then start again with the correct file. |

---

## Rules to remember

1. **One form = one JSON file.** Never use another MLS's JSON file for your form.
2. **Always test with `--limit 3` first** when you use a new form or a new JSON file.
3. **Never click Save until you have checked** the start, middle and end of the table.
4. **Never share the `zoho_profile` folder.** It has your Zoho login in it.
5. **Do not edit the JSON file** unless Shreyan asks you to.
6. Work on a **copy/test webhook first** if you are doing a form type you have never done before.

---

## Making the JSON file for a new MLS (3-step prompt pack)

Every MLS needs its own JSON file. Create it in **Muse** (use Muse itself, like we do — not a random AI chat) using the 3 messages below, **in one single chat, one message at a time**. Do NOT use one single prompt for everything — that gives incomplete JSON. The steps work because the AI first lists the fields, then matches them, then generates.

You need two things:

1. **The MLS input sheet PDF(s)** — decides the **order** and **section names**.
2. **The Zoho form builder page PDF print** (open the form in the Zoho builder, print/save the full page as PDF) — decides the **exact field names**.

### Message 1 — attach the MLS PDF(s) only, and send this:

```
Read every page of the attached MLS input sheet PDF(s) carefully.
List EVERY section and EVERY field, in the exact order they appear on the PDF.
Fields only — do not list the options inside checkbox / radio / dropdown fields.
Number the fields continuously and give me the total count at the end.
Do not create any JSON yet. Just give me the list, section by section.
```

Read the reply. If pages or sections look missing, tell Muse which page to re-read before continuing.

### Message 2 — attach the Zoho builder PDF print, and send this:

```
Now read the attached Zoho form builder PDF print.
List EVERY field label exactly as written in the builder, in order.
Mark each field that has an orange/yellow eye icon next to it as [hidden].
Mark signature fields as [signature].
Give me the total count at the end. Do not create any JSON yet.
```

### Message 3 — send this (no new attachments):

```
Now create the webhook mapping JSON from the two lists you just made.

Rules:
1. Order and section names come from the MLS list (Message 1). Go field by field in that exact order.
2. For each MLS field, use the matching field's EXACT label from the builder list (Message 2) as "zoho_label". If the wording is slightly different but it is clearly the same field, still match it.
3. "parameter_name" format: <Section>_<FieldName> in Title_Case_With_Underscores, for example General_Information_County. Keep the field's wording. Remove special characters. "#" becomes "Number". "Y/N" becomes "YN". Fractions in words (1/2 = Half, 1/4 = One_Quarter, 3/4 = Three_Quarter). Roman numerals become normal numbers (II = 2).
4. Skip a field only if it has no matching field in the builder list, or it is a signature field or the date-time field below a signature.
5. HIDDEN FIELDS: hidden fields are mapped like normal fields, at their PDF position. Do not skip a field because it is hidden. (Exception: the standard fields in rule 9.)
6. Never repeat a "parameter_name" or a "zoho_label". If two fields would get the same name, add a meaningful word (Details, Type, Features, Information). Never use _1, _2.
7. If the same MLS field is a different builder field per property type, include EACH type's version at that position. Example: "Property Sub Type" = Home Type (Residential), Multi-Family Sub-Type (Multi-Family), Land Sub-Type (Land).
8. LISTING DATES: "List Date" and "Expire Date" are called "Listing Date" and "Plan End Date" (parameter names end _Listing_Date / _Plan_End_Date), and ALWAYS add "Listing Term" (parameter _Listing_Term) between them.
9. STANDARD FIELDS: at the very top add "Property Type" (zoho_label "Property Type"), then "Address" (zoho_label "Address"). At the very bottom add, in this order: task_id, FormID (zoho_label "Unique ID"), UniqueID (zoho_label "Unique ID"), Date_Created (zoho_label "Date-Time"), env, added_time (zoho_label "Added Time"), ip_address (zoho_label "IP Address"), house_id, live_key. FormID and UniqueID both using "Unique ID" is the one allowed duplicate label.
10. CONVENIENCE RADIOS: if the builder list has a Yes/No radio that is NOT in the MLS list and other fields depend on it (example: a "Fireplace" radio above the fireplace detail fields), include it right before the first field that depends on it. ONLY if such a radio actually exists in the builder list — never invent one.
11. If I gave more than one property type, make ONE merged list: Residential order is the main order; fields unique to other types go right after the nearest related field.
12. Tables in the PDF (Rooms, Units) that Zoho implements with generic repeating fields: include those generic builder fields once, at the table's position.

13. OTHER ROOMS: the Zoho form has team-added "Other Room" fields that are NOT in the MLS PDF (Other Room 1, Other Room 2, and so on), and each one has Name, Dimensions and Level fields in the builder list. Include all of them — the room field itself first, then its Name, Dimensions and Level — placed immediately after the LAST field of the Rooms section.
Before you output, check yourself:
- First two entries are Property Type and Address; last entry is live_key.
- Listing Date, Listing Term, Plan End Date are together, in that order.
- No duplicate parameter names; no duplicate labels except Unique ID twice.
- Count your entries and tell me the count in one line BEFORE the JSON.

Output format: one line with the total count, then ONLY a JSON array like this — no explanation after it:
[
  {"parameter_name": "General_Information_County", "zoho_label": "County"},
  {"parameter_name": "General_Information_List_Price", "zoho_label": "List Price"}
]
If the JSON is too long for one reply, give it in parts, section by section, and I will say "continue" — do not skip or summarise any field.
```

### After you get the JSON

1. Copy the full JSON and save it as a `.json` file in the same folder as the tool.
2. Run the mapper with `--dry-run` on it — the count should match the count Muse claimed.
3. Always test with `--limit 3` first (Step 2 above), and spot-check the start, the listing trio, one radio group (like Fireplace) and the bottom standard block before the full run.

---

## When to ask Shreyan

- Python or setup errors you cannot fix with the table above.
- Many `[FAIL]` rows, or dropdowns selecting the wrong field again and again.
- You need a JSON file for a new MLS or a new form.
- The tool asks you to run something with `--inspect` — run it if he asks, and send him the `inspect.txt` file it creates.

---

*Short version: Clean table → run command with `--limit 3` → log in → press Enter → check → run full command → delete extra rows → check → Save in Zoho yourself.*
