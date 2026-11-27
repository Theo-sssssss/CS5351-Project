# Group 04 Presentation Notes

Nine-slide presentation. Slides and demonstration share five minutes, followed by two minutes of Q&A and one minute for changeover. The current presentation is `submission/EvoAgent-Presentation.pptx`.

## Slide 1

0:00–0:15 | Introduce Group 04 and EvoAgent, our AI-powered pull request review assistant. Class session: Tuesday, 1 December 2026, 09:30–12:20, AC5-515. Check the separate schedule for Group 04’s exact slot. The group has five minutes total for slides and demo, followed by two minutes for Q&A and one minute for changeover.

## Slide 2

0:15–0:45 | Reviewers need to understand what changed before merging. AI can save time, but reviewers still need to check where a finding came from and whether the full diff was covered. EvoAgent addresses both needs.

## Slide 3

0:45–1:35 | Our six team members contributed 36 hours each, for a total of 216 hours across three sprints and five versions. The table shows how that time was distributed. Version 3 took the most team time, at 68 hours. Together, we built an end-to-end pull request review workflow. Specialized AI reviewers propose findings, and EvoAgent links them to the changed code so developers can check the evidence. We also track coverage and save checkpoints so unfinished reviews can resume. I’ll now show how this works on a pull request.

## Slide 4

1:35–2:20 | Walk through one PR: batch the diff, check each finding against changed-code evidence, and report coverage. Explain that checkpoints preserve progress and evaluated feedback can inform later updates.

## Slide 5

2:20–3:50 | Open the prepared local demo before class. Show a test diff with a prepared review, inspect one finding and its evidence, then show coverage and pause/resume. Rehearse the switch back to slides. If startup or model access delays the run, immediately play EvoAgent-Demo.mp4 from the handoff package. Keep playback local and return to slides by 3:50.

## Slide 6

3:50–5:00 | The current packaged-source regression run passed 89 tests after extraction on 27 November. The current-source rerun used 100 synthetic cases without a real LLM. Aggregate precision was 100 percent, recall 82.50 percent and F1 90.41 percent. On the separate 20-case holdout, F1 was 76.92 percent, with no gain from the evolved Skill. On one unlabelled public PR, the batched workflow finished while the legacy run exceeded its budget. That pilot measured completion. Close by highlighting evidence-linked findings and visible coverage, then leave the questions slide on screen.

## Slide 7

5:00–7:00 | Q&A. Related work and references follow as backup slides. 7:00–8:00 | Changeover.

## Slide 8



## Slide 9


