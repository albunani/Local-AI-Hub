# Screenshots folder

Drop your renamed screenshot files directly into this folder (same level as
this file). The main README references these exact filenames — rename your
captures to match before committing, using the mapping below.

## Rename mapping (Windows PowerShell/CMD commands)

Run these from inside your `screenshots` folder. Adjust the right-hand side
if any of your guessed tab mappings below turn out to be wrong — the
important part is that the **left-hand names below end up existing**,
since those are what `README.md` links to.

```powershell
ren home.png home.png
ren Education.png education.png
ren Model-selector.png model-selector.png
ren Ollama-Connected.png ollama-connected.png
ren agriculture.png agriculture.png
ren Emergency.png emergency.png
ren study-workflow-0.png study-workflow-summary.png
ren study-workflow-1.png study-workflow-flashcards.png
ren "study-workflow-2 (1).png" study-workflow-quiz-question.png
ren "study-workflow-2 (2).png" study-workflow-quiz-result.png
ren study-workflow-3.png study-workflow-exam.png
```

**The guess above for the 5 `study-workflow-*` files is:** 0 = Summary tab,
1 = Flashcards tab, 2(1) = Quiz question view, 2(2) = Quiz graded result,
3 = Generate Exam tab — based on the order they were likely captured in
while clicking through the four Education tabs. Open each file and confirm;
if the order doesn't match, just adjust which original file maps to which
new name in the commands above before running them.

## Still missing — need to be captured fresh

- **`healthcare.png`** — a screenshot of the Healthcare assistant screen
  (not present in the current screenshots folder at all yet)
- **`knowledge-used.png`** — a screenshot with the "📚 Knowledge used for
  this answer" expander open under a generated result, showing the actual
  transparency text (e.g. "Used the full document in a single pass...")

## Full expected file list once done

```
screenshots/
├── home.png
├── education.png
├── healthcare.png                    ← capture this
├── agriculture.png
├── emergency.png
├── ollama-connected.png
├── model-selector.png
├── knowledge-used.png                ← capture this
├── study-workflow-summary.png
├── study-workflow-flashcards.png
├── study-workflow-quiz-question.png
├── study-workflow-quiz-result.png
└── study-workflow-exam.png
```

Delete this file once your screenshots are all in place.
