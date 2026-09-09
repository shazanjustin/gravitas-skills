---
name: client-friendly-report-writer
description: |
  Write or rewrite report findings into clear, client-facing analysis with plain language, calibrated causality, useful numbers, and practical recommendations.

  Use when the user mentions "client-facing report", "make this insight less dramatic", "report writing guideline", "social media findings", "cause-effect title", "Deloitte style", "McKinsey style", or asks to turn raw metrics into readable strategic findings.
---

# Client-Friendly Report Writer

Use this skill to write or turn rough findings, raw metrics, or over-written analysis into calm, useful, client-facing report copy.

This skill is especially useful for social media, campaign, content, and performance reports, but the writing rules can apply to any business report where the reader needs to understand what changed, why it likely changed, why it matters, and what to do next.

The goal is not to make writing sound smarter. The goal is to make the thinking harder to misunderstand.

## Core Doctrine

Do not write like a crisis report. Do not dramatise normal performance movement. Do not use inflated language to make the analysis feel more important.

A good client finding should be:

- clear enough for client servicing
- sharp enough for strategy
- specific enough for performance review
- calm enough to be trusted
- practical enough to guide the next decision

## Reference Style Sources

### McKinsey

- McKinsey & Company: https://www.mckinsey.com/
- McKinsey Insights: https://www.mckinsey.com/featured-insights
- McKinsey Marketing & Sales: https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights

McKinsey-style rule: make analysis useful for decision-makers. Findings should help the reader understand channel performance, content performance, audience behaviour, and the next action. Do not stop at reporting numbers.

Use this pattern:

```text
What happened → what it means → what decision it informs
```

Example:

```text
The report should not only show whether reach or engagement increased. It should explain which channels, formats, and content themes contributed to the movement, so the next content plan can be adjusted with less guesswork.
```

### The Economist

- The Economist: https://www.economist.com/

Economist-style rule: write with restraint. Use clear logic, plain language, and causality. Prefer precise, readable sentences over dramatic phrasing.

Use this pattern:

```text
Plain claim → evidence → explanation
```

## Default Output Structure

Use this structure as an option:

```text
[Cause-Effect Title]

[Metric/platform] [increased/decreased/remained stable] by [number], while [comparison metric] [movement]. This suggests [simple interpretation].

The movement could be caused by [likely driver], especially [content format/campaign/posting volume/example]. 

Moving forward, [specific action] should be prioritised to [desired outcome].
```

Use this compact structure when the report needs shorter slide copy:

```text
[Cause-Effect Title]

[What happened]. This appears linked to [likely reason]. Moving forward, [specific action].
```

Use this internal analysis structure when the user wants working notes:

```text
Trend: [what changed]
Likely driver: [probable reason]
Implication: [why it matters]
Action: [what to do next]
```

Use this structure for a numbered Key Takeaways slide, where findings run as 2 to 4 columns across one slide:

```text
01

[Headline: one sentence carrying the argument, cause-effect where the data supports it]

[What happened, with the 2 to 3 numbers that prove it.]

[What it means, and how the client compares.]

For [Client]: [the specific action that follows from this finding.]
```

Rules for this format:

- Keep every column's body within roughly 100 characters of the others. A column that runs long has to be set in a smaller size to fit, and the row stops reading as one set. In one July report, columns of 625, 743 and 983 characters forced the third down to 7pt against 8pt for the other two, which was visible at a glance.
- If the copy does not fit, cut the weakest takeaway rather than shrinking type for one column.
- 3 columns is the usual house format. Prefer 3 strong findings over 4 thin ones.
- Every column ends with the `For [Client]:` line. That line is the payoff, and a column without one is an observation rather than a takeaway.
- The headline should still follow the Title Rules below. A numbered slide is not a licence to write label headlines like "Posting Volume".

## Title Rules

Every finding title must explain a cause-effect relationship, a trend, or a useful strategic interpretation. The title should already contain the argument.

Avoid titles that only describe a metric movement:

- TikTok Performance Dropped
- Facebook Engagement Improved
- Instagram Was Strong
- Visibility Took a Hit
- Engagement Surged Across Channels

Prefer cause-effect titles:

- Lower Admissions-Focused Content Reduced TikTok Visibility
- Higher Posting Frequency Helped Facebook Maintain Engagement
- Campus-Led Content Supported Stronger Instagram Engagement
- Lower Posting Volume Reduced Cross-Platform Visibility
- Reduced Video-Led Content Weakened Facebook Reach
- High-Intent Content Helped Instagram Offset Lower Reach

Title formulas:

```text
[Cause] reduced [effect]
[Cause] supported [effect]
[Cause] helped maintain [effect]
[Cause] limited [effect]
[Cause] appears linked to [effect]
```

Good title examples:

- Lower Posting Frequency Limited LinkedIn Visibility
- Stronger Share-Led Content Helped Instagram Maintain Engagement
- Reduced Video-Led Content Weakened Facebook Reach
- Higher Posting Volume Supported TikTok Engagement Growth
- Clearer Utility Content Improved Audience Response

Comparison between different timing, such as quarters, monthly, weekly could be considered. 

## Number Rules

Use numerals for reporting and comparison.

Correct:

- 6 posts
- 18 posts
- 2.5% ER
- 60% of engagement
- 1,039 likes
- 54.0% decline
- 12 to 18 posts

Incorrect:

- six posts
- eighteen posts
- two point five percent
- sixty percent of engagement

Avoid starting sentences with numerals. Rewrite the sentence instead.

Bad:

```text
6 more posts were published this month.
```

Better:

```text
The account published 6 more posts this month.
```

Use numbers for comparison, not decoration. Use the most important 2 to 3 numbers per finding unless the user asks for deeper detail.

Good:

```text
Facebook reach declined 54.0%, but engagement rate improved from 0.86% to 1.07%. This suggests the smaller audience was more likely to interact with the content that reached them.
```

Bad:

```text
Facebook reach declined 54.0% to 48,462, views fell 86.5% to 63,295, ER rose 0.86% to 1.07%, posts increased from 12 to 18, likes increased 154.5%, shares increased 28.6%, and static content accounted for 60%.
```

If many metrics are provided, select the metrics that best prove the finding. Do not turn the paragraph into metric soup.

## Language Rules

Use plain analytical language. The tone should be calm, precise, readable, and evidence-led.

Write from the client's point of view. The client should not need to translate analyst language into business language. If a term is technically correct but not immediately clear, replace it with a simpler phrase.

Avoid abstract, overly technical, or vague wording:

- mathematical normalization
- marginal fluctuations
- reduced output
- content output
- distribution mechanics
- optimisation pressure
- algorithmic behaviour
- efficiency gains
- platform recalibration

Prefer concrete client-friendly wording:

- performance returned to a more typical level
- small changes
- fewer posts
- number of posts decreased
- fewer opportunities to reach the audience
- the platform showed the content to fewer people
- the content mix changed
- posting frequency was lower

Example:

Bad:

```text
Reduced output contributed to marginal fluctuations in visibility after mathematical normalization.
```

Better:

```text
The page published fewer posts, which gave the platform fewer opportunities to show the content to the audience.
```

Better with numbers:

```text
The page published 8 posts, down from 14 in the previous period. This likely contributed to lower reach because there were fewer opportunities for the content to appear in-feed.
```

Avoid dramatic or inflated words:

- plummeted
- collapsed
- surged
- skyrocketed
- bolstered
- massive
- erased
- triggered
- exceptional
- catastrophic
- apocalyptic
- algorithmic invisibility
- total collapse
- dramatic decline
- massive hit
- near-total reach erasure
- highly enthusiastic
- deeply connected

Prefer normal analytical words:

- declined
- declined sharply
- increased
- improved
- weakened
- supported
- reduced
- likely contributed to
- appears linked to
- remained stable
- performed better
- showed stronger engagement
- had lower visibility
- had stronger audience response
- helped maintain
- limited
- offset

Do not use theatrical phrasing. Client reporting is not campaign copy.

## Punctuation Rules

Do not use em dashes (—) or en dashes (–) in client-facing copy. Rewrite with a comma, a colon, a semicolon, or a separate sentence.

Bad:

```text
Reach declined 54.0% — the lowest of the year — while engagement held steady.
```

Better:

