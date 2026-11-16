---
name: "nexus-presolicitation-brief"
description: "Pre-solicitation protest risk brief built on the Bid Protest Nexus MCP. Use whenever the user describes a planned evaluation scheme, source selection plan, Section M, or award method (best-value tradeoff, LPTA, task order, FSS or BPA order) and wants to know what GAO sustains on setups like it, or says things like 'protest-proof my evaluation plan', 'run a Nexus brief', 'pre-solicitation protest check', 'what sinks tradeoffs like this', or 'what should the file show before we release the RFP'. Pulls sustained and contrasting GAO decisions and returns a short Word brief with fixes to make before release and a documentation checklist."
---

# Nexus Pre-Solicitation Brief

Build a short protest risk brief for a planned source selection before the solicitation goes out. The user describes how they plan to evaluate and award. You pull GAO decisions on similar setups from the Bid Protest Nexus MCP, both sustained protests and denials where the agency's record held up, and turn them into two things a contracting officer can act on: changes to make to the solicitation while it can still be changed, and a list of what the evaluation file needs to show.

Why before release: most sustained protests trace back to something the agency wrote or failed to write. Criteria the solicitation never stated, a tradeoff nobody explained, a weakness with nothing behind it. Those are cheap to prevent at the drafting stage and expensive to fix after award.

## Scope

Use this for a planned evaluation scheme at any point before proposals are evaluated: acquisition planning, drafting Sections L and M, writing the source selection plan, or a last check before release.

Do not use it to score or review proposals, to answer a protest that has been filed, or to give a legal opinion. The corpus holds GAO decisions only, so it cannot speak to the Court of Federal Claims or the Federal Circuit.

## Ground rules

These matter more than any step below, so read them first.

1. **Nexus is the only source for decisions.** Every B-number in the brief must come from a Nexus tool result in this session. Do not add decisions from memory or from a web search, even ones you are sure about. This brief may be pasted into a contract file or forwarded to counsel, and GAO has sanctioned filers over citations that did not check out. A brief with one wrong citation is worse than no brief.
2. **Disposition comes from `outcome_assessed`.** Summaries, issues, key points, and synopses in Nexus are model-generated. Paraphrase them, attribute them to the decision, and never present them as quotations from GAO. Stay with what `reasoning` says happened, and leave out legal labels or advice aimed at protesters that the generated text sometimes adds. Tell the reader to open each decision before citing it in a memo.
3. **Check which ground was sustained.** A decision labeled sustained can deny most of its grounds. Use a decision as a sustain example for a risk area only if the sustained ground is that risk area. Read `reasoning` and `outcome_rationale` to confirm.
4. **No counts, rates, or predictions.** Search returns the nearest matches, not every match, so you cannot say how often GAO sustains something or how many decisions exist. Say "examples include". Never call a plan protest-proof or estimate the odds of a protest.
5. **Keep the input generic.** Work from a description: method, factor names, relative weights, vehicle, rough dollar range. Do not ask for the source selection plan, the technical evaluation plan, the IGCE, or the draft solicitation. Source selection plans and technical evaluation plans are source selection information, and an unreleased solicitation is procurement sensitive. If the user pastes or uploads one anyway, use only what you need, do not quote it back, and remind them once to confirm the platform is approved for that material. No offeror names, proposal content, or prices belong in this workflow.
6. **Research aid, not legal advice.** Say so in the brief and suggest counsel review for anything headed into a legal memo.

## Workflow

A five-area brief takes about 25 to 30 Nexus calls. Batch the searches and the decision lookups so they run together.

### 1. Preflight

Confirm the Bid Protest Nexus tools are available: `corpus_info`, `search_decisions`, `get_decision`, `find_similar_decisions`, `get_similarity_synopsis`. The names may carry a connector prefix. If they are missing, tell the user the Bid Protest Nexus connector is not connected (it is published at acqagent.ai) and stop. Do not fall back to memory or the web.

Call `corpus_info` once. Note `built_at` and the decision count for the brief's coverage line, and check the outcome labels and filter rules. If the tool descriptions or `corpus_info` disagree with anything in this file, they are right and this file is stale.

### 2. Capture the scheme

Pull what you can from the user's message first. You need enough to choose risk areas:

