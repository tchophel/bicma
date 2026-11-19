"""Complaint forms defined as data: one common identity block per division plus the specific questions per category.

The same definition is sent to the complaint form (which draws itself from it) and used by the server to validate the
answers, so the two cannot drift apart. A category gets a form when its name contains every keyword of a spec in its
division; categories with no match keep the generic form.

Field types: text, textarea, date, select, yesno, checks, provider (free text with suggestions from the provider list).
`when` shows a field or document only in some cases: {"key": k, "equals": v} or {"key": k, "includes": v}.
"""
import datetime as dt

OTHER_SPECIFY = "Others (Specify)"

SELF_OTHERS_STD = [["self", "Self"], ["agency", "Agency"], ["institute", "Institute"], ["ministry", "Ministry"], ["others", "Others"]]
SELF_OTHERS_MCD = [["self", "For myself"], ["individual", "On behalf of another individual"], ["organisation", "On behalf of an organisation / institution"]]

IDENTITY = {
    "std": {"location": True, "present_address": False, "complaining_for": SELF_OTHERS_STD, "other_party_label": "Name of other concerned party"},
    "iid": {"location": True, "present_address": False, "complaining_for": None, "other_party_label": ""},
    "mcd": {"location": False, "present_address": True, "complaining_for": SELF_OTHERS_MCD, "other_party_label": "Name of the individual or organisation"},
}
DESCRIPTION = {"std": "Detailed description of the complaint", "iid": "Detailed description of the complaint", "mcd": "Brief description"}
GENERAL_DOC = {"key": "supporting", "label": "Supporting documents (photos, PDF, etc.)", "required": False}


def _t(key, label, req=False, **kw):
    return {"key": key, "label": label, "type": "text", "required": req, **kw}


def _prov(key, label, req=False, **kw):
    return {"key": key, "label": label, "type": "provider", "required": req, **kw}


def _doc(key, label, req=False, **kw):
    return {"key": key, "label": label, "required": req, **kw}


YES_NO = ["Yes", "No"]
MISCONDUCT = [
    "Failure to provide an opportunity to respond",
    "Harassment, threats or intimidation by a journalist",
    "Recording conversations or taking photographs/videos without consent",
    "Entering private property or invading personal privacy without permission",
    "Misuse of press identity cards, accreditation or professional privileges",
    "Accepting money, gifts or favours to influence news coverage",
    "Misuse of professional position or information for personal benefit",
    "Interviewing children below 16 years without parental/guardian consent or presence",
    "Disrespectful or insensitive behaviour during interviews or interactions",
    "Disclosure of confidential news sources without proper justification",
    "Unprofessional behaviour towards fellow journalists or media professionals",
    "Other conduct-related complaint",
]
CONTENT_NATURE = [
    "National Security, Sovereignty, or Unity: content threatening the Tsa-Wa-Sum, national security, or communal harmony",
    "Cultural & Religious Sensitivity: content disrespecting Bhutanese culture, traditions, religious figures, or sacred sites",
    "Self-Harm & Dangerous Challenges",
    "Sexually explicit or pornographic content",
    "Content involving violence or graphic material",
    "Content involving children or child protection concerns",
    "Misleading or false information",
    "Defamatory or offensive content",
    "Inaccurate or Unbalanced Reporting",
    "Obscene or Indecent Content",
    "Incitement to Violence or Illegal Activities",
    "Impersonation & Fake Accounts",
    OTHER_SPECIFY,
]
LANGUAGES = ["Dzongkha", "English", "Tshangla (Sharchopkha)", "Lhotshamkha", "Other"]
VOTING = {"key": "nature", "equals": "Voting procedures"}
PRIZE = {"key": "nature", "equals": "Non-payment of prizes"}

