# LinkedIn content-type classification

Classify the media container of the LinkedIn post, not its topic, campaign, or organic/paid status.

## Evidence priority

1. Directly inspect the public LinkedIn post.
2. Use explicit raw-export metadata such as a native video duration, document/page indicator, poll fields, or article URL.
3. Use a user-provided screenshot or source-system view.
4. If none is conclusive, leave the value blank and flag the row for review.

Never use `Post type = Organic` or `Sponsored` as a media format. Never classify from caption phrases such as “watch,” “read,” or “swipe” without corroborating media evidence.

## Labels and signals

| Label | Use when the post visibly contains |
|---|---|
| `Image` | One static image or a multi-image gallery |
| `Video` | A native playable video or explicit native-video metadata |
| `Document` | A LinkedIn document/PDF/slide carousel with pages |
| `Article` | An external-link preview, LinkedIn article, or newsletter |
| `Poll` | Poll choices and voting controls |
| `Event` | A LinkedIn event card/page as the main attachment |
| `Text` | No media, document, link preview, poll, or event |

## Common LinkedIn guest-page clues

- Static media normally appears as one or more image elements between the caption and engagement counts.
- A native document often exposes a document title or page-style viewer rather than a normal post image.
- An external publisher/domain card is `Article`, even if the card itself contains a thumbnail.
- A video thumbnail alone is insufficient if it is actually an external-link card; confirm a native player or video metadata.

Guest pages change over time. Treat these clues as supporting evidence, not permanent HTML rules.

## Confidence

- `high`: the post or raw metadata explicitly shows the format.
- `medium`: multiple indirect signals agree.
- `low`: evidence is incomplete; normally leave the content type blank and set `needs_review` to `true`.

Keep a short evidence note, for example:

- `Native video player visible on public post`
- `Five-image gallery visible before engagement counts`
- `LinkedIn PDF document viewer with page controls`
- `Bloomberg external-link preview card`