| Need | Examples | If missing |
|---|---|---|
| Procedure and vehicle | Negotiated procurement, task or delivery order under a multiple-award IDIQ, Federal Supply Schedule order or BPA, simplified acquisition | Ask |
| Award method | Best-value tradeoff, LPTA, highest technically rated with fair and reasonable price, comparative analysis | Ask |
| Factors and relative importance | Technical approach, key personnel, corporate experience, past performance, price. Which outweigh which | Ask |
| Price or cost evaluation | Reasonableness only, realism reserved or required, cost realism, unbalanced pricing | Assume reasonableness only and say so |
| Rating method | Adjectival, confidence ratings, pass/fail | Assume adjectival |
| Exchanges | Award without discussions, discussions planned, oral presentations | Assume award without discussions |
| Agency, set-aside status, dollar range, contract type | HHS, total small business, about $40M, fixed-price | Proceed without, note it |

Ask at most one round of questions, and only for the first three rows, because those change which decisions are relevant. Use the session's question tool if it has one. If the user says to just run it, proceed and list your assumptions at the top of the brief.

### 3. Choose four to six risk areas

Map the scheme's features to risk areas using the lens library below. Always include the two that apply to nearly every competitive award: evaluation against the stated criteria, and the award decision rationale (the tradeoff for best value, the acceptability call for LPTA). Then add the ones the scheme's features point to. More than six produces a brief nobody reads.

### 4. Search

For each risk area run two searches, in parallel where you can:

- **Sustained pass**: `search_decisions` with the lens query, `outcome` set to `sustained`, `year_min` set to the current year minus 12, `limit` 8.
- **Contrast pass**: the same query with `outcome` set to `denied`, `limit` 5. Denials show what an adequate record looked like, which is more useful to a contracting officer than sustains alone.

If the agency is known, add one **agency pass**: a short description of the evaluation, the `agency` filter, `outcome` set to `sustained`, and `year_min` at the current year minus 8. Decisions against the user's own agency get attention.

What testing against the live corpus showed:

- **One issue per query, in GAO's vocabulary.** "Best-value tradeoff decision inadequately documented; source selection authority did not explain why the higher-priced proposal was worth the price premium" works. Queries that stack several issues, or that describe the kind of protest instead of the facts, drift to generic evaluation cases. If results drift, shorten the query.
- **Put the vehicle in the query text, not the `vehicle` filter.** The filter keeps only decisions whose issues or key points mention the vehicle, which cuts the pool hard and pulls in off-topic results. Use the filter only where the lens library says it helps, or as a second pass when a vehicle-specific risk area comes back thin.
- **Similarity scores are not comparable** across queries or between search and neighbor lookups. Judge relevance by reading `core_issue` and `summary`.
- **Agency names are inconsistent** (with and without abbreviations, some blank). Filter on a distinctive substring such as "Health and Human" or "Veterans". Sub-agencies such as CMS or NIH appear in summaries, not in the agency field, so put them in the query text.
- **Expect filler.** The sustained pool is small, a few hundred decisions in a 12-year window, and search always returns the number you ask for. A narrow issue gives one to three decisions that are on point, then loosely related ones. Keep the first kind and drop the rest.
- **Thin results**: add a pass with `outcome` set to `sustained_in_part`, then widen the year window, then rephrase. If a risk area still has nothing on point, say so in the brief. Do not pad it with loosely related decisions.
- **Record types**: reconsiderations and advisory opinions show up in results. Skip them unless they are squarely on point, and label them if you cite one.
- **Same procurement, several decisions**: suffixes such as .3, .5, .6 on one B-number, decided around the same date, are usually separate protesters on one award. Treat them as one example.
- **Dismissals** are usually about timeliness or standing and teach nothing about evaluation. Keep one only when its reasoning is the lesson, for example a realism challenge dismissed because the solicitation never promised a realism analysis.

### 5. Read the finalists

Shortlist one or two sustains and one contrast for each risk area, which comes to roughly ten to fifteen decisions. Prefer the same procedure and vehicle, recent years, and the user's agency.

