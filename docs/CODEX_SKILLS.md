# Useful Codex skills for this project

These recommendations use the skills available in Nikita's current session. They
are optional workflow aids, not application dependencies; teammates may have a
different installed catalog. No additional skills or plugins were installed.

Ask Codex to “use the `<name>` skill” for a specific task. In Codex CLI/IDE, `/skills`
or `$` selects a skill; ChatGPT supports `@` selection. See the
[official skill guide](https://learn.chatgpt.com/docs/build-skills).

| Skill | When it helps here | Likely owner |
| --- | --- | --- |
| `pdf:pdf` | Inspect source/delivery PDFs, extract evidence, render pages, and visually verify generated PDF artifacts and highlight alignment. | Jeff, Lucas, Rehan |
| `nextjs-developer` | Scaffold and build the Next.js/TypeScript frontend and agree API integration. | Lucas |
| `emil-design-eng` | Polish PDF inspection panes, citation navigation, review controls, loading and error states. | Lucas |
| `react-doctor` | Check React accessibility, architecture and regressions after frontend changes. | Lucas |
| `domain-modeling` | Keep shared contract terminology and CONTEXT.md precise when resolving interface questions. | Nikita + Jeff |
| `verify-this` | Verify claims such as dispute blocking, stale-approval rejection, restart idempotency, or evaluation-key isolation with concrete evidence. | Nikita, Rehan |
| `cli-for-agents` | Design deterministic corpus/evaluation CLI commands with seeds, predictable output, and useful errors when those tools are implemented. | Jeff, Rehan |
| `hack-check` | Check progress against judging criteria, identify scope drift, and update HACK.md at milestones. | Team |
| `hack-ship` | Prepare submission, README, demo access, backup plan and secret/disclosure checks near shipping. | Rehan + team |
| `hack-pitch` | Turn the working demo into a short pitch and prepare judge questions. | Rehan |
| `openai-docs` | Answer Codex setup, skills, and configuration questions using official documentation. | Anyone |

Start with `pdf:pdf` for an actual PDF fixture, `nextjs-developer` for Lucas's UI,
and `verify-this` for a concrete policy/retry claim. Use one appropriate skill for
the task instead of loading the entire list. The PDF skill is for artifact work;
it does not replace building the application's PDF viewer or evidence resolver.
OpenAI Docs does not supply Anthropic/CDP/LangGraph API documentation.

After a repeated workflow stabilizes, `skill-creator` can package it as a shared
skill. `skill-installer` can install a missing skill when explicitly requested.
There is no need to install anything to run the current backend checks.
