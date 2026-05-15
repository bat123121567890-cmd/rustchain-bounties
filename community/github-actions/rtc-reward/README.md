# RTC Reward Action

Automatically award RTC tokens when a PR is merged. Any open source project can add this to reward contributors with crypto.

## Usage

Add this workflow to your `.github/workflows/rtc-reward.yml`:

```yaml
name: RTC Reward
on:
  pull_request:
    types: [closed]

jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: Scottcjn/rtc-reward-action@v1
        with:
          node-url: https://50.28.86.131
          amount: 5
          wallet-from: project-fund
          admin-key: \${{ secrets.RTC_ADMIN_KEY }}
        env:
          GITHUB_TOKEN: \${{ secrets.GITHUB_TOKEN }}
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `node-url` | RustChain node URL | false | `https://rustchain.org` |
| `amount` | RTC amount to award per merged PR | true | - |
| `wallet-from` | Source wallet for rewards | true | - |
| `admin-key` | Admin key for transaction signing | true | - |
| `dry-run` | Dry run mode (no actual transactions) | false | `false` |
| `wallet-file` | Wallet file path in repo | false | `.rtc-wallet` |

## How It Works

1. **Detects merged PRs** via GitHub Actions trigger
2. **Extracts contributor wallet** from PR body or `.rtc-wallet` file
3. **Awards RTC tokens** via RustChain node API
4. **Posts confirmation comment** on the PR

## Features

- ✅ Configurable RTC amount per merge
- ✅ Reads contributor wallet from PR body or file
- ✅ Posts comment confirming payment
- ✅ Supports dry-run mode for testing
- ✅ Self-signed TLS support for rustchain.org

## License

MIT