# (division, keywords, name shown in admin, fields, documents, description label/required or None)
SPECS = [
    # ---- STD
    ("std", ["interference"], [_t("frequency", "Specific frequency / frequency range", True), _prov("company", "Concerned company (optional)")], [], True),
    ("std", ["unauthori"], [_t("frequency", "Specific frequency / frequency range", True), _prov("company", "Concerned company (optional)")], [], True),
    ("std", ["network"], [_prov("operator", "Concerned telecom operator", True)], [], True),
    ("std", ["bts"], [
        {"key": "request_type", "label": "Type of request", "type": "select", "required": True, "options": ["Addition of a BTS site", "Removal of a BTS site"]},
        _prov("operator", "Telecom operator", True)],
     [_doc("tower_photo", "Photo of the concerned tower (mandatory for removal)", "when", when={"key": "request_type", "equals": "Removal of a BTS site"}, image=True)], True),
    ("std", ["emf"], [_prov("operator", "Concerned telecom operator (optional)")], [_doc("photo", "Supporting document (photo, optional)", False, image=True)], True),
    ("std", ["tower"], [_prov("operator", "Concerned telecom operator", True)], [_doc("photo", "Supporting document (photo)", True, image=True)], True),
    # ---- IID
    ("iid", ["internet"], [_prov("isp", "Concerned ISP", True), _t("isp_contact", "Contact number of ISP")], [], True),
    ("iid", ["cable"], [_prov("cable_provider", "Name of cable service provider", True)], [], True),
    ("iid", ["rural", "communication"], [_prov("operator", "Concerned telecom operator (can be both)", True)], [], True),
    ("iid", ["data", "cent"], [_prov("operator", "Concerned data center operator", True), _t("operator_contact", "Contact number of operator")], [], True),
    ("iid", ["tariff"], [_prov("provider", "Name of the concerned service provider", True)], [], True),
    ("iid", ["coverage", "rural"], [_prov("operator", "Concerned telecom operator", True)], [], True),
    ("iid", ["mso"], [_prov("mso", "Concerned MSO", True)], [], True),
    # ---- MCD
    ("mcd", ["journalist"], [
        _t("journalist", "Name of journalist / entity complained against", True), _t("media_org", "Media organization", True), _t("designation", "Designation"),
        {"key": "misconduct_date", "label": "Date of the alleged misconduct", "type": "date", "required": True, "past": True},
        {"key": "misconduct", "label": "Nature of alleged misconduct", "type": "checks", "required": True, "options": MISCONDUCT}],
     [_doc("evidence", "Evidence to support your allegation")], True),
    ("mcd", ["content"], [
        _t("title", "Title of the post, article or video published", True), _t("creator", "Name of content creator / publisher", True),
        {"key": "nature", "label": "Nature of complaint", "type": "checks", "required": True, "options": CONTENT_NATURE},
        _t("nature_other", "Please specify", True, when={"key": "nature", "includes": OTHER_SPECIFY}),
        {"key": "published_on", "label": "Date of publication", "type": "date", "required": True, "past": True},
        _t("medium", "Medium where the post / article / video was published", True), _t("link", "Post / article / video link, if published online"),
        {"key": "language", "label": "Language of the content", "type": "select", "required": True, "options": LANGUAGES},
        {"key": "remedy", "label": "Remedy sought", "type": "textarea", "required": True}],
     [_doc("correspondence", "Correspondence with the concerned person or the media house, if received"),
      _doc("published_copy", "A copy of the published material that may support your statement"), _doc("objection", "Statement of objection")], True),
    ("mcd", ["reality"], [
        _t("show", "Name of reality show", True), _t("organisers", "Name of the organiser(s)", True),
        {"key": "nature", "label": "Nature of complaint", "type": "select", "required": True, "options": ["Voting procedures", "Non-payment of prizes"]},
        {"key": "voting_method", "label": "Voting method", "type": "select", "required": True, "options": ["Online voting", "SMS voting", "Paid voting", "Other"], "when": VOTING},
        {"key": "voting_start", "label": "Voting period: start date", "type": "date", "required": True, "when": VOTING},
        {"key": "voting_end", "label": "Voting period: end date", "type": "date", "required": True, "when": VOTING},
        {"key": "voting_details", "label": "Details of the complaint", "type": "textarea", "required": True, "when": VOTING},
        _t("actual_prize", "Actual prize received", True, when=PRIZE), _t("announced_prize", "Announced prize", True, when=PRIZE),
        {"key": "winner_date", "label": "Date declared winner", "type": "date", "required": True, "past": True, "when": PRIZE},
        {"key": "previous", "label": "Previous complaint to the organiser?", "type": "yesno", "required": True, "options": YES_NO},
        {"key": "response", "label": "Response received", "type": "textarea", "required": False, "when": {"key": "previous", "equals": "Yes"}}],
     [_doc("voting_evidence", "Evidence of voting (screenshots, voting receipts, transaction records or other documents)", False, when=VOTING),
      _doc("agreement", "A copy of the agreement", False, when=PRIZE),
      _doc("announcement", "Announcement, programme recording, or winner notification", False, when=PRIZE),
      _doc("correspondence", "Correspondence with the organiser, if received")], False),
    ("mcd", ["film", "production"], [
        _t("film", "Name of the film", True), _t("company", "Name of the production company / producer(s)", True), _t("role", "Role in production", True),
        _t("agreed_payment", "Agreed payment", True), _t("amount_received", "Amount received", True)],
     [_doc("contract", "Contract or agreement, if any"), _doc("receipts", "Payment receipts or bank transaction records"),
      _doc("other_evidence", "Any other evidence supporting the claim")], False),
]
# Categories to create under each division when they are missing (existing categories are never changed or removed).
CATEGORIES = {
    "std": ["Radio-frequency interference", "Unauthorised spectrum use", "Network/Coverage issues", "Requests for addition or removal of BTS sites",
            "EMF radiation level measurement", "Telecom tower structure"],
    "iid": ["Internet Services", "Cable Television", "Rural communication program", "Data Center Services",
            "Tariff, service terms and potential market-abuse issues", "Coverage issues in Rural areas", "MSO's"],
    "mcd": ["Journalist/Media Conduct", "Content", "Online Reality Show", "Film Production-related"],
}


