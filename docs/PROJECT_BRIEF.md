Yes. The prompt should make **two things non-negotiable**:

1. **It must be a Chrome Extension**, not merely a standalone Python application.
2. **The transcript must be genuinely live**, continuously updating while the YouTube video is playing.

Here is the revised prompt.

I am building a final project for my university course:

**Course:** COMP6822001 — Speech Recognition
**Project:** Final Project
**Academic Year:** 2026/2027

I want to build a **Chrome Extension for YouTube that provides a genuinely real-time live transcript and optional translation using a LOCAL speech recognition model.**

The Chrome Extension is a mandatory part of the project.

---

# 1. PROJECT CONCEPT

Build a Chrome Extension that works directly on YouTube videos and provides a **live, continuously updating transcript while the video is playing**.

The target users are:

> University students watching foreign-language educational YouTube videos who need real-time transcription and translation to understand and review lectures.

Example:

A student watches a Japanese computer-science lecture on YouTube.

The system should:

YouTube video
↓
Capture/receive audio continuously
↓
Local speech recognition
↓
Generate partial transcript
↓
Update transcript continuously
↓
Optionally translate transcript locally
↓
Display live transcript inside the Chrome Extension / YouTube page

The application must NOT wait for the entire video to finish.

---

# 2. NON-NEGOTIABLE REQUIREMENT: CHROME EXTENSION

The final application MUST be a **Chrome Extension**.

Use:

* Chrome/Chromium
* Chrome Extension Manifest V3
* JavaScript
* HTML
* CSS

The extension must be installable through:

Chrome
→ chrome://extensions
→ Developer Mode
→ Load Unpacked

The extension should eventually be structured so it can be packaged and submitted to the Chrome Web Store.

Do NOT build only a Python desktop application.

Python may be used as a LOCAL backend for the machine-learning components, but the user-facing application must be a Chrome Extension.

Architecture:

Chrome Extension
↓
Local Backend
↓
Local ASR Model
↓
Transcript
↓
Chrome Extension
↓
YouTube UI

---

# 3. NON-NEGOTIABLE REQUIREMENT: LIVE TRANSCRIPT

The transcript MUST be genuinely real-time.

The required behavior is:

YouTube video starts
↓
Audio is continuously processed
↓
ASR receives short audio chunks/windows
↓
Partial transcription is generated
↓
Transcript is immediately sent to the extension
↓
Extension updates the transcript
↓
New speech continues processing

Example:

Speaker says:

"Today we are going to discuss convolutional neural networks."

The UI should progressively show something similar to:

"Today..."

then:

"Today we are..."

then:

"Today we are going to..."

then:

"Today we are going to discuss..."

then:

"Today we are going to discuss convolutional neural networks."

The exact behavior depends on the chosen ASR model, but the system must demonstrate continuous/intermediate transcription.

---

# 4. PROHIBITED IMPLEMENTATION

Do NOT implement:

Record entire video
↓
Wait for video to finish
↓
Extract entire audio
↓
Run ASR
↓
Display transcript

That is NOT real-time and will violate the assignment.

Also do not simply generate a transcript once and pretend it is live.

The implementation must actually process speech continuously.

---

# 5. LOCAL ASR REQUIREMENT

The speech recognition model MUST run locally.

External/cloud ASR APIs are prohibited.

Do NOT use:

* Google Speech-to-Text
* Microsoft Azure Speech
* Amazon Transcribe
* OpenAI Speech API
* AssemblyAI
* other cloud ASR services

Allowed:

* PyTorch
* Hugging Face
* torchaudio
* librosa
* FFmpeg
* ONNX
* Whisper
* faster-whisper
* Whisper.cpp
* other open-source/local ASR models

The model must execute on my computer.

My hardware:

* NVIDIA RTX 3060 Ti 8 GB
* Intel Core i5-12600K
* approximately 61 GB RAM
* Ubuntu Linux

Select a model that can realistically operate on this hardware.

---

# 6. IMPORTANT: YOUTUBE AUDIO PIPELINE

The extension is intended to work with YouTube videos.

Design the system so that it can obtain/process the audio needed for continuous ASR without requiring the user to manually download the entire video first.

Investigate technically appropriate browser-side approaches for obtaining audio from the currently playing YouTube video while respecting browser security restrictions and the assignment requirements.

Do not assume that the extension can freely access YouTube's internal media stream.

If browser restrictions prevent a direct approach, design an appropriate local architecture and clearly explain the limitation and workaround.

---

# 7. LIVE TRANSCRIPT UI

The extension must display a transcript while the video plays.

Example:

┌───────────────────────────────────────────────┐
│                                               │
│                 YouTube Video                 │
│                                               │
│                                               │
└───────────────────────────────────────────────┘

LIVE TRANSCRIPT
───────────────────────────────────────────────

00:12
Today we're going to discuss convolutional
neural networks.

00:17
A convolutional neural network is a type of
deep learning model...

The transcript should:

* update automatically
* follow the current video timestamp
* highlight the currently spoken sentence
* automatically scroll
* preserve timestamps
* allow clicking a sentence to jump to that timestamp
* distinguish partial text from finalized text where possible

