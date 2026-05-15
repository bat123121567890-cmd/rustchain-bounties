# GitHub Action: RTC Reward on PR Merge

## Repository Structure
- `action.yml` - Action definition
- `package.json` - Dependencies  
- `src/main.js` - Main logic
- `README.md` - Usage documentation

## Features Implemented
✅ Configurable RTC amount per merge  
✅ Reads contributor wallet from PR body or `.rtc-wallet` file  
✅ Posts comment on PR confirming payment  
✅ Supports dry-run mode for testing  
✅ Self-signed TLS support for rustchain.org  
✅ Published to GitHub Marketplace ready  

## Usage Example
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

## Verification
- Tested logic flow with mock GitHub context
- Handles edge cases (no wallet found, API errors)
- Includes proper error handling and logging
- Ready for npm packaging and GitHub Marketplace publication

This completes all requirements for bounty #2864 (20 RTC).
