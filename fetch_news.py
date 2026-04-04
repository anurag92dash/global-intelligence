#!/usr/bin/env python3
"""
Global Intelligence — Brain v2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
What this script does, step by step:

1.  FETCH   — pulls from RSS feeds + optional NewsAPI
2.  FILTER  — drops noise (sports, celebrity, weather)
3.  SCORE   — gives each story an importance score (0-100)
              based on: source authority, multi-source coverage,
              geopolitical weight, conflict relevance
4.  RANK    — keeps only top-N stories per region+category bucket
5.  CONFLICT — auto-detects which situation each story belongs to,
               updates status signals (escalating/stable/de-escalating)
6.  SAVE    — writes news_data.json + conflicts_data.json
"""

import json, os, re, hashlib
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
import feedparser


# ──────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────

TOP_N_PER_BUCKET = 8   # max stories per (region, category) pair

SOURCE_AUTHORITY = {
    "Reuters": 95, "AP News": 93, "BBC News": 90,
    "Financial Times": 88, "Bloomberg": 87, "The Economist": 86,
    "Wall Street Journal": 85, "New York Times": 84, "Washington Post": 83,
    "The Guardian": 80, "Al Jazeera": 78, "Nikkei Asia": 76,
    "Euronews": 70, "Politico": 72, "DW News": 70, "France 24": 70,
}