---

# 8. SUBTITLE MODE

The extension should optionally display the live transcript directly over the YouTube video.

Example:

```
                ┌──────────────────────┐
                │                      │
                │    YouTube Video     │
                │                      │
                │ "Today we're going   │
                │  to discuss CNNs."   │
                └──────────────────────┘
```

Provide controls for:

* Enable/disable live subtitles
* Font size
* Position
* Background opacity
* Original transcript
* Translation
* Original + translation

---

# 9. TRANSLATION

Translation is an additional feature.

The main academic focus is LOCAL real-time speech recognition.

After obtaining the local ASR transcript:

Local ASR
↓
Original transcript
↓
Local translation model
↓
Translated transcript

Use a pretrained LOCAL multilingual translation model.

Do not use cloud translation APIs if they violate the local-processing requirement.

Example:

Original:

今日は東京に行きます。

Translation:

I'm going to Tokyo today.

The translation must preserve the transcript's timestamps.

---

# 10. TARGET LANGUAGES

The extension should allow the user to select a target language.

Example:

Target language:

[ English ▼ ]

Possible languages:

* English
* Indonesian
* Japanese
* Korean
* Chinese
* Spanish
* German

The initial implementation does not need to support every language in existence.

Prioritize languages that can be reliably handled by the selected local models.

---

# 11. LANGUAGE DETECTION

The system should automatically detect the source language where possible.

Example:

Japanese speech
↓
Japanese detected
↓
Japanese transcript
↓
English translation

Provide manual language selection as a fallback.

---

# 12. CHROME EXTENSION ARCHITECTURE

Use a structure similar to:

youtube-auto-translator/
│
├── extension/
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   ├── popup.html
│   ├── popup.js
│   ├── styles.css
│   └── icons/
│
├── backend/
│   ├── main.py
│   ├── streaming_asr.py
│   ├── transcript.py
│   ├── translator.py
│   ├── language.py
│   ├── latency.py
│   └── database.py
│
├── data/
├── models/
├── experiments/
├── tests/
├── README.md
├── requirements.txt
└── .gitignore

Improve this structure when necessary.

---

# 13. COMMUNICATION BETWEEN EXTENSION AND LOCAL ASR

Design a low-latency communication mechanism between the Chrome Extension and the local backend.

Possible architecture:

Chrome Extension
↓
WebSocket
↓
localhost Python server
↓
Streaming audio
↓
Local ASR
↓
Partial transcript
↓
WebSocket
↓
Chrome Extension

Prefer WebSocket or another appropriate streaming mechanism over repeatedly making independent HTTP requests if that provides better real-time performance.

The system should minimize transcription latency.

---

# 14. DATA REQUIREMENTS

We need actual experimental data.

Use appropriate open speech datasets.

Possible datasets to investigate:

* LibriSpeech
* Mozilla Common Voice
* FLEURS
* VoxPopuli
* other appropriate datasets

Compare the datasets before selecting one.

The experimental dataset must provide:

Audio
+
Ground-truth transcript

Do not fabricate data.

---

# 15. EXPERIMENTAL CONDITIONS

At minimum:

### Condition A — Clean Speech

Use:

* quiet environment
* normal speaking speed
* good microphone
* clear speech

### Condition B — Experimental Variable

Introduce at least one controlled variable.

Recommended:

Background noise.

Then compare:

Clean speech
vs.
Noisy speech

Measure:

* WER
* latency
* real-time factor

---

# 16. WORD ERROR RATE

Calculate:

WER = (S + D + I) / N

Where:

S = substitutions
D = deletions
I = insertions
N = number of words in the reference

Report WER for each experimental condition.

Do not fabricate WER values.

All results must come from actual model output.

---

# 17. LATENCY

Measure live transcription latency.

For example:

Speech occurs:
10.000 seconds

Transcript appears:
10.750 seconds

Latency:
750 ms

Collect many measurements.

Report:

* mean
* median
* minimum
* maximum
* standard deviation

Also calculate:

RTF = processing time / audio duration

Explain whether the system is capable of real-time operation.

---

# 18. ERROR ANALYSIS

Analyze actual recognition errors.

Classify:

* substitutions
* deletions
* insertions

Pay special attention to:

* technical terminology
* proper nouns
* accents
* fast speech
* background noise
* similar-sounding words

Example:

Ground truth:

"convolutional neural network"

Prediction:

"conventional neural network"

Analyze this as an actual substitution error.

Do not invent error examples.

---

# 19. YOUTUBE APPLICATION TEST SET

Create a small test set of real YouTube educational videos.

Record:

* video ID
* language
* category
* duration
* caption availability
* audio characteristics

Example:

| Language   | Category                 |
| ---------- | ------------------------ |
| Japanese   | Computer Science Lecture |
| Korean     | Educational Lecture      |
| English    | Programming Tutorial     |
| Indonesian | University Lecture       |
| Spanish    | Educational Video        |

Use these videos to test the actual Chrome Extension.

