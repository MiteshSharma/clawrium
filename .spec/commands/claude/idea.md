---
description: Capture raw idea/thoughts and create new issue
---

You are capturing raw thoughts and ideas for Clawrium.

## Context
@.spec/CONTRIBUTING.md

## Template
@.spec/templates/idea.md

## Your Task

1. Generate a unique issue ID: `YYMMDD-XXX` (date + 3 random lowercase chars)
2. Create directory: `.spec/<issue>/`
3. Create `.spec/<issue>/idea.md` with the user's raw thoughts
4. **Iterate with the user** using Socratic questions until all main sections are filled
5. Ask user what they want to do next: create spec or file GitHub issue

## Workflow

### Phase 1: Capture Raw Idea

1. Listen to user's initial idea (from $ARGUMENTS or ask)
2. Generate issue ID (e.g., `260323-abc`)
3. Create the issue folder and idea.md with raw thoughts

### Phase 2: Socratic Exploration (Iterate)

Work through each section of the template with the user:

1. **Customer Value** - Who has this problem? What's the impact?
2. **Pain Point Analysis** - What's broken? How often? Workarounds?
3. **Existing Solutions** - What exists? Why isn't it enough?
4. **Timing & Priority** - Why now? What if we don't?

For each section:
- Ask the questions from the template
- Wait for user response
- Update idea.md with answers
- Move to next section

**Keep iterating until:**
- [ ] Customer value is clear (who + impact)
- [ ] Pain point is specific and frequent
- [ ] Existing solutions are evaluated
- [ ] Timing justification exists
- [ ] Initial scope has 2-4 concrete items

### Phase 3: Next Steps

Once sections are complete, ask the user:

```
Idea exploration complete!

What would you like to do next?
1. Create detailed spec: /clawrium:write-spec <issue>
2. File GitHub issue directly (for smaller/simpler items)
3. Keep refining this idea
```

## Output Format

After each update to idea.md:
```
Updated: .spec/<issue>/idea.md

Sections complete: X/4
- [x] Customer Value
- [ ] Pain Point Analysis  <-- current
- [ ] Existing Solutions
- [ ] Timing & Priority

Next question: <question from current section>
```

## Prompt Log

Add to the Prompt Log section:
- model: (current model)
- date: (today)
- type: idea-capture
- prompt: (user's raw input)

$ARGUMENTS