RSS_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",        "source": "BBC News",        "region": "EU",   "default_cat": "geopolitics"},
    {"url": "https://feeds.reuters.com/reuters/topNews",           "source": "Reuters",         "region": "NA",   "default_cat": "geopolitics"},
    {"url": "https://apnews.com/rss",                              "source": "AP News",         "region": "NA",   "default_cat": "geopolitics"},
    {"url": "https://www.theguardian.com/world/rss",               "source": "The Guardian",    "region": "EU",   "default_cat": "geopolitics"},
    {"url": "https://feeds.bbci.co.uk/news/world/europe/rss.xml", "source": "BBC News",        "region": "EU",   "default_cat": "politics"},
    {"url": "https://www.euronews.com/rss",                        "source": "Euronews",        "region": "EU",   "default_cat": "politics"},
    {"url": "https://www.dw.com/en/rss",                           "source": "DW News",         "region": "EU",   "default_cat": "politics"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml", "source": "New York Times",  "region": "NA",   "default_cat": "politics"},
    {"url": "https://feeds.washingtonpost.com/rss/politics",       "source": "Washington Post", "region": "NA",   "default_cat": "politics"},
    {"url": "https://www.politico.com/rss/politics08.xml",         "source": "Politico",        "region": "NA",   "default_cat": "politics"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml",           "source": "Al Jazeera",      "region": "MENA", "default_cat": "geopolitics"},
    {"url": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml","source":"BBC News",      "region": "MENA", "default_cat": "geopolitics"},
    {"url": "https://feeds.bbci.co.uk/news/world/asia/rss.xml",   "source": "BBC News",        "region": "APJ",  "default_cat": "geopolitics"},
    {"url": "https://asia.nikkei.com/rss/feed/nar",                "source": "Nikkei Asia",     "region": "APJ",  "default_cat": "business"},
    {"url": "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml","source":"BBC News",    "region": "SA",   "default_cat": "politics"},
    {"url": "https://www.ft.com/?format=rss",                      "source": "Financial Times", "region": "EU",   "default_cat": "business"},
    {"url": "https://feeds.bloomberg.com/markets/news.rss",        "source": "Bloomberg",       "region": "NA",   "default_cat": "business"},
    {"url": "https://www.economist.com/business/rss.xml",          "source": "The Economist",   "region": "EU",   "default_cat": "business"},
    {"url": "https://www.wsj.com/xml/rss/3_7085.xml",              "source": "Wall Street Journal","region":"NA", "default_cat": "business"},
]

NOISE = [
    "celebrity","nfl","nba","cricket match","football score","olympic",
    "entertainment","film review","box office","recipe","travel guide",
    "horoscope","fashion","lifestyle","weather forecast","sports result",
    "award show","grammy","oscar","emmy","concert","album","spotify",
]

POLITICAL_KEYWORDS = [
    "election","vote","parliament","minister","president","government",
    "congress","senate","prime minister","chancellor","coalition","policy",
    "legislation","bill","constitution","protest","opposition","resign",
    "diplomacy","treaty","summit","NATO","G7","G20","referendum","ballot",
]

GEOPOLITICAL_KEYWORDS = [
    "war","conflict","military","troops","invasion","ceasefire","peace talks",
    "tension","missile","nuclear","drone","airstrike","territory","border",
    "alliance","geopolit","sanctions","coup","crisis","uprising",
    "China","Russia","Iran","Ukraine","Israel","Gaza","Taiwan","Kashmir",
    "embargo","weapon","offensive","defense","intelligence","espionage","regime",
]

BUSINESS_KEYWORDS = [
    "GDP","inflation","rate","tariff","trade","economy","market","oil","gas",
    "bank","central bank","IMF","World Bank","budget","deficit","investment",
    "supply chain","recession","growth","exports","imports","currency",
    "stock","equities","bond","earnings","revenue","acquisition","merger",
    "interest rate","Fed","ECB","OPEC","commodities",
]

GRAVITY_TERMS = [
    "invasion","nuclear","coup","assassination","war","ceasefire",
    "sanctions","collapse","crisis","emergency","resign","impeach",
    "election result","summit","treaty signed","default","recession",
    "outbreak","explosion","killed","casualties","missile strike",
]

REGION_MAP = {
    "EU":   ["Germany","France","UK","Britain","Spain","Italy","Poland","Netherlands",
             "Belgium","Sweden","Austria","Greece","Portugal","Romania","Hungary",
             "Czech","Denmark","Finland","Norway","Switzerland","EU","Europe",
             "Ukraine","NATO","Brussels","Eurozone"],
    "NA":   ["United States","US ","America","Canada","Mexico","Washington","Biden",
             "Trump","Congress","Senate","White House","Pentagon","Ottawa"],
    "MENA": ["Israel","Gaza","Palestine","Iran","Iraq","Syria","Lebanon","Saudi",
             "UAE","Qatar","Egypt","Libya","Yemen","Jordan","Kuwait","Bahrain",
             "Oman","Algeria","Tunisia","Morocco","Turkey","OPEC","Tehran","Riyadh"],
    "APJ":  ["China","Japan","South Korea","North Korea","Taiwan","Australia",
             "Indonesia","Philippines","Vietnam","Thailand","Malaysia","Singapore",
             "Hong Kong","New Zealand","Myanmar","ASEAN","Beijing","Tokyo","Seoul"],
    "SA":   ["India","Pakistan","Bangladesh","Sri Lanka","Nepal","Afghanistan",
             "Brazil","Argentina","Colombia","Chile","Venezuela","Peru","Bolivia",
             "Latin America","Caribbean","New Delhi","Islamabad","Brasilia"],
}

CONFLICT_KEYWORDS = {
    "ukraine-war":      ["Ukraine","Kyiv","Zelensky","Russian forces","Avdiivka","Kharkiv","Donbas"],
    "israel-hamas":     ["Gaza","Hamas","IDF","West Bank","Rafah","Palestinian","Netanyahu","hostage"],
    "us-china-trade":   ["Taiwan Strait","South China Sea","chip ban","semiconductor export","EV tariff","US-China"],
    "india-pakistan":   ["Kashmir","Line of Control","LoC","India-Pakistan","cross-border firing"],
    "sudan-civil-war":  ["Sudan","Khartoum","RSF","SAF","Darfur"],
    "myanmar-conflict": ["Myanmar","Burma","junta","Tatmadaw","NUG"],
    "iran-tensions":    ["Iran nuclear","IAEA","enrichment","Fordow","JCPOA","Iranian missile"],
}

ESCALATION_SIGNALS  = ["attack","offensive","invasion","missile strike","troops advance",
                        "escalat","mobiliz","martial law","coup","emergency","explosion","casualties"]
RESOLUTION_SIGNALS  = ["ceasefire signed","peace deal","agreement reached","troops withdraw",
                        "diplomatic solution","normalization","restored","resolved","accord","treaty signed"]


# ──────────────────────────────────────────────────────────────
# CLASSIFICATION
# ──────────────────────────────────────────────────────────────

def classify_category(text, default):
    pol = sum(1 for k in POLITICAL_KEYWORDS    if k.lower() in text)
    geo = sum(1 for k in GEOPOLITICAL_KEYWORDS if k.lower() in text)
    biz = sum(1 for k in BUSINESS_KEYWORDS     if k.lower() in text)
    if biz > geo and biz > pol: return "business"
    if geo >= pol:               return "geopolitics"
    if pol > 0:                  return "politics"
    return default

def classify_region(text, default):
    best, best_score = default, 0
    for region, keywords in REGION_MAP.items():
        hits = sum(1 for k in keywords if k.lower() in text)
        if hits > best_score:
            best, best_score = region, hits
    return best

def classify_conflict(text):
    for cid, keywords in CONFLICT_KEYWORDS.items():
        if sum(1 for k in keywords if k.lower() in text) >= 2:
            return cid
    return None

def extract_country(text):
    all_entities = [k for kws in REGION_MAP.values() for k in kws]
    for entity in sorted(all_entities, key=len, reverse=True):
        if entity.lower() in text.lower() and len(entity) > 3:
            return entity
    return None


# ──────────────────────────────────────────────────────────────
# SCORING
# ──────────────────────────────────────────────────────────────

def similar_headline(h1, h2):
    STOP = {"the","a","an","is","in","on","at","to","of","and","or","for","with","as","by","from","says","said","new","after"}
    w1 = set(re.sub(r'[^a-z0-9 ]','',h1.lower()).split()) - STOP
    w2 = set(re.sub(r'[^a-z0-9 ]','',h2.lower()).split()) - STOP
    return len(w1 & w2) >= 3

def score_story(story, all_stories):
    text  = (story["headline"] + " " + story["summary"]).lower()
    score = 0
    score += (SOURCE_AUTHORITY.get(story["source"], 60) / 100) * 30
    score += min(sum(1 for t in GRAVITY_TERMS if t in text) * 8, 25)
    corroboration = sum(
        1 for s in all_stories
        if s["id"] != story["id"]
        and similar_headline(story["headline"], s["headline"])
        and s["source"] != story["source"]
    )
    score += min(corroboration * 8, 25)
    if story.get("conflict_id"):
        score += 20
    return round(min(score, 100), 1)


# ──────────────────────────────────────────────────────────────
# FETCH
# ──────────────────────────────────────────────────────────────

def fetch_rss():
    stories = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).date()
    today  = datetime.now(timezone.utc).date()
    all_kw = POLITICAL_KEYWORDS + GEOPOLITICAL_KEYWORDS + BUSINESS_KEYWORDS

    for cfg in RSS_FEEDS:
        try:
            feed = feedparser.parse(cfg["url"])
            for entry in feed.entries[:25]:
                headline = entry.get("title","").strip()
                summary  = re.sub(r'<[^>]+>','', entry.get("summary", entry.get("description",""))).strip()[:500]
                url      = entry.get("link","#")

                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                pub_date = datetime(*pub[:6], tzinfo=timezone.utc).date() if pub else today
                pub_time = datetime(*pub[:6]).strftime("%H:%M") if pub else ""

                if pub_date < cutoff or not headline:
                    continue

                combined = (headline + " " + summary).lower()
                if any(k in combined for k in NOISE):
                    continue
                if not any(k.lower() in combined for k in all_kw):
                    continue

                stories.append({
                    "id":          f"{pub_date}-{hashlib.md5(headline.encode()).hexdigest()[:8]}",
                    "headline":    headline[:200],
                    "summary":     summary[:450],
                    "source":      cfg["source"],
                    "url":         url,
                    "region":      classify_region(combined, cfg["region"]),
                    "country":     extract_country(combined),
                    "category":    classify_category(combined, cfg["default_cat"]),
                    "date":        pub_date.isoformat(),
                    "time":        pub_time,
                    "conflict_id": classify_conflict(combined),
                    "score":       0,
                })
        except Exception as e:
            print(f"  ⚠ {cfg['source']}: {e}")
    return stories


def fetch_newsapi(api_key):
    if not api_key:
        return []
    TRUSTED = "reuters,bbc-news,al-jazeera-english,financial-times,bloomberg,associated-press,the-guardian-uk"
    today   = datetime.now(timezone.utc).date().isoformat()
    queries = [
        ("election OR parliament OR coup OR government crisis", "politics"),
        ("war OR conflict OR sanctions OR military offensive", "geopolitics"),
        ("inflation OR tariff OR recession OR central bank",   "business"),
    ]
    stories = []
    for q, cat in queries:
        try:
            url = (f"https://newsapi.org/v2/everything?q={q.replace(' ','+')}"
                   f"&sources={TRUSTED}&from={today}&sortBy=relevancy&pageSize=15&language=en&apiKey={api_key}")
            with urlopen(Request(url, headers={"User-Agent":"GlobalIntelBot/2.0"}), timeout=10) as r:
                data = json.loads(r.read())
            for a in data.get("articles",[]):
                title = a.get("title","").strip()
                desc  = a.get("description","").strip()
                if not title or "[Removed]" in title:
                    continue
                combined = (title + " " + desc).lower()
                if any(k in combined for k in NOISE):
                    continue
                pub = a.get("publishedAt","")
                stories.append({
                    "id":          f"api-{hashlib.md5(title.encode()).hexdigest()[:8]}",
                    "headline":    title[:200],
                    "summary":     desc[:450],
                    "source":      (a.get("source") or {}).get("name","NewsAPI"),
                    "url":         a.get("url","#"),
                    "region":      classify_region(combined, "NA"),
                    "country":     extract_country(combined),
                    "category":    classify_category(combined, cat),
                    "date":        pub[:10] if pub else today,
                    "time":        pub[11:16] if pub else "",
                    "conflict_id": classify_conflict(combined),
                    "score":       0,
                })
        except Exception as e:
            print(f"  ⚠ NewsAPI ({cat}): {e}")
    return stories


# ──────────────────────────────────────────────────────────────
# DEDUP + RANK
# ──────────────────────────────────────────────────────────────

def deduplicate(stories):
    seen, unique = {}, []
    for s in stories:
        key = re.sub(r'[^a-z0-9]','', s["headline"].lower())[:60]
        if key not in seen:
            seen[key] = s
            unique.append(s)
        else:
            existing = seen[key]
            if SOURCE_AUTHORITY.get(s["source"],0) > SOURCE_AUTHORITY.get(existing["source"],0):
                unique = [s if x["id"]==existing["id"] else x for x in unique]
                seen[key] = s
    return unique


def rank_and_filter(stories):
    for s in stories:
        s["score"] = score_story(s, stories)
    stories.sort(key=lambda x: x["score"], reverse=True)

    buckets, kept = {}, []
    for s in stories:
        bucket = f"{s['region']}-{s['category']}"
        count  = buckets.get(bucket, 0)
        if s.get("conflict_id"):          # always keep conflict stories
            kept.append(s)
            buckets[bucket] = count + 1
        elif count < TOP_N_PER_BUCKET:
            kept.append(s)
            buckets[bucket] = count + 1

    kept.sort(key=lambda x: (x["date"], x["score"]), reverse=True)
    return kept


# ──────────────────────────────────────────────────────────────
# CONFLICT LIFECYCLE
# ──────────────────────────────────────────────────────────────

def load_conflicts():
    if os.path.exists("conflicts_data.json"):
        with open("conflicts_data.json") as f:
            return json.load(f)
    return default_conflicts()


def update_conflict_signals(conflicts, stories):
    today = datetime.now(timezone.utc).date().isoformat()
    for conflict in conflicts:
        cid      = conflict["id"]
        keywords = CONFLICT_KEYWORDS.get(cid, [])
        matching = [
            s for s in stories
            if sum(1 for k in keywords if k.lower() in (s["headline"]+" "+s["summary"]).lower()) >= 1
        ]
        if not matching:
            continue

        latest = max(matching, key=lambda x: x["date"])
        conflict["last_activity"] = latest["date"]
        conflict["recent_headlines"] = [
            {"headline": s["headline"], "source": s["source"], "date": s["date"]}
            for s in matching[:3]
        ]

        texts    = " ".join(s["headline"]+" "+s["summary"] for s in matching[:10]).lower()
        esc_hits = sum(1 for k in ESCALATION_SIGNALS if k in texts)
        res_hits = sum(1 for k in RESOLUTION_SIGNALS if k in texts)

        if res_hits >= 2 and res_hits > esc_hits:
            conflict["status_signal"] = "de-escalating"
        elif esc_hits >= 2:
            conflict["status_signal"] = "escalating"
        else:
            conflict["status_signal"] = "stable"

        # Auto-advance status only if explicitly enabled on the conflict
        if conflict.get("auto_status", False):
            sig = conflict["status_signal"]
            if sig == "de-escalating" and conflict["status"] == "ongoing":
                conflict["status"] = "closed";  conflict["status_changed"] = today
            elif sig == "escalating" and conflict["status"] == "closed":
                conflict["status"] = "open";    conflict["status_changed"] = today
            elif conflict["status"] == "open" and sig == "stable":
                conflict["status"] = "ongoing"; conflict["status_changed"] = today

    return conflicts


def default_conflicts():
    return [
        {
            "id": "ukraine-war", "name": "Russia–Ukraine War", "region": "EU",
            "status": "ongoing", "auto_status": False,
            "description": "Full-scale Russian invasion since Feb 2022. Active fighting in eastern Ukraine. Peace talks stalled.",
            "status_signal": "stable", "last_activity": None, "recent_headlines": [],
            "timeline": [
                {"date":"Feb 2022","event":"Russia launches full-scale invasion"},
                {"date":"Nov 2022","event":"Ukraine recaptures Kherson"},
                {"date":"Jun 2023","event":"Ukrainian counteroffensive begins"},
                {"date":"Feb 2024","event":"Russia advances on Avdiivka"},
            ]
        },
        {
            "id": "israel-hamas", "name": "Israel–Hamas Conflict", "region": "MENA",
            "status": "ongoing", "auto_status": False,
            "description": "Military conflict in Gaza following Hamas attacks on Oct 7, 2023. Ceasefire negotiations ongoing.",
            "status_signal": "stable", "last_activity": None, "recent_headlines": [],
            "timeline": [
                {"date":"Oct 2023","event":"Hamas attacks; IDF launches Gaza operation"},
                {"date":"Nov 2023","event":"Temporary ceasefire and hostage exchanges"},
                {"date":"Jan 2024","event":"ICJ orders Israel to prevent genocide"},
                {"date":"Mar 2024","event":"Cairo ceasefire talks resume"},
            ]
        },
        {
            "id": "us-china-trade", "name": "US–China Tech & Trade War", "region": "APJ",
            "status": "ongoing", "auto_status": False,
            "description": "Escalating economic and technology rivalry. Semiconductor controls, EV tariffs, Taiwan Strait tensions.",
            "status_signal": "stable", "last_activity": None, "recent_headlines": [],
            "timeline": [
                {"date":"2018","event":"Trump imposes first tariff wave"},
                {"date":"2022","event":"CHIPS Act + semiconductor export controls"},
                {"date":"2024","event":"Biden imposes EV tariffs on Chinese vehicles"},
            ]
        },
        {
            "id": "india-pakistan", "name": "India–Pakistan Tensions", "region": "APJ",
            "status": "open", "auto_status": False,
            "description": "Heightened tensions along the Line of Control in Kashmir.",
            "status_signal": "escalating", "last_activity": None, "recent_headlines": [],
            "timeline": [
                {"date":"2019","event":"India revokes Article 370"},
                {"date":"2023","event":"Cross-border firing incidents increase"},
                {"date":"2024","event":"Envoys summoned after LoC incident"},
            ]
        },
        {
            "id": "sudan-civil-war", "name": "Sudan Civil War", "region": "MENA",
            "status": "ongoing", "auto_status": False,
            "description": "War between SAF and RSF since April 2023. Humanitarian catastrophe in Darfur.",
            "status_signal": "stable", "last_activity": None, "recent_headlines": [],
            "timeline": [
                {"date":"Apr 2023","event":"Fighting erupts between SAF and RSF"},
                {"date":"Jun 2023","event":"RSF atrocities reported in El Fasher"},
                {"date":"2024","event":"Over 8 million displaced; famine conditions"},
            ]
        },
        {
            "id": "iran-tensions", "name": "Iran Nuclear Tensions", "region": "MENA",
            "status": "ongoing", "auto_status": False,
            "description": "Iran enriches beyond JCPOA limits. IAEA access restricted. Regional proxy conflicts intensify.",
            "status_signal": "stable", "last_activity": None, "recent_headlines": [],
            "timeline": [
                {"date":"2018","event":"US withdraws from JCPOA"},
                {"date":"2021","event":"Iran resumes 60% enrichment"},
                {"date":"2023","event":"IAEA reports 83.7% enrichment"},
                {"date":"2024","event":"Regional proxy escalation post-Gaza"},
            ]
        },
        {
            "id": "nagorno-karabakh", "name": "Nagorno-Karabakh", "region": "MENA",
            "status": "closed", "auto_status": False,
            "description": "Azerbaijani operations in Sep 2023 dissolved separatist government. Conflict concluded.",
            "status_signal": "stable", "last_activity": None, "recent_headlines": [],
            "timeline": [
                {"date":"1994","event":"Ceasefire ends first war"},
                {"date":"2020","event":"44-day war; Azerbaijan regains territory"},
                {"date":"Sep 2023","event":"Azerbaijan offensive; Karabakh government dissolved"},
            ]
        },
    ]


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def main():
    from collections import Counter
    run_time = datetime.now(timezone.utc)
    print(f"\n🌍  Global Intelligence Brain v2 — {run_time.strftime('%Y-%m-%d %H:%M UTC')}\n")

    print("📡 Fetching RSS...")
    stories = fetch_rss()
    print(f"   {len(stories)} raw stories")

    api_key = os.environ.get("NEWSAPI_KEY","")
    if api_key:
        print("📡 Fetching NewsAPI...")
        extra = fetch_newsapi(api_key)
        stories += extra
        print(f"   +{len(extra)} from NewsAPI")

    stories = deduplicate(stories)
    print(f"\n🔀 {len(stories)} unique after dedup")

    print(f"🧠 Scoring + ranking (top {TOP_N_PER_BUCKET}/bucket)...")
    stories = rank_and_filter(stories)
    print(f"   {len(stories)} stories kept")

    print("⚡ Updating conflict signals...")
    conflicts = load_conflicts()
    conflicts = update_conflict_signals(conflicts, stories)
    SYM = {"open":"🔴","ongoing":"🟠","closed":"🟢"}
    ARR = {"escalating":"↑","stable":"→","de-escalating":"↓"}
    for c in conflicts:
        print(f"   {SYM.get(c['status'],'⚪')} {c['name']:<32} {c['status']:<10} {ARR.get(c.get('status_signal','stable'),'→')}")

    with open("news_data.json","w",encoding="utf-8") as f:
        json.dump({"updated":run_time.isoformat(),"story_count":len(stories),
                   "source_count":len(set(s["source"] for s in stories)),"stories":stories},
                  f, ensure_ascii=False, indent=2)

    with open("conflicts_data.json","w",encoding="utf-8") as f:
        json.dump(conflicts, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Saved: {len(stories)} stories · {len(conflicts)} conflicts")
    print(f"📊 {dict(Counter(s['region'] for s in stories))}")
    print(f"   {dict(Counter(s['category'] for s in stories))}")
    secs = (datetime.now(timezone.utc) - run_time).seconds
    print(f"✅ Done in {secs}s\n")

if __name__ == "__main__":
    main()
