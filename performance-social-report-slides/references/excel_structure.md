# Expected Excel Structure

## Sheet Layout

The report Excel file should have **one sheet** (name is auto-detected).
The sheet contains two major sections:

### 1. Overall Summary (top)
Section headers: `OVERALL CAMPAIGN`, `META`, `YOUTUBE`, `TIKTOK`
These are aggregate rows and are **skipped** by the parser.

### 2. Monthly Breakdown (main data)
Triggered by the marker `BY MONTHLY (JANUARY, FEBRUARY, MARCH)`.
Contains one or more months, each labelled `JANUARY`, `FEBRUARY`, `MARCH` etc.

Within each month there are **campaign blocks** — one block = one post/slide.

## Campaign Block Structure

Each block starts with a **header row** followed by **data rows**, ending at an empty row:

```
[header row]   Campaign name | Placement | Objective | Platform | Amount spent (MYR) | ...
[data row 1]   0|XXXXX|...   | Instagram Reels | ...
[data row 2]   (empty)       | Feed            | ...   ← same campaign, blank col 0
[data row 3]   (empty)       | Instagram Stories | ...
[empty row]                                             ← block ends here
```

## Platform Detection

The **second column of the header row** identifies the platform:

| Header col 1 value      | Platform  | Column set |
|-------------------------|-----------|------------|
| `Placement`             | Instagram | IG_COLS    |
| `Advertising objective` | TikTok    | TT_COLS    |
| `Campaign type`         | YouTube   | YT_COLS    |

## Instagram Column Indices (0-based)

| Index | Field             |
|-------|-------------------|
| 0     | Campaign name     |
| 1     | Placement         |
| 2     | Objective         |
| 3     | Platform          |
| 4     | Amount spent (MYR)|
| 5     | Impressions       |
| 6     | Reach             |
| 7     | Frequency         |
| 8     | Facebook likes    |
| 9     | Post comments     |
| 10    | Post shares       |
| 11    | Post reactions    |
| 12    | Post engagements  |
| 13    | Post saves        |
| 14    | Clicks (all)      |
| 15    | Views             |

## TikTok Column Indices (0-based)

| Index | Field                    | Mapped to         |
|-------|--------------------------|-------------------|
| 0     | Campaign name            | Campaign name     |
| 1     | Advertising objective    | Placement         |
| 2     | Amount spent (MYR)       | Amount spent      |
| 3     | Impressions              | Impressions       |
| 4     | Reach                    | Reach             |
| 5     | Frequency                | Frequency         |
| 6     | Paid likes               | Post reactions    |
| 7     | Paid comments            | Post comments     |
| 8     | Paid shares              | Post shares       |
| 9     | Clicks (all)             | Clicks (all)      |
| 10    | Video views              | Views             |

Post engagements and Post saves are **not available** in TikTok data → show `-`.

## YouTube Column Indices (0-based)

| Index | Field                  |
|-------|------------------------|
| 0     | Campaign               |
| 1     | Campaign type          |
| 2     | Impr. (Impressions)    |
| 3     | Reach                  |
| 4     | Amount spent (MYR)     |
| 5     | Engagements            |
| 6     | TrueView views         |
| 7     | Engagement rate        |
| 13    | Video played to 25%    |
| 14    | Video played to 50%    |
| 15    | Video played to 75%    |
| 16    | Video played to 100%   |

## Post Links

Links to the actual posts appear at the **bottom of each month's section**, after all campaign blocks, in rows starting with `Link:`. They are listed in order but not explicitly labelled by post.

The thumbnail generator matches them by type:
- `/p/` URLs → static/carousel posts (DS Article type campaigns)
- `/reel/` URLs → video posts (Social Boosting / KITA SERUMPUN type)

Missing links are flagged as unavailable (90-day retention policy note in source data).
