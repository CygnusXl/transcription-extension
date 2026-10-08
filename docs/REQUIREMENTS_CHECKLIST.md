# Requirements Checklist — COMP6822001 Final Project

Source: `Form_Submit_Final_Project_COMP6822001.docx` (Odd term, Undergraduate, AY 2026/2027, **AI Use Type: Integrated**).
Deliverables (section 17): **(1) working real-time application, (2) technical report.** Nothing else is graded separately.

Status key: **Done** = exists in repo and verified; **Scaffolded** = skeleton only; **Planned** = designed, not built; **Student** = only you can do it (real data/people).

## Success criteria (section 19)

| Criterion | Status | Notes |
| --- | --- | --- |
| Real-world problem | Planned | Foreign-language lecture videos are hard to follow/review; write it up in report section 1 |
| Real target user | Student | Make it concrete (see "Target user" below) and recruit real people |
| Speech recognition application | Scaffolded | Extension + backend skeleton; ASR not built yet (Stage 3) |
| Works in real time | Planned | Needs tabCapture + streaming ASR; must show partial then updated text |
| Local ASR inference | Planned | faster-whisper on the RTX 3060 Ti; no cloud ASR |
| No external ASR API | Done (by design) | Nothing in the repo calls a cloud ASR service |
| Technical evaluation | Planned | Baseline + at least one experimental condition |
| User testing | Student | At least 5 real target users |
| Relevant target users | Student | Testers must match the stated target user |
| Collect user feedback | Student | Questionnaire/interview; observation notes |
| Feedback included in report | Student | Must be tied to the technical results (section 9 of the form) |
| Strengths and weaknesses analysis | Planned | Combine WER/latency with user feedback |

## Application requirements (sections 3, 10)

| Requirement | Status | Notes |
| --- | --- | --- |
| Continuous audio stream as input | Planned | Tab audio via `chrome.tabCapture` + offscreen document. See risk 1 |
| Streaming + preprocessing (16 kHz mono) | Planned | AudioWorklet downsampling |
| Inference while speech is ongoing | Planned | Sliding window, no full-recording step |
| Partial then updated transcription | Planned | Wire protocol already has `final: false/true` |
| Transcript displayed live | Scaffolded | Sidebar + overlay exist; verify in Chrome |
| Show latency and status in the UI | Planned | The form's example UI shows "Latency: 0.8 s" and "Status: Listening"; add both to the sidebar |
| Explain latency/responsiveness in report | Planned | Needs measured data |

## Experiments (sections 12-14)

| Requirement | Status | Notes |
| --- | --- | --- |
| Baseline (clean speech) | Planned | |
| At least one experimental condition | Planned | Background noise at fixed SNRs is the most relevant for lecture audio |
| WER = (S + D + I) / N | Planned | Use `jiwer`; keep scripts in `experiments/` so runs are reproducible |
| CER where WER does not apply | Planned | The form lists "WER/CER". Japanese/Chinese have no word spaces, so use CER for those |
| Real-time metric (latency / RTF) | Scaffolded | `backend/latency.py` computes summary stats and RTF; measurement harness not built |
| Error analysis table (Reference / System output / Error type) | Planned | Real model output only; look for technical terms, proper nouns, accents, noise |

## User testing (sections 6-9)

| Requirement | Status | Notes |
| --- | --- | --- |
| 5+ real target users | Student | Fewer only with lecturer approval |
| Realistic tasks | Student | Task list is in `PROJECT_BRIEF.md` section 20 |
| Observation notes | Student | |
| Questionnaire/interview/rating scale | Student | AI may help write the questions, never the answers |
| Results table (ease of use, responsiveness, transcription quality, satisfaction) | Student | |
| Analysis of feedback, linked to WER/latency | Student | |

## Report (sections 15-16, 21)

See [`REPORT_OUTLINE.md`](REPORT_OUTLINE.md) for the exact required structure. Required evidence: app screenshots, architecture diagram, experimental results, transcription examples, WER results, latency measurements, user-testing results, user feedback, analysis of feedback.

## AI usage (section 21, 10% of grade)

| Requirement | Status |
| --- | --- |
| AI Usage Log inside the report (No., AI Tool, Purpose, Prompt/Instruction Summary, Output Used, Student Verification) | Scaffolded in `AI_USAGE_LOG.md` |
| Per use: part of project helped, how output was used, how verified, student's own changes/decisions | Scaffolded |
| Empirical verification of AI output | Student |
| Be able to explain model, streaming, latency measurement, WER, and the AI-written code at demo | Student |
| AI Usage Declaration at the end of the report | Text ready in `REPORT_OUTLINE.md` |
| No AI-fabricated results, users, or feedback | Student (serious academic misconduct) |

## Risks and decisions to confirm

1. **Input type.** The form's application requirement says "Continuous microphone/audio stream". Tab audio from YouTube is an audio stream, but the form's examples are about a user speaking. To remove the risk, add a **microphone mode** to the extension (cheap, same pipeline) and/or confirm with the lecturer that tab audio qualifies.
2. **AI use type.** The form marks **Integrated** (the other types are struck through), and section 21 says AI use is encouraged with no percentage cap. The earlier brief said "up to 50%", which matches the *Partial* type, not this form. Ask the lecturer which applies. Either way, log everything and verify it.
3. **Target user concreteness.** "University students" alone is called insufficient. State something checkable, for example: *BINUS undergraduate students who watch non-English educational YouTube videos for coursework*, and recruit from exactly that group.
4. **Language of the evaluation.** WER on English (LibriSpeech or similar) is the simplest and most defensible baseline. If you also evaluate Japanese or Korean, report CER.
5. **Submission.** Submit through Exam Apps on the exam schedule. The exam date is not in the form; check it.