```text
Reach declined 54.0%, the lowest of the year, while engagement held steady.
```

For ranges, write the word instead of a dash.

Bad:

```text
Contest period: 3–31 July
TikTok Grocer Day, 13–17 July
```

Better:

```text
Contest period: 3 to 31 July
TikTok Grocer Day, 13 to 17 July
```

Hyphens inside compound words are fine and should be kept: same-day, one-off, receipt-gated, high-intent, doctor-fronted. The rule is about the long dashes only.

Check the output for `—` and `–` before returning it. This is a formatting rule, not a style preference, so it applies to every deliverable including slide copy, tables, and headlines.

## Causality Rules

Do not overclaim. Unless the data proves causality, use calibrated language.

Use high-confidence causality only when the evidence is direct:

- was mainly driven by
- was primarily due to

Use medium-confidence causality for strong patterns:

- appears linked to
- likely contributed to
- suggests
- points to

Use low-confidence causality for hypotheses:

- may indicate
- may suggest
- could reflect
- may be partly linked to

Avoid unless causality is proven:

- caused
- triggered
- resulted in
- led directly to
- created a collapse

Default phrase:

```text
likely contributed to
```

Example:

Bad:

```text
The shift to static academic recaps triggered a total collapse in Facebook visibility.
```

Better:

```text
The shift from video-led content to static academic recaps likely contributed to weaker Facebook visibility.
```

Best when numbers are available:

```text
Facebook reach declined after the content mix moved away from video-led formats that performed well in the previous period. This suggests the platform may still depend on more dynamic formats to drive reach and interaction.
```

## Client Comprehension Rules

Assume the client is smart but busy. They may not live inside social analytics every day, so the writing should remove friction.

Use words the client can immediately picture:

- Say "fewer posts" instead of "reduced output".
- Say "small changes" instead of "marginal fluctuations".
- Say "returned to a more typical level" instead of "normalised" or "mathematical normalization".
- Say "the audience was more likely to interact" instead of "engagement efficiency improved".
- Say "the platform showed the content to fewer people" instead of "distribution was constrained".

When a concept needs explanation, explain it in business terms:

- Reach = how many people had the chance to see the content.
- Engagement rate = how likely people were to interact after seeing it.
- Shares = whether the content was useful or relevant enough to pass on.
- Saves = whether the content had reference value.
- Posting frequency = how many chances the brand gave itself to appear in-feed.

Do not hide weak clarity behind consulting language. Clear beats clever.

## Analytical Rules

Each finding should focus on 1 main argument.

Bad:

```text
Reach declined, Facebook engagement dropped, Instagram stayed resilient, TikTok underperformed, LinkedIn impressions declined, post volume reduced, and the recommendation is to increase content frequency.
```

Better: split into separate findings.

- Lower Posting Volume Reduced Cross-Platform Visibility
- Reduced Video-Led Content Weakened Facebook Reach
- Campus-Led Content Helped Instagram Maintain Engagement
- Lower Admissions-Focused Content Reduced TikTok Visibility

Separate the thinking clearly:

1. Observation: what the numbers show.
2. Interpretation: what likely explains the movement.
3. Implication: why the client should care.
4. Action: what should happen next.

Do not combine too many explanations in 1 paragraph. If a finding needs several causes, either rank them or split the finding.

## Recommendation Rules

Recommendations must connect directly to the finding.

Bad:

```text
Improve content quality.
```

Better:

```text
Prioritise short admissions-led TikTok videos that answer practical student questions, as this format previously generated stronger reach and shares.
```

Bad:

```text
Increase engagement.
```

Better:

```text
Use more saveable and shareable Instagram formats, especially campus-life and outcome-led posts, to maintain high-intent engagement.
```

A good recommendation should specify:

- what to do
- where to do it
- why it follows from the finding
- what outcome it is meant to improve

## Before-and-After Rewrites

### Example 1: Overdramatic cross-platform finding

Bad:

```text
Visibility took a massive hit across the social ecosystem, characterised by near-total reach erasure on certain channels.
```

Good:

