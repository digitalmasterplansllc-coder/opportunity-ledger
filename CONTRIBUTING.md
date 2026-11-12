# Contributing
This project helps people understand the economics of small income opportunities.
Contributions should improve clarity and usefulness without making unsupported earnings claims.

## First contributions
- Add JSON import with schema validation, preview and transactional rollback.
- Add actual-versus-estimated delivery time and costs as separate fields.
- Improve keyboard and screen-reader accessibility with documented manual tests.
- Translate the interface into Brazilian Portuguese or Spanish.
- Add a print-friendly offer summary without customer personal information.

## Development
Use Python 3.10+ and a modern browser. No third-party dependencies are required.
Run `python3 -m unittest -v`. Keep financial arithmetic on the server in integer cents/Decimal.
Run the app with a temporary database for experiments:
`python3 app.py --db practice.db --port 8766 --open`.

Open an issue with the problem, expected behavior and a fictional reproduction.
Keep pull requests focused; explain tradeoffs and add tests for changed calculations or persistence.
Do not include credentials, database files, customer records or proprietary code from another project.
Do not claim a feature is implemented until it works. If using AI assistance, review the code and
be prepared to explain it. Do not add external telemetry or paid dependencies without discussion.

## Security
Do not publish sensitive reproduction data in an issue. For a serious issue, contact the repository
maintainer through GitHub's private security reporting if enabled. There is no dedicated security
email configured yet. Keep the app bound to localhost.
