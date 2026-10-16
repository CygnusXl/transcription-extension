# AI Usage Log

Course form: **AI Use Type = Integrated** (section 21: AI is allowed and encouraged, but must be transparent, verified, and explainable by the student; it counts for 10% of the grade).

Not allowed (serious academic misconduct): AI-generated experiment results, WER or latency numbers, user-testing data, user responses, interview transcripts, or questionnaire answers presented as real.

Add a row for every material use. This table goes into the report. The extra columns keep the information section 21.1 asks for (which part AI helped with, and what you decided afterwards).

| No. | AI Tool | Purpose | Part of project | Prompt/Instruction Summary | Output Used | Student Verification | Student changes/decisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Claude (Claude Code) | Initial repo scaffold | Chrome extension skeleton, FastAPI/WebSocket backend skeleton, docs | Asked it to create the GitHub repo from the project brief and build the Stage 1-2 skeleton | Used as a starting point | TODO: load the extension in Chrome and confirm the sidebar appears; run the backend and confirm `/health` and the WebSocket handshake | TODO |
| 2 | Claude (Claude Code) | Requirements check | Requirements checklist and report outline | Gave it the course form and asked it to check the project against it | Used | TODO: re-read the form yourself and confirm the checklist is correct | TODO |
| 3 | Claude (Claude Code) | Implement Stage 3 and translation | Tab-audio capture (offscreen document, AudioWorklet), streaming ASR (LocalAgreement-2 over faster-whisper), NLLB translation, session/protocol, tests | Asked it to build the real-time pipeline from my idea: use the tab's internal audio, make a live transcript, translate it | Used as the implementation | TODO: run `pytest` and `node tests/worklet.test.js`; load the extension in Chrome; start a capture on a real YouTube tab; check partial text appears while the video plays; measure latency on your GPU | TODO: record what you changed or decided (model size, step length, buffer length, ...) |

Fill in the TODO cells yourself after you actually do the verification. Do not leave AI-written verification claims in this table.

## Findings from the AI's own development checks

These come from checks the AI ran in a CPU-only sandbox. They are leads, not your results. Re-run them yourself and record what you see.

- First version passed *all* committed text as Whisper's context prompt, including words still inside the audio window. A real-model run showed the last word of a sentence disappearing, because Whisper then skipped audio it believed was already transcribed. Fixed by only using text that has left the window. A fake-model test could not have found this.
- The streaming algorithm initially lost words in a unit test; the cause was the test's fake model, not the algorithm. Always check whether a failing test is wrong or the code is wrong.
- `faster_whisper.decode_audio` failed with the installed PyAV version; avoided because the backend does not use it.
- NLLB translated Korean 합성곱 신경망 as "synthetic square neural networks": a candidate technical-terminology example for the error analysis (measure it properly before citing it).