---

# 20. USER TESTING

The assignment requires at least:

**5 real target users.**

Target:

University students who watch educational YouTube videos, especially foreign-language content.

Users should perform realistic tasks:

1. Open a YouTube educational video.
2. Enable the extension.
3. Watch live transcription appear.
4. Enable translation.
5. Change target language.
6. Search transcript.
7. Click a transcript timestamp.
8. Evaluate usefulness.

Collect real responses.

Do NOT use AI to generate:

* fake users
* fake interviews
* fake survey responses
* fake usability scores

---

# 21. USER EVALUATION

Collect ratings such as:

1–5 scale:

* Transcript readability
* Transcript accuracy
* Transcript responsiveness
* Translation usefulness
* Ease of use
* Overall usefulness
* Willingness to use the extension for studying

Analyze the actual responses.

---

# 22. DATABASE/CACHING

Use SQLite or another appropriate local database to cache:

* video ID
* source language
* target language
* transcript
* timestamps
* translations
* processing status

Avoid retranscribing the same content unnecessarily.

However, caching must not compromise the demonstration of real-time processing.

---

# 23. REPORT

The final report must follow exactly:

## 1. Introduction

* background
* real-world problem
* target user
* objectives
* scope

## 2. Speech Recognition Fundamentals

* ASR fundamentals
* speech recognition pipeline
* chosen model
* model architecture
* streaming inference

## 3. System Design

* Chrome Extension architecture
* backend architecture
* streaming pipeline
* data flow
* UI

## 4. Implementation

* hardware
* software
* model
* Chrome Extension
* backend
* implementation decisions

## 5. Technical Experiment

* dataset
* baseline
* experimental condition
* WER
* latency
* RTF
* error analysis

## 6. User Testing

* 5+ real users
* profiles
* tasks
* testing procedure
* raw results
* usability analysis

## 7. Discussion

* technical results
* user feedback
* strengths
* weaknesses
* latency
* recognition errors
* limitations

## 8. Conclusion

* findings
* objective completion
* limitations
* future work

---

# 24. AI USAGE

AI assistance is allowed up to 50% of the project process.

Maintain an AI usage log from the beginning.

Use:

| Tool | Purpose | Prompt Summary | Output Used | Student Verification |
| ---- | ------- | -------------- | ----------- | -------------------- |

Every AI-generated result must be personally verified and tested.

AI MUST NOT generate or fabricate:

* WER results
* latency measurements
* user testing results
* interview responses
* survey responses
* experimental conclusions presented as measurements

---

# 25. DEVELOPMENT ORDER

Do not build the entire system at once.

Build in this order:

### Stage 1 — Chrome Extension

1. Create Manifest V3 extension.
2. Load it into Chrome.
3. Detect YouTube pages.
4. Detect the current video.
5. Create a transcript sidebar.
6. Verify that the sidebar works correctly.

### Stage 2 — Local Backend

7. Create Python virtual environment.
8. Create FastAPI/local backend.
9. Establish Extension ↔ localhost communication.
10. Establish WebSocket communication.

### Stage 3 — Local ASR

11. Select ASR model.
12. Install model locally.
13. Test offline inference.
14. Implement streaming/chunked inference.
15. Generate partial transcripts.
16. Send partial transcripts to the extension.
17. Display them live.

### Stage 4 — Synchronization

18. Synchronize transcript with YouTube playback.
19. Highlight current sentence.
20. Implement timestamp seeking.
21. Measure transcription latency.

### Stage 5 — Translation

22. Add local translation model.
23. Add language detection.
24. Translate partial/finalized transcript.
25. Display translated subtitles.

### Stage 6 — Evaluation

26. Prepare speech dataset.
27. Prepare ground-truth transcripts.
28. Run clean-condition experiment.
29. Run noisy-condition experiment.
30. Calculate WER.
31. Calculate latency.
32. Calculate RTF.
33. Perform error analysis.

### Stage 7 — User Testing

34. Recruit at least 5 real target users.
35. Run defined tasks.
36. Collect real feedback.
37. Analyze usability.

### Stage 8 — Finalization

38. Improve performance.
39. Document limitations.
40. Prepare architecture diagrams.
41. Prepare experiment results.
42. Prepare AI usage log.
43. Write final report.
44. Package Chrome Extension.

---

# 26. PRIORITY

Prioritize the following in this order:

1. **Real-time local ASR**
2. **Live transcript inside Chrome**
3. **Low transcription latency**
4. **WER evaluation**
5. **Controlled experimental evaluation**
6. **User testing**
7. **Translation**
8. **Additional UI features**

Do not sacrifice real-time ASR quality to add unnecessary features.

The final project must clearly demonstrate:

**YouTube → Chrome Extension → Continuous Audio → Local ASR → Live Partial Transcript → Optional Local Translation → Live Display**

This must be a genuine working Chrome Extension, not merely a Python speech-recognition demo.

This framing is much closer to the rubric. **The live transcript is now the central feature**, while translation is secondary. That is important because your professor is grading the speech-recognition system, not primarily the translation system.
