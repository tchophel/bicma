"""Default "what is this category for" text shown to complainants. Administrators can edit each one on the Categories page;
these are only used to fill a category that has no text yet (matched on its name, ignoring case)."""

DEFAULT_DESCRIPTIONS = {
    "billing dispute": "A charge on your bill you do not agree with, a wrong amount, or a refund you were promised and have not received.",
    "breach of licence conditions": "A service provider or broadcaster not following the conditions of its BICMA licence.",
    "cable television": "Problems with your cable TV service: missing or poor channels, signal cut-offs, billing or installation by a cable operator.",
    "content": "Material that was broadcast or published and that harms you or others, such as false claims, abuse or privacy violations.",
    "data center services": "Problems with a data centre or hosting service: outages, security or contract and billing issues.",
    "emf radiation level measurement": "Request to check radiation levels (EMF) from a mobile tower or other radio equipment near your home, school or workplace.",
    "film classification": "A film's age rating or classification that you think is wrong, or a screening that does not follow its rating.",
    "film production-related": "Matters about film production permits, shooting or production companies that BICMA regulates.",
    "harmful or unlawful online content": "Online posts, pages or videos that are harmful, threatening or against the law, and that you want BICMA to look at.",
    "internet services": "Slow, unreliable or unavailable internet, wrong billing, or poor support from your internet service provider (ISP).",
    "journalist/media conduct": "A journalist or media house breaking the code of conduct, for example unfair, false or intrusive reporting.",
    "media fairness and conduct": "Unfair, biased or unethical behaviour by a media house or journalist.",
    "mobile network issues in rural areas": "Weak or no mobile signal, dropped calls or slow data in a village or rural area.",
    "mso's": "Problems with a multi-system operator (MSO) that delivers TV channels to your area: signal cut, channels removed or poor service.",
    "network coverage": "No signal, weak signal or poor indoor coverage where you live or work.",
    "network/coverage issues": "No signal, weak signal, dropped calls or slow data from a mobile operator.",
    "online reality show": "A complaint about an online reality show or talent hunt: its content, voting, prizes or how it was run.",
    "quality of service": "A telecom service that is below the standard you should get: slow speeds, frequent drops or long repair times.",
    "radio-frequency interference": "Radio signals disturbing your TV, radio, phone or other equipment, or a device interfering with a licensed service.",
    "regulated broadcast or published content": "Something broadcast or published by a regulated media organisation that you believe breaks the rules.",
    "requests for addition or removal of bts sites": "Ask for a new mobile tower (BTS site) in your area, or for an existing tower to be removed, with the reason.",
    "rural communication program": "Problems with a rural communication project, such as a community internet centre that is closed or not working.",
    "service interruption": "A telecom, internet or TV service that has stopped working or keeps cutting out.",
    "spectrum / apparatus licensing and type approval": "Questions or problems about radio spectrum licences, licensing of radio equipment, or approval of devices.",
    "tariff, service terms and potential market-abuse issues": "Price or package changes without notice, unfair service terms, or a provider abusing its market position.",
    "tariffs": "Prices, packages or charges that were changed without notice or that you think are unfair.",
    "telecom tower structure": "A mobile tower that is unsafe, badly built, too close to homes, or built without permission.",
    "unauthorised spectrum use": "Someone using radio frequencies without a licence, such as an illegal transmitter or jammer.",
}


def default_for(name):
    return DEFAULT_DESCRIPTIONS.get((name or "").strip().lower(), "")