Call `get_decision` on every decision you plan to cite, in parallel. Do not cite from a search summary alone. Use `reasoning`, `outcome_rationale`, and `key_points` to pin down what the record lacked or showed. When the agency field is empty, take the agency from the summary. Take the link from `source_url`. When it is empty, give the B-number and date and tell the reader to look it up on gao.gov. Do not build a link yourself.

Each `get_decision` result lists five neighboring decisions with their outcomes. Check them for two things:

- **A later decision on the same procurement.** A sustain followed by a denial under the same B-number root, after corrective action, shows what the repaired record looked like. That pair is the best contrast you can give.
- **A close neighbor that went the other way.** For the one or two sustains that fit the scheme best, you can also call `find_similar_decisions` with `opposite_outcome` set to true and a recent `year_min` (add `exclude_same_docket` when you want a different procurement), or `get_similarity_synopsis` with `include_passages` set to false.

The synopsis line on practical use and some key points are written for someone arguing a protest. Turn them around: what would the agency have needed in the file for the result to flip?

### 6. Write the brief

Follow the template below. Aim for two pages, three at most. If it runs long, cut a risk area before you cut the checklists.

Writing rules:

- Every statement about what GAO did carries a B-number and year.
- If the agency pass turned up a sustain on point, lead a bottom-line item with it. A loss at the reader's own agency is the fastest way to get the fix made.
- Every checklist item traces to at least one cited decision. If you add a general good-practice item with no decision behind it, label it "general practice" and keep those few.
- "Fix before release" items change the solicitation or the evaluation plan. "Put in the file" items are what evaluators and the selecting official write down during evaluation. Keep them separate, because the first kind expires the day the solicitation is released.
- Be specific. "Define relevant experience in Section M, including any size or scope yardstick the evaluators will use" beats "ensure criteria are clear".
- Plain language, no legal Latin, no hedging beyond the standing caveats.

### 7. Deliver

Default to a Word document (.docx), because that is what goes in a contract file. If the session has a docx skill, read it before building. Name the file `Nexus_Brief_[short name]_[YYYY-MM-DD].docx`. If the user asks for a different format, use that.

In the chat, give the bottom line in three bullets and one line on anything the search could not support. Do not restate the whole brief.

Offer one next step that fits: rerun after they change the scheme (redo only the affected risk areas), or go deeper on one risk area.

## Lens library

Pick by feature. The query starters are tested phrasings. Adapt the nouns to the scheme (for example "corporate experience" instead of "past performance") and add the procedure in plain words when it matters ("in a task order competition").

| Scheme feature | Risk area | Query starter |
|---|---|---|
| Any competitive award | Evaluation against the stated criteria | evaluation applied unstated evaluation criteria that the solicitation did not disclose |
| Any competitive award | Findings supported by the record | weakness assigned to the proposal was not supported by the contemporaneous evaluation record |
| Any competitive award | Equal treatment | disparate treatment: agency credited the awardee with a strength for a feature the protester also proposed |
| Best-value tradeoff | Tradeoff rationale | best-value tradeoff decision inadequately documented; source selection authority did not explain why the higher-priced proposal was worth the price premium |
| Tradeoff with ratings | Ratings used mechanically | source selection decision relied on adjectival ratings without a qualitative comparison of proposals |
| LPTA | Acceptability calls | proposal found technically unacceptable for reasons not contemplated by the solicitation's evaluation criteria |
| LPTA | Awardee held to the requirements | awardee's proposal did not comply with a material solicitation requirement |
| Highest technically rated, or price is a minor factor | Price given real weight | tradeoff was mechanical and failed to meaningfully consider price (overlaps the tradeoff lenses; few decisions use the highest-technically-rated label) |
| Corporate experience, past performance | Relevance | past performance relevance determination was inconsistent with the solicitation's definition of relevant |
| Corporate experience, past performance | Whose experience counts | agency credited offeror with the experience of an affiliate or subcontractor without a basis in the proposal |
| Key personnel | Availability and commitment | key personnel became unavailable after proposal submission and the offeror did not notify the agency |
| Fixed-price | Price realism | price realism analysis the solicitation provided for was not performed or was unreasonable |
| Fixed-price | Price reasonableness | agency failed to reasonably determine that the awardee's price was fair and reasonable |
| Cost-type | Cost realism | cost realism analysis was unreasonable; agency did not document adjustments to proposed costs |
| Discussions or exchanges planned | Meaningful and equal | discussions were not meaningful or were unequal; only one offeror was allowed to revise its proposal |
| Oral presentations | Record of orals | agency did not keep an adequate record of oral presentations (recent decisions are few, so widen the year window) |
| Order under a multiple-award IDIQ | Scope and fair opportunity | task order exceeded the scope of the underlying contract |
| FSS order or BPA | Schedule scope | order included labor categories or items not on the vendor's Federal Supply Schedule contract |
| Not set aside | Set-aside decision | decision not to set aside for small businesses was not supported by market research |
| Sole source or brand name | Justification | justification for sole-source award was unreasonable (here the `vehicle` filter set to `sole-source` helps) |
| Incumbent, advisors, or support contractors involved | Conflicts of interest | contracting officer failed to meaningfully consider an organizational conflict of interest |
| Complex instructions, page limits, definitions | Solicitation ambiguity | latent ambiguity in the solicitation (add the subject, such as page limits or relevant experience) |
| Down-select or competitive range | Exclusion decisions | exclusion from the competitive range was unreasonable or undocumented |

