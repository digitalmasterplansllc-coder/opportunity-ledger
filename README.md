# Opportunity Ledger
### Turn ideas into evidence.

A free, local-first web application for freelancers, makers and small service businesses.
Compare the economics of your offers, test demand with small experiments and track collected revenue.
No account, telemetry, paid API or external service is required.

**A complete local application:** Python HTTP backend, SQLite persistence and responsive browser interface.
It is independent of Digital Masterplans and contains none of its source, customer data or integrations.
Created with AI assistance for Sueli's open-source contribution. Contributions are welcome.

## Start in one command
Requires Python 3.10 or later. No pip installation or build step.

```sh
python3 app.py --open
```
On Windows:
```powershell
py app.py --open
```
Then visit **http://127.0.0.1:8765**. Keep the terminal open while using the app.
You can also double-click `start.command` on macOS after granting it execute permission,
or `start.bat` on Windows. Stop the server with Ctrl+C.

## What you can actually do
- Create, edit and delete opportunities with price, costs, fees, hours and target pay.
- See estimated contribution, hourly contribution, target-pay surplus and a cost-covering price.
- Compare up to three offers side by side.
- Filter by stage and search by title, category or next action.
- Sort by hourly contribution or surplus after target pay.
- Move offers through Idea, Testing, Won, Delivered and Lost stages.
- Record non-overlapping demand experiments: contacts, replies, wins, outreach spending and receipts.
- Read aggregate experiment results and a persistent activity trail.
- Export opportunities as CSV or export data as JSON.
- Explore optional fictional examples. The workspace starts empty.
- Use six currency labels. **Changing currency does not convert amounts.**
- Learn from the in-app playbook and calculation definitions.

## Try this complete journey
1. Start the server and click **Explore examples**.
2. Edit an offer. Change its hours and watch the live calculation preview.
3. Save, visit Opportunities and compare two offers.
4. Open Experiments and record a fictional cohort: 10 contacts, 4 replies, 1 win.
5. Enter outreach spend and collected revenue, then save.
6. Refresh the browser: your entries persist in SQLite.
7. Export your records. Remove fictional entries before recording real work.

## What the numbers mean
- Contribution = price - direct costs - acquisition costs - percentage fees.
- Contribution/hour = contribution / hours. Undefined for zero hours.
- Surplus after target pay = contribution - hours x your chosen hourly pay.
- Price to cover costs + target pay = (direct costs + acquisition + target pay) / (1 - fee rate).
  The result rounds upward to a cent. It does not prove customers will pay it.
- Probability-weighted contribution = contribution x your estimated win probability.
  This is not a full expected-value model: some acquisition costs can occur even when you lose.
- Revenue/outreach spend excludes delivery costs and time. **It is not profit or ROI.**

Core monetary amounts use integer cents. Python Decimal handles input rounding and fees.
The live browser preview is approximate; saved server calculations are authoritative.
Taxes and overhead are excluded unless you include them in direct costs. No income is guaranteed.

## Data ownership and privacy
Your data is stored in `ledger.db` next to the application. The app binds only to `127.0.0.1`.
There are no tracking pixels, analytics, external fonts or provider calls.
Stop the app and copy `ledger.db` to back up your workspace; restoring that file restores your records.
JSON and CSV are portable exports, not a full restore mechanism: importing is not implemented.
Activity is retained for ordinary visibility, not as a tamper-proof accounting ledger.
Do not commit database files to GitHub. `.gitignore` excludes them.

## Architecture and tradeoffs
```
Browser interface -> localhost HTTP API -> SQLite
```
- One Python process; SQLite connections are opened per operation.
- Mutations and their activity events share a database transaction.
- Record versions reject stale opportunity updates with HTTP 409.
- User content is HTML-escaped before rendering.
- Writes require a per-launch token and an exact localhost Host header.
- CSV text is neutralized when it could be interpreted as a spreadsheet formula.
- Content Security Policy restricts scripts and assets to the app itself.

**This is a single-user local application, not a public multi-tenant service.**
There is no user authentication, HTTPS termination, collaboration, scheduling or payment processing.
Do not expose it on the internet. Anyone with access to your computer/account may access the database.
The Python standard-library HTTP server is used for a simple dependency-free local experience.

## Tests
```sh
python3 -m unittest -v
```
Coverage includes arithmetic, zero/negative/nonfinite input handling, stale edits,
experiment validation, persistent data, deletes, duplicate demo protection and HTTP write controls.
See `VALIDATION.md` for the exact verification completed for this version.

## Publish this project on GitHub
Create an empty public repository named `opportunity-ledger`, then run these commands in this folder:
```sh
git init
git add .
git status
# Inspect the staged files; no database or secrets should appear.
git commit -m "Initial open-source Opportunity Ledger application"
git branch -M main
# Add YOUR repository URL using GitHub's displayed instructions, then push.
```
GitHub Pages serves static files and will not run this Python backend.
People download this repository and run it locally. You can host a separately made static landing
page for discovery, but the current application is intentionally not a public hosted service.

## Contribute
See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under [MIT](LICENSE).
