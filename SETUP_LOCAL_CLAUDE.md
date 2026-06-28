# Local Claude Code + Obsidian Vault Setup

This lets a **local** Claude Code session (running on your Windows PC) read your real
Obsidian vault and build quizzes directly from your notes — then push them live.

> Why local? The cloud chat session cannot reach your PC's files. The Obsidian MCP
> server reads your vault from local disk, so it only works on the machine that has
> the vault.

---

## One-time setup

1. **Pull the latest repo** on your Windows machine so you have these files:
   ```powershell
   cd C:\Users\ravin\Desktop\Obsidian_Daily_Quiz
   git pull origin main
   ```

2. **Run the setup script** (installs Node check, Claude Code, verifies vault):
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup_local_claude.ps1
   ```
   If Node.js is missing it will open the download page — install the **LTS** build,
   then re-run the script.

3. **Start Claude Code in this folder:**
   ```powershell
   cd C:\Users\ravin\Desktop\Obsidian_Daily_Quiz
   claude
   ```
   The committed `.mcp.json` auto-loads the **obsidian** MCP server. When prompted,
   approve/trust it.

4. **Verify** inside the session:
   ```
   /mcp
   ```
   You should see `obsidian` connected. Or just ask:
   *"List the folders in my Obsidian vault."*

---

## Daily use

Once connected, in the **local** session you can say:

- *"Read my 'Quiz Prediction Model' note and make 30 tough PG-level questions with
   memory-palace hooks, balanced A/B/C/D, then write to daily_questions.json and push."*
- *"Pull from the Cosmetology > Recent Advances folder and build today's quiz."*
- *"Summarise what's in my Stanley Dermatosurgery folder."*

The local session has **both** vault access (read notes) **and** repo access (commit +
push), so it builds and publishes in one go.

---

## If the vault path is wrong

The vault path appears in **two** places — update both to match your real vault root:

1. `.mcp.json` → `args` array (the last entry)
2. `setup_local_claude.ps1` → the `$VAULT` line near the top

Current configured path:
```
C:\Users\ravin\Documents\Dermatology venereology and leprosy
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/mcp` shows obsidian as *failed* | Check Node.js is installed (`node --version`); confirm the vault path exists |
| "command not found: claude" | Re-run the setup script, or `npm install -g @anthropic-ai/claude-code` |
| npx is slow on first run | Normal — it downloads `obsidian-mcp` once, then caches it |
| Server won't trust | Run `claude` from inside the repo folder so it reads the project `.mcp.json` |
