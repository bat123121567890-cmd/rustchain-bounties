# Auto-Award RTC on PR Merge

A reusable GitHub Action that automatically rewards RTC tokens to contributors when their PR is merged.

## Quick Start

Use the action directly from BossChaos/rtc-reward-action:

```yaml
on:
  pull_request_target:
    types: [closed]

jobs:
  award-rtc:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: BossChaos/rtc-reward-action@v1.0.0
        with:
          rtc-amount: '20'
          wallet-address: 'RTC6d1f27d28961279f1034d9561c2403697eb55602'
          dry-run: 'true'
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Features

- ✅ **Configurable RTC amount** — set any reward amount
- 👛 **Contributor wallet mapping** — JSON map of GitHub username → RTC wallet
- 🧪 **Dry-run mode** — test without sending real tokens
- 💬 **Auto-comment** — confirmation comment on merged PR
- 🔄 **Reusable** — works across any RustChain repo

## Inputs

| Input | Description | Default |
|---|---|---|
| `rtc-amount` | Amount of RTC to award | `20` |
| `wallet-address` | Default sender wallet | `RTC6d1f27d28961279f1034d9561c2403697eb55602` |
| `dry-run` | Simulate transfer | `false` |
| `github-token` | GitHub token | `${{ github.token }}` |
| `contributor-wallet-map` | JSON: username → wallet | `{}` |
| `comment-on-success` | Post PR comment | `true` |
| `comment-template` | Custom comment template | Default |

## Full Documentation

See: https://github.com/BossChaos/rtc-reward-action
