# Token Economics — why this tool saves money

The pitch: **don't send AI models pictures of data — send them the data.**
Both utilities on this site convert pixels into text, which is dramatically
cheaper for LLMs to read and far more useful (the model can actually compute
with numbers; it can only "eyeball" an image).

## Plot → Data

Anthropic prices images at roughly `(width × height) / 750` tokens, and
images larger than 1568 px on the long edge are scaled down to that size
before counting. OpenAI's tile-based pricing lands in the same ballpark.

| What you send | Approx. tokens |
|---|---|
| Phone photo of a plot (resized to 1568×1176) | ~2,460 |
| Typical screenshot of a plot (1092×1092) | ~1,590 |
| Small screenshot (800×600) | ~640 |
| **Extracted data, 60 points** (this tool's default) | **~320** |
| **Extracted data, 20 points** | **~120** |
| **Extracted data, 5 points** | **~45** |

Extracted-data estimates assume ~5 tokens per (x, y) pair plus ~20 tokens of
labeling, e.g.:

```
## Series 1 (#1f77b4)
x = [1.0, 3.0, 5.0, 7.0, 9.0]
y = [20.0, 14.04, 8.015, 17.06, 4.044]
```

**Headline numbers:**

- Phone photo → 60-point extraction: **~8× cheaper**
- Phone photo → 20-point extraction: **~20× cheaper**
- Screenshot → 5-point extraction: **~35× cheaper**

### The savings compound per message

An image in a chat is re-read on **every following turn** of the
conversation. Ten follow-up questions about a 2,460-token photo costs
~24,600 input tokens; the same conversation about a 120-token data table
costs ~1,200. The multiplier applies to the whole conversation, not just
the first message.

### It's not just cheaper — it's better input

- The model can sort, average, fit, and transform actual numbers; from an
  image it can only estimate ("looks like it peaks around 17?").
- No vision hallucination: the numbers the model sees are the numbers
  the tool measured.
- Works with text-only / cheaper models that accept no images at all.

## PDF → Text

Vision-based PDF reading (e.g. Anthropic's PDF support) bills each page as
**both** its text and a full-page image — typically 1,500–3,000 tokens per
page. Plain extracted text from a typical page runs 400–800 tokens.

| What you send | Approx. tokens / page |
|---|---|
| PDF processed with vision | ~1,500–3,000 |
| Scanned page as a raw image | ~1,500–2,500 |
| **Extracted text (this tool)** | **~400–800** |
| **Extracted markdown** (headings/tables preserved) | **~450–900** |

**Headline number: ~3–5× cheaper per page**, and scanned PDFs become usable
with models that can't OCR at all.

## Methodology notes (keep claims honest)

- Image token formula: Anthropic documentation, `tokens ≈ w × h / 750`,
  long edge capped at 1568 px. Checked June 2026 — re-verify before
  publishing, pricing rules change.
- Text token estimates assume ~4 characters per token (English) and
  ~3 tokens per short number; measured against typical outputs of this
  tool, not worst cases.
- Real savings depend on plot complexity and the point count the user
  chooses; the "Max points" setting trades resolution for tokens.
- Cost-in-dollars multipliers are the same as token multipliers, since
  input tokens are priced linearly.
