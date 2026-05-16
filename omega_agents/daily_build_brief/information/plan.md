# daily_build_brief — Plan

## Current Plan (v1)
1. Scan project root for `*_DONE.md` files (glob pattern)
2. Read `git log --oneline -20`
3. Run `python -m pytest tests/ --tb=no -q` and capture count line
4. Read CLAUDE.md Section 9 for next priority
5. Format and return markdown brief

## Future Enhancements
- Auto-post brief to a Slack channel (when Hermes is integrated)
- Compare with previous day's brief to highlight velocity
- Add Modal cron trigger for automated daily run
