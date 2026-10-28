# IT PMO Kanban

<!-- ship-pages:start -->
A single-page Kanban board demo for a fictitious bank's internal IT PMO, built with vanilla HTML, CSS and JavaScript.

[![CI/CD](https://github.com/oberaifamily/Claude_Training-2/actions/workflows/pages.yml/badge.svg)](https://github.com/oberaifamily/Claude_Training-2/actions/workflows/pages.yml)

**Live demo:** https://oberaifamily.github.io/Claude_Training-2/

## Features

- Four fixed columns (Backlog, In Progress, Blocked, Done) with live task counts.
- Drag and drop cards between columns, plus a keyboard-friendly "Move" control on every card.
- Priority colour coding, overdue badges, relative due dates and assignee avatars.
- Filter by project, assignee and priority, with a live status summary in the header.
- Add Task form with inline validation and an inline delete confirmation.
- Light and dark themes that follow the system setting, and a WhatsApp contact button.

## Run locally

Open `index.html` in a browser. No build step or server is needed. Board data lives in memory only, so a refresh resets it to the demo data.

## Configuration

Both settings are constants at the top of the script in `index.html`:

- `FORMSUBMIT_ENDPOINT`: replace `YOUR_EMAIL@example.com` with the address that should receive new-task emails. FormSubmit sends a one-time activation email to that address, and notifications are delivered only after its link is clicked.
- `WHATSAPP_NUMBER` and `WHATSAPP_MESSAGE`: the contact number (digits only, with country code) and the pre-filled message for the WhatsApp button.

## Deployment

Pushes to `main` run `.github/workflows/pages.yml`: secret scan, validation, then deploy to GitHub Pages. In the repo settings, Pages must use **GitHub Actions** as its source. Run `python3 scripts/secret-scan.py --history` locally before pushing.
<!-- ship-pages:end -->