## Brief template

```
PRE-SOLICITATION PROTEST RISK BRIEF
[Generic requirement name] | Prepared [date] | Planning aid for the contracting officer

SCHEME AS UNDERSTOOD
- Procedure and vehicle:
- Award method:
- Factors and relative importance:
- Price or cost evaluation:
- Assumptions made:

BOTTOM LINE
Three short items. One per top risk, each ending with the fix.
Protest forum: one line, only for orders (see the note on order protests).

RISK AREAS  (most important first, one block each)
[Risk area name]
- What sank the agency: the pattern in one or two sentences (B-number, year; B-number, year).
- Where the record held: one sentence on a denial and what the file showed (B-number, year).
- Fix before release: the specific change to the solicitation or evaluation plan.
- Put in the file: what evaluators and the selecting official should write down.

DECISIONS CITED
Table: B-number | Date | Agency | Outcome | Risk area | Link

BEFORE RELEASE CHECKLIST
[ ] Item (B-number)

DURING EVALUATION CHECKLIST
[ ] Item (B-number)

READ BEFORE YOU RELY ON THIS
- Source: Bid Protest Nexus, corpus built [built_at date], [count] GAO decisions. GAO only, no court decisions.
- Case descriptions are AI-generated summaries. Open each decision before citing it.
- Decisions apply the FAR text in force when they were decided. Confirm current section numbers and wording against your agency's FAR overhaul deviations.
- Research aid, not legal advice.
```

## Two notes that keep the brief honest

**FAR overhaul.** Most decisions in the corpus predate the Revolutionary FAR Overhaul. The principles carry over, but section numbers and some wording have moved or changed in the deviation text agencies have adopted, including in the parts that govern orders, commercial buys, and source selection. Cite the decision and the principle. Do not state a current FAR section number from memory. If the user has a clause or deviation tool available, point them to it for the current text.

**Order protests.** If the buy is a task or delivery order under a multiple-award IDIQ, GAO can hear a protest only above a statutory dollar threshold, which differs for civilian and defense agencies, or when the protest says the order exceeds the scope, period, or maximum value of the contract. Orders against the Federal Supply Schedule are not subject to that threshold. Mention this in one line when it applies. The thresholds change, so state a number only if you can confirm it from a current authoritative source in this session. Otherwise tell the user to confirm it with counsel.

## Example of one finished risk block

Decision numbers are left as placeholders on purpose. Always pull your own.

```
Corporate experience: evaluate what Section M says
- What sank the agency: evaluators measured experience against a size threshold the solicitation never mentioned (B-4XXXXX, 2018), and in another case reached conclusions about experience that contradicted each other within the same report (B-4XXXXX, 2026).
- Where the record held: the solicitation defined relevant experience by scope and complexity, and the report tied each rating to those terms (B-4XXXXX, 2023).
- Fix before release: put the yardstick in Section M. If size, recency, or prime-versus-subcontractor role will matter, say so and say how.
- Put in the file: for each reference, the stated criterion it was measured against and why it did or did not meet it. Have one person read the consensus report end to end for contradictions.
```