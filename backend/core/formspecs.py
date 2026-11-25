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


def _ops(key, label, req=False, **kw):
    """Tick-boxes drawn from the Providers in master data (Telecom operator type)."""
    return {"key": key, "label": label, "type": "provider_checks", "required": req, "provider_type": "Telecom operator", **kw}


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
    "Other conduct-related complaint (Specify)",
]
OTHER_CONDUCT = "Other conduct-related complaint (Specify)"
OTHER_OPTION = "Other (specify)"
REMEDIES = ["Removal of the content", "Correction or clarification", "Public apology", "Right of reply", "Warning to the content creator / publisher", OTHER_SPECIFY]
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
VOTING_OTHER = {"all": [VOTING, {"key": "voting_method", "includes": OTHER_OPTION}]}
PRIZE = {"key": "nature", "equals": "Non-payment of prizes"}

# (division, keywords, name shown in admin, fields, documents, description label/required or None)
SPECS = [
    # ---- STD
    ("std", ["interference"], [_t("frequency", "Specific frequency / frequency range", True), _prov("company", "Concerned company (optional)")], [], True),
    ("std", ["unauthori"], [_t("frequency", "Specific frequency / frequency range", True), _prov("company", "Concerned company (optional)")], [], True),
    ("std", ["network"], [_ops("operator", "Concerned telecom operator", True)], [], True),
    ("std", ["bts"], [
        {"key": "request_type", "label": "Type of request", "type": "select", "required": True, "options": ["Addition of a BTS site", "Removal of a BTS site"]},
        _ops("operator", "Telecom operator", True)],
     [_doc("tower_photo", "Photo of the concerned tower (mandatory for removal)", "when", when={"key": "request_type", "equals": "Removal of a BTS site"}, image=True, hint="A clear photo of the tower you want removed (JPG or PNG).")], True),
    ("std", ["emf"], [_ops("operator", "Concerned telecom operator (optional)")], [_doc("photo", "Supporting document (photo, optional)", False, image=True, hint="Photos of the measurement reading, the equipment or the site, and any measurement report (PDF).")], True),
    ("std", ["tower"], [_ops("operator", "Concerned telecom operator", True)], [_doc("photo", "Supporting document (photo)", True, image=True, hint="A clear photo of the concerned tower (JPG or PNG).")], True),
    # ---- IID
    ("iid", ["internet"], [_prov("isp", "Name of ISP", True), _t("customer_id", "Customer service identification number provided by the ISP", True)], [], True),
    ("iid", ["cable"], [_prov("cable_provider", "Name of cable service provider", True, provider_type="Cable TV operator")], [], True),
    ("iid", ["rural", "communication"], [_prov("operator", "Concerned telecom operator (can be both)", True)], [], True),
    ("iid", ["data", "cent"], [_prov("operator", "Concerned data center operators", True), _t("operator_contact", "Contact number of operators")], [], True),
    ("iid", ["tariff"], [_prov("provider", "Name of the concerned service provider", True)], [], True),
    ("iid", ["coverage", "rural"], [_prov("operator", "Specify the telecom operator", True)], [], True),
    ("iid", ["network", "rural"], [_prov("operator", "Specify the telecom operator", True)], [], True),
    ("iid", ["mso"], [_prov("mso", "Concerned MSO", True)], [], True),
    # ---- MCD
    ("mcd", ["journalist"], [
        _t("journalist", "Name of journalist / entity complained against", True), _t("media_org", "Media organization", True), _t("designation", "Designation"),
        {"key": "misconduct_date", "label": "Date of the alleged misconduct", "type": "date", "required": True, "past": True},
        {"key": "misconduct", "label": "Nature of alleged misconduct", "type": "checks", "required": True, "options": MISCONDUCT},
        _t("misconduct_other", "Please specify", True, when={"key": "misconduct", "includes": OTHER_CONDUCT})],
     [_doc("evidence", "Evidence to support your allegation")], True),
    ("mcd", ["content"], [
        _t("title", "Title of the post, article or video published", True), _t("creator", "Name of content creator / publisher", True),
        {"key": "nature", "label": "Nature of complaint", "type": "checks", "required": True, "options": CONTENT_NATURE},
        _t("nature_other", "Please specify", True, when={"key": "nature", "includes": OTHER_SPECIFY}),
        {"key": "published_on", "label": "Date of publication", "type": "date", "required": True, "past": True},
        _t("medium", "Medium where the post / article / video was published", True), _t("link", "Post / article / video link, if published online"),
        {"key": "language", "label": "Language of the content", "type": "select", "required": True, "options": LANGUAGES},
        {"key": "previous", "label": "Have you already raised this complaint with the content creator / publisher? (Yes/No)", "type": "yesno", "required": True, "options": YES_NO},
        {"key": "response", "label": "Response received", "type": "textarea", "required": False, "when": {"key": "previous", "equals": "Yes"}},
        {"key": "remedy", "label": "Remedy sought", "type": "checks", "required": True, "options": REMEDIES},
        _t("remedy_other", "Please specify", True, when={"key": "remedy", "includes": OTHER_SPECIFY})],
     [_doc("published_copy", "Supporting documents", True,
           required_hint="A copy of the published material: a screenshot, photo, recording, printout or file of the post, article or video you are complaining about.",
           optional_hint="Correspondence with the content creator / publisher, or a statement of objection, if available.",
           also=[{"key": "supporting", "label": "Correspondence with the content creator / publisher, or a statement of objection"}])], True),
    ("mcd", ["reality"], [
        _t("show", "Name of reality show", True), _t("organisers", "Name of the organiser(s)", True),
        {"key": "nature", "label": "Nature of complaint", "type": "select", "required": True, "options": ["Voting procedures", "Non-payment of prizes"]},
        {"key": "voting_method", "label": "Voting method", "type": "checks", "required": True, "options": ["Online voting", "SMS voting", "Paid voting", OTHER_OPTION], "when": VOTING},
        _t("voting_method_other", "Please specify the voting method", True, when=VOTING_OTHER),
        {"key": "voting_start", "label": "Voting period: start date", "type": "date", "required": True, "when": VOTING},
        {"key": "voting_end", "label": "Voting period: end date", "type": "date", "required": True, "when": VOTING},
        {"key": "voting_details", "label": "Details of the complaint", "type": "textarea", "required": True, "when": VOTING},
        _t("actual_prize", "Actual prize received", True, when=PRIZE), _t("announced_prize", "Announced prize", True, when=PRIZE),
        {"key": "winner_date", "label": "Date declared winner", "type": "date", "required": True, "past": True, "when": PRIZE},
        {"key": "previous", "label": "Have you already raised this complaint with the organiser? (Yes/No)", "type": "yesno", "required": True, "options": YES_NO},
        {"key": "response", "label": "Response received", "type": "textarea", "required": False, "when": {"key": "previous", "equals": "Yes"}}],
     [_doc("supporting", "Supporting documents", False, when=VOTING,
           hint="Voting screenshots, voting receipts, transaction records or other evidence, and any correspondence with the organiser.",
           also=[{"key": "voting_evidence", "label": "Evidence of voting"}, {"key": "correspondence", "label": "Correspondence with the organiser"}]),
      _doc("supporting", "Supporting documents", False, when=PRIZE,
           hint="A copy of the agreement; the announcement, programme recording or winner notification; and any correspondence with the organiser.",
           also=[{"key": "agreement", "label": "A copy of the agreement"},
                 {"key": "announcement", "label": "Announcement, programme recording, or winner notification"},
                 {"key": "correspondence", "label": "Correspondence with the organiser, if received"}])], False),
    ("mcd", ["film", "production"], [
        _t("film", "Name of the film", True), _t("company", "Name of the Production Company/Producer(s)", True), _t("role", "Role in Production", True),
        _t("agreed_payment", "Agreed payment", True), _t("amount_received", "Payment received", True)],
     [_doc("contract", "Contract or agreement, if any"), _doc("receipts", "Payment receipts or bank transaction records"),
      _doc("other_evidence", "Any other evidence supporting the claim")], False),
]
# Categories to create under each division when they are missing (existing categories are never changed or removed).
CATEGORIES = {
    "std": ["Radio-frequency interference", "Unauthorised spectrum use", "Network/Coverage issues", "Requests for addition or removal of BTS sites",
            "EMF radiation level measurement", "Telecom tower structure"],
    "iid": ["Internet Services", "Cable Television", "Rural communication program", "Data Center Services",
            "Tariff, service terms and potential market-abuse issues", "Mobile network issues in Rural areas", "MSO's"],
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
    d, words, fields, docs, has_description = best
    if d == "mcd" and "reality" in words:
        fields = _with_reality_shows(fields)
    geo = d == "std" or (d == "iid" and "rural" in words and ("coverage" in words or "network" in words))
    extra = [dict(x) for x in docs]
    if d in ("std", "iid"):
        # One upload box per form. A required (or required-when) document of the category replaces the general box, because
        # the server checks it by name; an optional one is folded into the general box, which then says what to upload.
        required = [x for x in extra if x.get("required") is True]
        if required:
            docs = required
        else:
            general = dict(GENERAL_DOC)
            hints = [x["hint"] for x in extra if x.get("hint") and not x.get("required")]
            if hints:
                general["hint"] = hints[0]
            # a document that is only required in some cases (e.g. the tower photo for a removal request) stays beside it
            docs = [general] + [x for x in extra if x.get("required") == "when"]
    else:
        docs = extra
    docs = _merge_plain_docs(docs)
    return {"division": d, "identity": IDENTITY[d], "fields": fields, "docs": docs, "geo": geo,
            "description": {"label": DESCRIPTION[d], "required": True} if has_description else None}


def _lower_first(text):
    return text[0].lower() + text[1:] if text[1:2].islower() else text


def what_to_upload(labels):
    """"Contract or agreement, if any; payment receipts or bank transaction records." from a list of document names."""
    text = "; ".join(_lower_first(x) for x in labels)
    return (text[0].upper() + text[1:] + ".") if text else ""


def _merge_plain_docs(docs):
    """Several always-shown, optional documents become one upload box that lists what to upload. Documents that depend on an
    answer (`when`) or are required stay as they are (a category that wants one box per answer lists it itself, with `also`
    naming the old keys). The merged box remembers the old keys so earlier uploads keep their labels."""
    plain = [x for x in docs if not x.get("when") and not x.get("required") and x["key"] != GENERAL_DOC["key"]]
    if len(plain) < 2:
        return docs
    merged = {"key": "supporting", "label": "Supporting documents", "required": False, "hint": what_to_upload([x["label"] for x in plain]),
              "also": [{"key": x["key"], "label": x["label"]} for x in plain]}
    out, placed = [], False
    for x in docs:
        if x in plain:
            if not placed:
                out.append(merged); placed = True
        else:
            out.append(x)
    return out


def _holds(w, details):
    if "all" in w:  # every listed condition must hold
        return all(_holds(x, details) for x in w["all"])
    cur = details.get(w["key"])
    if "equals" in w:
        return cur == w["equals"]
    return isinstance(cur, list) and w["includes"] in cur


def reality_shows():
    """The reality shows an administrator listed under Settings (one per line)."""
    from core.models import SystemConfiguration
    raw = SystemConfiguration.get("reality_shows", "") or ""
    return list(dict.fromkeys(x.strip() for x in raw.splitlines() if x.strip()))[:200]


def _with_reality_shows(fields):
    """"Name of reality show" becomes a list to pick from (plus "Other (specify)"), when shows are listed in Settings."""
    import copy
    shows = reality_shows()
    if not shows:
        return fields
    fields = copy.deepcopy(fields)
    for i, f in enumerate(fields):
        if f["key"] == "show":
            fields[i] = {"key": "show", "label": "Name of reality show", "type": "select", "required": True, "options": shows + [OTHER_OPTION]}
            fields.insert(i + 1, _t("show_other", "Please specify the name of the reality show", True, when={"key": "show", "equals": OTHER_OPTION}))
            break
    return fields


def visible(item, details):
    w = item.get("when")
    return True if not w else _holds(w, details)


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
            errors[f"details.{f['key']}"] = "Select at least one option." if f["type"] in ("checks", "provider_checks") else "This field is required."
            continue
        if empty:
            continue
        if f["type"] == "checks" and (not isinstance(val, list) or any(v not in f["options"] for v in val)):
            errors[f"details.{f['key']}"] = "Choose from the listed options."
        elif f["type"] == "provider_checks":
            from core.models import Provider
            allowed = set(Provider.objects.filter(is_active=True).values_list("name", flat=True))
            if not isinstance(val, list) or any(v not in allowed for v in val):
                errors[f"details.{f['key']}"] = "Choose from the listed operators."
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
        for old in dct.get("also", []):
            if old["key"] == key:
                return old["label"]
    return key


# ---- Questions an Administrator adds in the form builder (core.FormQuestion), on top of the fixed ones above ----

def custom_fields_for(category):
    """The active custom questions for a category: those of its division that apply to every category, plus its own."""
    from django.db.models import Q
    from core.models import FormQuestion
    if category is None or not category.default_division_id:
        return []
    qs = (FormQuestion.objects.filter(is_active=True, division_id=category.default_division_id).filter(Q(category__isnull=True) | Q(category_id=category.pk))
          .order_by("position", "created_at"))
    out = []
    for q in qs:
        item = {"key": q.key, "label": q.label, "type": q.kind, "required": q.required}
        if q.kind in ("select", "checks"):
            item["options"] = list(q.options or [])
        elif q.kind == "yesno":
            item["options"] = YES_NO
        if q.hint:
            item["hint"] = q.hint
        out.append(item)
    return out


def validate_custom(category, details):
    """{field: message} for the custom questions (same rules as the fixed ones)."""
    fields = custom_fields_for(category)
    return validate({"fields": fields, "docs": []}, details, set()) if fields else {}


def label_custom(category, details):
    fields = custom_fields_for(category)
    return label_details({"fields": fields}, details) if fields else []
