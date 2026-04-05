# Global Intelligence — Daily Briefing

A self-updating geopolitical and business news dashboard. Fully automated, zero cost.

**Live at:** `https://anurag92dash.github.io/global-intelligence/`

---

## Architecture

```
GitHub Actions (cron 06:00 UTC / 11:30 IST)
        ↓
fetch_news.py — fetches, scores, filters, saves
        ↓
news_data.json + conflicts_data.json  ← committed back to repo
        ↓
GitHub Pages serves index.html
        ↓
Browser fetches JSON via jsDelivr CDN (bypasses Jekyll)
```

The entire pipeline runs inside GitHub's free tier. No servers, no databases, no cost.

---

## News Sources

Only high-authority outlets are used. Each source has an authority score that feeds into story ranking.

| Source | Authority | Focus |
|---|---|---|
| Reuters | 95 | Global, all categories |
| AP News | 93 | Global, all categories |
| BBC News | 90 | Global, all categories |
| Financial Times | 88 | Business, Europe |
| Bloomberg | 87 | Business, Markets |
| The Economist | 86 | Business, Global |
| Wall Street Journal | 85 | Business, NA |
| New York Times | 84 | Politics, NA |
| Washington Post | 83 | Politics, NA |
| The Guardian | 80 | Geopolitics, EU |
| Al Jazeera | 78 | MENA, APJ |
| Nikkei Asia | 76 | Business, APJ |
| Politico | 72 | Politics, NA |
| Euronews | 70 | Politics, EU |
| DW News | 70 | Politics, EU |

---

## How News is Filtered

Raw RSS feeds produce ~150 stories per run. Four layers of filtering bring this down to ~70 high-signal stories.

**1. Noise removal** — drops sports, entertainment, celebrity, weather, and lifestyle content by keyword.

**2. Relevance gate** — a story must contain at least one keyword from the politics, geopolitics, or business keyword banks to pass.

**3. Importance scoring (0–100):**
- Source authority → up to 30 pts
- Gravity terms (invasion, coup, sanctions, ceasefire...) → up to 25 pts
- Corroboration (same event covered by multiple sources) → up to 25 pts
- Conflict relevance (linked to a tracked situation) → 20 pts

**4. Bucket cap** — top 8 stories per region × category survive. Conflict-tagged stories always pass regardless of score.

---

## Regions

| Code | Coverage |
|---|---|
| EU | Europe, UK, NATO, Ukraine |
| NA | USA, Canada, Mexico |
| MENA | Middle East, North Africa, Turkey, OPEC |
| APJ | Asia Pacific, China, Japan, ASEAN, Australia |
| SA | South Asia, India, Pakistan, Brazil, Latin America |

---

## How History Works

`histories.json` contains hand-curated one-liner timelines for 14 major topics — going back to root causes, not just recent events. Each covers the full arc from origin to present, sourced from Reuters, BBC, FT, Al Jazeera, and The Guardian.

**Topics:** Russia–Ukraine War · Israel–Hamas · US–China Trade War · India–Pakistan · Sudan Civil War · Iran Nuclear Tensions · China–Taiwan · US Politics · EU Political Landscape · China under Xi · India's Rise · Middle East Realignment · Global Inflation Cycle · Global AI Race

Click any conflict chip or topic chip in the dashboard to read the full history with a vertical timeline.

---

## Conflict Lifecycle

| Status | Meaning |
|---|---|
| 🔴 Open | New or actively escalating |
| 🟠 Ongoing | Active, developing |
| 🟢 Closed | Resolved or concluded |

The script computes a daily `status_signal` (escalating ↑ / stable → / de-escalating ↓) from keyword patterns in matching stories. The actual status is changed manually by editing `conflicts_data.json` in GitHub.

---

## Files

```
index.html              the dashboard
fetch_news.py           the automation brain
histories.json          curated topic histories (edit manually)
conflicts_data.json     situation tracker (auto-updated + manually editable)
news_data.json          daily story output (auto-generated, do not edit)
.nojekyll               disables Jekyll so JSON files are served correctly
.github/workflows/
  daily_briefing.yml    cron schedule
```

---

## Adding a New Situation

Add to `conflicts_data.json`:

```json
{
  "id": "your-id",
  "name": "Situation Name",
  "region": "MENA",
  "status": "open",
  "description": "One paragraph summary.",
  "timeline": [
    { "date": "2024", "event": "What happened" }
  ]
}
```

Add a matching entry to `histories.json` with the same `id` for the full historical timeline.