def division_key(division):
    n = (getattr(division, "name", "") or "").lower()
    return "std" if n.startswith("spectrum") else "iid" if n.startswith("infocomm") else "mcd" if n.startswith("media") else ""


def spec_for(category):
    """The resolved form for a category, or None when it keeps the generic form."""
    if category is None or not category.default_division_id:
        return None
    div = division_key(category.default_division)
    name = category.name.lower()
    best = None
    for d, words, fields, docs, has_description in SPECS:
        if d == div and all(w in name for w in words) and (best is None or len(words) > len(best[1])):
            best = (d, words, fields, docs, has_description)
    if best is None:
        return None
    d, _, fields, docs, has_description = best
    docs = ([GENERAL_DOC] if d in ("std", "iid") else []) + [dict(x) for x in docs]
    return {"division": d, "identity": IDENTITY[d], "fields": fields, "docs": docs,
            "description": {"label": DESCRIPTION[d], "required": True} if has_description else None}


def visible(item, details):
    w = item.get("when")
    if not w:
        return True
    cur = details.get(w["key"])
    if "equals" in w:
        return cur == w["equals"]
    return isinstance(cur, list) and w["includes"] in cur


def validate(spec, details, present_slots, today=None):
    """Return {field: message} for the category-specific answers and required documents."""
    today = today or dt.date.today()
    errors = {}
    details = details if isinstance(details, dict) else {}
    for f in spec["fields"]:
        if not visible(f, details):
            continue
        val = details.get(f["key"])
        empty = val in (None, "", []) or (isinstance(val, str) and not val.strip())
        if f["required"] and empty:
            errors[f"details.{f['key']}"] = "Select at least one option." if f["type"] == "checks" else "This field is required."
            continue
        if empty:
            continue
        if f["type"] == "checks" and (not isinstance(val, list) or any(v not in f["options"] for v in val)):
            errors[f"details.{f['key']}"] = "Choose from the listed options."
        elif f["type"] in ("select", "yesno") and val not in f["options"]:
            errors[f"details.{f['key']}"] = "Choose one of the listed options."
        elif f["type"] == "date":
            try:
                d = dt.date.fromisoformat(str(val))
                if f.get("past") and d > today:
                    errors[f"details.{f['key']}"] = "The date cannot be in the future."
            except ValueError:
                errors[f"details.{f['key']}"] = "Enter a valid date."
        elif f["type"] in ("text", "provider", "textarea") and (not isinstance(val, str) or len(val) > 2000):
            errors[f"details.{f['key']}"] = "Enter at most 2,000 characters."
    for dct in spec["docs"]:
        if not visible(dct, details):
            continue
        required = dct["required"] is True or dct["required"] == "when"
        if required and dct["key"] not in present_slots:
            errors[f"doc__{dct['key']}"] = f"Attach: {dct['label']}."
    return errors


def label_details(spec, details):
    """[(label, text)] for the answers a case officer reads."""
    out = []
    for f in spec["fields"]:
        v = (details or {}).get(f["key"])
        if v in (None, "", []) or not visible(f, details or {}):
            continue
        out.append({"label": f["label"], "value": "; ".join(v) if isinstance(v, list) else str(v)})
    return out


def slot_label(spec, key):
    for dct in (spec or {}).get("docs", []):
        if dct["key"] == key:
            return dct["label"]
    return key
