# GitHub Setup

## Recommended repository settings

Repository name:

```text
casemesh-ai
```

Recommended initial visibility:

```text
Private
```

Switch to public after the implementation and documentation reach a stable portfolio-ready milestone.

Do not initialize the GitHub repository with a README, `.gitignore`, or license because this package already contains them.

## First push

After extracting the prepared folder and opening PowerShell inside it:

```powershell
git init
git branch -M main
git add .
git commit -m "chore: initialize CaseMesh AI repository"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/casemesh-ai.git
git push -u origin main
```

If Git asks for authentication, complete the browser-based GitHub sign-in flow.

## Recommended GitHub settings after the first push

### General
- Default branch: `main`
- Disable force pushes to `main`
- Disable branch deletion for `main`

### Branch protection (when available)
Require:
- pull request before merge,
- conversation resolution,
- status checks once CI exists.

### Security
Enable when repository becomes public:
- Dependabot alerts
- Dependabot security updates
- secret scanning where available

## Do not upload
- `.env`
- real credentials
- private raw data
- cloud access keys
- personal billing information
