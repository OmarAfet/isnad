# Interface copy: plan and decisions

## Register — decided 2026-10-05

**White Saudi dialect**, chosen by Omar (team lead) over simple MSA and mixed.

Recorded trade-off, raised at decision time: the content is Quran and hadith, the users include
non-Saudi du'ah and new Muslims, and the committee includes Shariah reviewers, so simple MSA was
recommended. Omar chose dialect. Scope of the decision: interface copy only. Scripture, references,
grading terms (صحيح، ضعيف، موضوع) and scholars' names are data and are shown exactly as the sources
print them, never paraphrased into dialect.

Shared dialect words only (فيه، اللي، وش، تقدر، عشان، الحين، بس، قبل لا), one reader addressed as
"you", the product as the subject. No «», no dashes, Western digits.

## Content plan (written in English first, per the arabic-web-copy process)

**Home.** One message: describe what you remember; get the exact text, its source and the scholars'
ruling, or an honest "not found".

| Slot | Says | Budget |
|---|---|---|
| Hero title | Remembered the meaning, forgot the words? | ≤ 6 words |
| Subtitle | Write what you remember; we return the correct text with source and grade | ≤ 14 |
| Placeholder | What do you remember of the verse or hadith? | question |
| Hint | Any language, any wording (the filed promise) | ≤ 5 |
| Button | Search for the text | 1 to 4 |
| Examples | Three to four queries that show paraphrase, quotation, another language | chips |

**Result, drawn as a chain.** Your description → the text → the source → the ruling. Labels are single
words. The match percentage is labelled as match-to-description, never as authenticity.

**States.** Found, likely, unsure, not found, too vague, fatwa request, service down, network error,
rate limited. Each says what happened and what to do next. Errors do not apologise.

**Warnings that must never be softened.** Weak: do not attribute it to the Prophet ﷺ as established.
Fabricated: it is a lie attributed to the Prophet ﷺ; do not spread it.

**Footer, required by the framework's transparency rule.** Isnad is AI-assisted; it selects from
verified texts and writes none; rulings are relayed with the scholar's name; Isnad issues no fatwa.

**Method page.** The only page allowed technical detail: the two stages, the models, the numbers,
the limits.

## Ruling questions — decided 2026-10-05 22:20 (session 2)

Omar's request: Isnad must not issue fatwas, but give the existing ones. His choice among three
previews: **the texts on the matter, with sources and grades, then a referral and a link to the
fiqh encyclopedia the Reference Framework approves (dorar.net/feqhia)**. Rejected: published
fatwas by named bodies (new dataset and licences; too risky before the deadline).

Grounds: the Reference Framework, level (د): "يوضح المعلومات العامة ويحيل إلى جهة مؤهلة", the
general information and a referral, not a referral alone. Approved fiqh reference: "أي كتاب معتمد
في الفقه على أحد المذاهب الفقهية الأربعة أو منصة dorar.net/feqhia", with the rule "لا تتحول إلى
فتوى شخصية أو ترجيح آلي مستقل". Isnad writes no ruling in any state.

| Slot | Says | Budget |
|---|---|---|
| Lead, general question | Here are the texts on this matter | ≤ 8 words |
| Lead, personal case | Your question is about your own case; its ruling needs a scholar who hears its details | ≤ 16 |
| Lead under it, personal | These are the general texts on the matter | ≤ 8 |
| Referral title | Isnad does not issue fatwas | ≤ 4 |
| Referral line | For the ruling in detail: | ≤ 4 |
| Link | The fiqh encyclopedia at Dorar | ≤ 5, external |
| Referral action | Ask the people of knowledge or an approved fatwa body | ≤ 9 |
| No texts found | We found no texts on this matter in Isnad's sources | ≤ 10 |

Approved preview wording (Omar, 2026-10-05): "النصوص الواردة في المسألة:" / "إسناد ما يفتي.
للحكم بالتفصيل:" / "الموسوعة الفقهية (الدرر السنية)" / "اسأل أهل العلم أو جهة إفتاء معتمدة".
