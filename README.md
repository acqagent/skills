# acqagent/skills

Open-source [Claude Code plugin marketplace](https://docs.claude.com/en/docs/claude-code/plugin-marketplaces) for federal-acquisition skills.

## Install (one line)

In Claude Code:

```
/plugin marketplace add acqagent/skills
/plugin install far-clause-checker@acqagent
```

That's it. The skill is installed into `~/.claude/plugins/` and auto-triggers when you ask Claude about FAR clauses, RFO compliance, set-aside applicability, or HHS deviations.

To update later:

```
/plugin marketplace update acqagent
/plugin install far-clause-checker@acqagent
```

## Available plugins

| Plugin | Version | What it does |
|--------|---------|--------------|
| [`far-clause-checker`](./plugins/far-clause-checker) | 2.1.0 | Validates FAR provisions and clauses against the Revolutionary FAR Overhaul (RFO) and HHS Agency Deviation Matrix. Produces a standalone `.docx` compliance report. FAR only; no DFARS. |

More skills are in development. See [acqagent.ai/skills](https://acqagent.ai/skills) for the full catalog.

## Repo layout

```
.
├── .claude-plugin/
│   └── marketplace.json              # marketplace manifest
├── plugins/
│   └── far-clause-checker/
│       ├── .claude-plugin/
│       │   └── plugin.json           # plugin manifest
│       ├── SKILL.md                  # skill prompt + workflow
│       ├── CHANGELOG.md              # release notes
│       ├── scripts/
│       │   └── far_checker.py        # the runner
│       └── references/
│           ├── DATA_DICTIONARY.md
│           ├── Revolutionary_FAR_Overhaul_HHS_Matrix.csv
│           └── WarU_Provision___Clause_Matrix__22_Apr_2026.xlsx
└── README.md
```

## Direct download (no marketplace needed)

If you'd rather skip the marketplace and drop the skill in by hand, [acqagent.ai/skills/far-clause-checker](https://acqagent.ai/skills/far-clause-checker) hosts both `.skill` and `.zip` bundles with full install instructions for Claude Code and claude.ai.

## Contributing

PRs welcome. To add a skill:

1. Create `plugins/<your-skill>/` with `.claude-plugin/plugin.json` and your `SKILL.md` + supporting files.
2. Add an entry to `.claude-plugin/marketplace.json`.
3. Open a PR.

For substantive workflow changes, open an issue first so we can talk it through.

## License

MIT. See individual plugin folders for plugin-specific notices.

## About AcqAgent

[AcqAgent](https://acqagent.ai) is an independent, open-source project for federal contracting practitioners. Not affiliated with any federal agency. Content is informational, not legal or contracting advice.
