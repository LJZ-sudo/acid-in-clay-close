# Figure 4 Evaluation Guide

## Overview

Figure 4 requires multi-dimensional scoring data from 5 reports. You need an independent LLM (recommended: Claude Opus 4.5 or GPT-5.2) as an "expert reviewer" to score them.

---

## Step 1: PDF Reports (Already Generated)

All 6 PDF reports have been generated in `model_reports/`:

| # | Model | PDF File | Size |
|---|-------|----------|------|
| 1 | DeepSeek-R1 | `report_deepseek-r1.pdf` | ~833 KB |
| 2 | Gemini 2.5 Pro | `report_gemini-2.5-pro.pdf` | ~479 KB |
| 3 | GPT-5.2 Pro | `report_gpt-5.2-pro.pdf` | ~1604 KB |
| 4 | Qwen (Deep Research) | `report_qwen.pdf` | ~983 KB |
| 5 | Agent-Enhanced (Pipeline) | `report_agent-pipeline.pdf` | ~1772 KB |
| 6 | Agent-Enhanced (ReAct) | `report_agent-react.pdf` | ~2327 KB |

> **Note**: For evaluation, use either Report #5 (Pipeline) or Report #6 (ReAct) as the "Agent-Enhanced" entry. The **ReAct** version (#6) is recommended as it is more comprehensive.

---

## Step 2: Submit Scoring Request to LLM

### Recommended Reviewer Models
- **Primary**: Claude Opus 4.5 (best at long-document comparative analysis)
- **Alternative**: GPT-5.2 Pro, Gemini 2.5 Pro

### Submission Content
1. First send the **complete content** of `scoring_prompt.md`
2. Then upload 5 PDF files, clearly labeling each:
   - "Report 1: DeepSeek-R1" + upload PDF
   - "Report 2: Gemini 2.5 Pro" + upload PDF
   - "Report 3: GPT-5.2 Pro" + upload PDF
   - "Report 4: Qwen" + upload PDF
   - "Report 5: Agent-Enhanced" + upload PDF (use `report_agent-react.pdf`)

### Sample Message

```
Please act as an expert reviewer in electrochemistry and proton conductors.
Score the following 5 deep mechanism analysis reports according to the criteria below.

[Paste the full content of scoring_prompt.md]

The 5 reports are attached:
- Report 1: DeepSeek-R1
- Report 2: Gemini 2.5 Pro
- Report 3: GPT-5.2 Pro
- Report 4: Qwen (Deep Research)
- Report 5: Agent-Enhanced (our AI Agent system)

Please output the scores strictly in the required JSON format.
```

---

## Step 3: Save Scoring Results

Save the LLM's JSON response as:

```
close/paper_figure/figure4_model_comparison/scores.json
```

JSON format example:

```json
{
  "evaluations": [
    {
      "model": "DeepSeek-R1",
      "scores": {
        "D1_scientific_accuracy": 8,
        "D2_mechanistic_depth": 7,
        "D3_data_utilization": 7,
        "D4_completeness": 8,
        "D5_logical_coherence": 7,
        "D6_novelty_predictive": 6,
        "D7_presentation": 7
      },
      "weighted_total": 72.0,
      "brief_comment": "..."
    },
    {
      "model": "Gemini-2.5-Pro",
      "scores": { "..." : "..." },
      "weighted_total": 65.0,
      "brief_comment": "..."
    },
    {
      "model": "GPT-5.2-Pro",
      "scores": { "..." : "..." },
      "weighted_total": 78.0,
      "brief_comment": "..."
    },
    {
      "model": "Qwen",
      "scores": { "..." : "..." },
      "weighted_total": 70.0,
      "brief_comment": "..."
    },
    {
      "model": "Agent-Enhanced",
      "scores": { "..." : "..." },
      "weighted_total": 82.0,
      "brief_comment": "..."
    }
  ]
}
```

---

## Step 4: Generate Final Figure 4

After saving `scores.json`, come back and tell me. I will:

1. Automatically read the real scores from `scores.json`
2. Regenerate Figure 4 (radar chart + bar chart)
3. Remove the "PLACEHOLDER" watermark
4. Output in PNG + PDF format

Or you can run manually:
```bash
python close/paper_figure/figure4_model_comparison/plot_figure4_radar.py
```

---

## Scoring Dimensions Quick Reference

| Dimension | Weight | Focus |
|-----------|--------|-------|
| D1 Scientific Accuracy | 20% | Are mechanisms correct? (Grotthuss/Vehicle/Packed-acid) |
| D2 Mechanistic Depth | 20% | Goes beyond description to explain "why" |
| D3 Data Utilization | 15% | Cites specific sample IDs, Ea values, temperatures |
| D4 Completeness | 15% | All 6 required sections covered |
| D5 Logical Coherence | 10% | Logical connections between sections |
| D6 Novelty & Prediction | 10% | Specific, actionable predictions |
| D7 Presentation Quality | 10% | Publication-ready quality |

**Scoring Scale**: 5 = Average/Pass, 7 = Good, 9+ = Excellent

---

## Tips for Improving Score Reliability

1. **Multi-round review**: Have 2-3 different LLMs score independently, take the average
2. **Cross-validation**: If a model's score on any dimension differs by >2 across reviewers, review carefully
3. **Blind review**: Optionally, label reports as Report A/B/C/D/E without revealing the model source
