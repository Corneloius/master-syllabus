# Master Syllabus Deployment Workflow

## Your Setup (Option B)

- **Working folder:** `c:\Users\brons\Projects` (edit files here)
- **Git repo:** `c:\Users\brons\master-syllabus-repo` (push from here)

---

## Quick Deploy Steps

### Method 1: Use the helper script

```powershell
cd c:\Users\brons\Projects
.\deploy.ps1
```

Then review changes and commit/push manually.

### Method 2: Manual steps

1. **Copy files to repo:**
   ```powershell
   Copy-Item "c:\Users\brons\Projects\index.html" "c:\Users\brons\master-syllabus-repo\" -Force
   Copy-Item "c:\Users\brons\Projects\Master_Syllabus_Spring_2026.html" "c:\Users\brons\master-syllabus-repo\" -Force
   ```

2. **Go to repo and check status:**
   ```powershell
   cd c:\Users\brons\master-syllabus-repo
   git status
   ```

3. **Commit and push:**
   ```powershell
   git add index.html Master_Syllabus_Spring_2026.html
   git commit -m "Your descriptive message here"
   git push origin main
   ```

---

## Using AI Assistant (Agent Mode)

When you want to deploy, just say:
- "Deploy to GitHub" or
- "Push the latest changes" or
- "Update the live site"

I'll copy the files, commit, and push for you automatically.

---

## Live Site

After pushing, wait 1-2 minutes, then check:
**https://corneloius.github.io/master-syllabus/**

GitHub Pages automatically rebuilds when you push to the `main` branch.