```text
Lower Posting Volume Reduced Cross-Platform Visibility

Facebook and TikTok recorded the largest visibility declines, while Instagram and LinkedIn also trended downward. This appears linked to lower posting volume and fewer high-reach formats compared with the previous period.

This matters because lower visibility reduces the brand’s ability to reach both existing followers and new audiences. Moving forward, posting consistency should be restored while retaining formats that have previously shown strong reach potential.
```

### Example 2: Facebook

```text
Higher Posting Frequency Helped Facebook Maintain Engagement

Facebook reach declined 54.0%, but engagement rate improved from 0.86% to 1.07%. This suggests the smaller audience was more likely to interact with the content that reached them.

The increase in posting volume, from 12 to 18 posts, likely helped maintain activity during a lower-reach period. Static content also contributed 60% of total engagement, indicating that clear, easy-to-consume formats continued to work for the audience.

Moving forward, Facebook should maintain consistent posting while identifying which static formats are driving the strongest interaction.
```

### Example 3: Instagram

```text
High-Intent Content Helped Instagram Offset Lower Reach

Instagram reach declined 88.4%, but organic engagement increased 51.6% to 532. Engagement rate also improved to 3.09%, suggesting that the audience was more responsive to the content that reached them.

The increase in saves and comments indicates that the content had stronger relevance among active followers. This matters because high-intent actions are usually a better signal of content value than passive reach alone.

Moving forward, Instagram should continue using content formats that give audiences a clear reason to save, comment, or share.
```

### Example 4: TikTok

```text
Higher Posting Volume Supported TikTok Engagement Growth

TikTok increased posting volume from 3 to 10 posts, while organic engagement increased 255.8% to 153. Organic views also increased to 6,489, suggesting that the platform responded positively to higher content frequency.

The stronger share growth indicates that some posts were able to move beyond the immediate follower base. This matters because TikTok performance depends on repeat testing and enough posting volume for the algorithm to identify which content can travel.

Moving forward, TikTok should maintain higher posting frequency while testing repeatable formats that can drive shares and comments.
```

### Example 5: LinkedIn

```text
Lower Posting Frequency Limited LinkedIn Visibility

LinkedIn impressions declined 22.3%, likely linked to lower posting frequency during the period. With fewer posts, the page had fewer opportunities to appear in-feed and maintain visibility among professional audiences.

This matters because LinkedIn performance is often built through consistent presence rather than isolated high-performing posts. Moving forward, the page should increase posting consistency while prioritising posts that show institutional credibility, industry relevance, and clear professional value.
```

### Example 6: Campaign report

```text
Clearer Product Messaging Improved Consideration

The campaign generated stronger click activity on posts that explained the product benefit directly, while broader awareness-led posts saw lower interaction. This suggests the audience responded better when the message made the value proposition easy to understand.

This matters because consideration content needs to reduce ambiguity, not just create visibility. Moving forward, the campaign should prioritise posts that pair a clear benefit with a specific use case, then use lighter awareness content as a supporting layer.
```

### Example 7: Executive summary

```text
Consistent Posting Helped Maintain Engagement Despite Lower Reach

Overall reach declined across the main channels, but engagement remained more stable where posting frequency increased and the content offered clear audience value. This suggests that consistency helped protect interaction during a lower-visibility period.

The key implication is that the brand should not treat reach recovery as a volume-only issue. The next plan should restore posting consistency while prioritising formats that give audiences a clear reason to comment, save, or share.
```

## Editing Procedure

When rewriting user-provided findings:

1. Identify the main trend.
2. Identify the likely driver.
3. Remove dramatic, inflated, or unsupported claims.
4. Select the most useful 2 to 3 numbers.
5. Rewrite the title as cause-effect or trend-effect.
6. Separate observation from interpretation.
7. Add the business or platform implication.
8. Add a practical recommendation tied to the finding.
9. Check that the client can understand it without extra explanation.

## Final Quality Check

Before returning the final output, verify:

- Does each title show cause and effect, or at least a clear strategic trend?
- Are numbers written as numerals?
- Are only the most useful numbers included?
- Is the language plain rather than dramatic?
- Is causality calibrated?
- Is each finding focused on 1 main argument?
- Is the recommendation linked to the finding?
- Does the output sound like a restrained consulting insight, not a dramatic campaign post?
- Can a client understand it without needing explanation?

If the answer to any of these is no, rewrite again.
