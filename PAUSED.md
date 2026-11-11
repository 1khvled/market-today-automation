# PAUSED — 2026-11-11

This bot (سوق اليوم / The Market Today, page `1421089964411983`) is **turned
off on purpose**. Do not re-enable it without asking the owner.

## What was done

All seven GitHub Actions workflows were disabled server-side
(`disabled_manually`), not deleted:

| workflow | id |
|---|---|
| FB auto-post (every 20 min) | 373598582 |
| Daily stats digest | 373598581 |
| Weekly credential check | 373598580 |
| Monthly style refresh | 373598583 |
| Monthly growth snapshot | 373598585 |
| Weekly leadership audit | 373598588 |
| Token self-heal (daily) | 373598591 |

No queued or in-progress runs remained. Vercel was checked: this bot is **not
deployed there** (the account has 7 projects, none of them this one), so the
`vercel.json` cron is inert. GitHub Actions was the only live trigger.

## Why

The page had 2 followers / 2 likes after 227 posts, 0 reactions and 0 external
comments on its last 11 posts. The owner chose to keep only the English page
(Ethan Cole) running. See `../README.md` in `eight-dollar-project` for the
full picture.

## To bring it back

```
gh workflow enable 373598582 --repo 1khvled/market-today-automation
# ...and the other ids above as needed
```

Before re-enabling, read `../eight-dollar-project/README.md` §4 — the volume,
prompt and photo fixes in this repo are unverified in production because the
bot was paused before its first run with them.
