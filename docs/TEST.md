# AAIC AI-assisted Test Assignment

> [!NOTE]
> This is a test assignment for the position of **AI-assisted Engineering Lead** at AAIC.

---

## Overall Assignment Context

You will receive a high-level product specification for a small project. Your goal is to implement the product accordingly.

- **Details & Assumptions**: The specification is intentionally high-level. You are expected to make reasonable assumptions and validate them with the product lead when needed.
- **Real-world Need**: This is not a "test project"—there is a real need this product addresses.
- **AI Tools**: You are expected to use AI tools (like **Cursor** or **Claude Code**) heavily. Please include a short overview of your approach in the documentation.

### Deliverables
The assignment should result in a GitHub repository containing:
- [x] Well-documented source code
- [x] A comprehensive test suite
- [x] Onboarding and handover documentation
- [x] Instructions for local run or deployment
- [x] Implementation specifications and design choices
- [x] Process journal (if developed in phases)

> [!TIP]
> This is a paid assignment. If the task feels overwhelming, select a subset of features (an MVP) and implement them thoroughly rather than starting everything and completing nothing.

---

## Evaluation Criteria

### What We Will Be Looking For
1. **Execution**: Does the project run? How easy is it to test?
2. **Handover**: How straightforward is the handover process?
3. **Product Mindset**: How do you handle gaps in the specification and distinguish required vs. out-of-scope features?
4. **Transparency**: How do you document technical assumptions and design choices (e.g., data model)?
5. **Quality**: What is your test coverage? Is the code clear, robust, and readable?

### What We Won't Be Looking For
- AI vs. Human ratio in code/tests/docs.
- Particular patterns of AI usage.
- Industrial-level scalability and DevOps.
- Easter eggs.

---

## Proposed Repository Structure

We recommend following these conventions for better readability:

| Directory/File | Purpose |
| :--- | :--- |
| `src/` | Source code |
| `docs/` | Documentation (onboarding, handover, runbook) |
| `journal/` | Implementation specs (`XX_spec_name.md`) |
| `journal/PROGRESS.md` | Implementation journal |
| `env.example` | Example environment variables |
| `configuration.yaml` | Project-level configuration |
| `run.sh` | Script to run the server locally |

---

## Product Brief: Timetable Assistant Bot

### Goal
Build a Discord/Telegram/WhatsApp bot that monitors a channel or group and **automatically converts any mentioned times into multiple timezones**.

**Example:**
- *User:* "See you at 10:30"
- *Bot:* "It is 10:30 Amsterdam, 11:30 Cyprus, 13:30 Yerevan."

### Context
Our team is distributed across the globe: Vancouver, Miami, Lisbon, Amsterdam, Milan, Belgrade, Limassol, Tbilisi, and Yerevan.
- The bot learns each participant's timezone and builds a list of "active timezones."
- When someone mentions a time, the bot detects the source timezone and converts it to all active timezones.

---

## Frequently Asked Questions

**Q: Who came up with this assignment?**
A: One of our engineers. We value understanding the problem space and controlling AI output over traditional "code challenges."

**Q: Don't you need engineers who write good code without AI?**
A: Yes, being a good coder correlates with being a good software engineer. However, engineering is about designing elegant and maintainable solutions.

**Q: Is it ethical to ask candidates to complete "real projects"?**
A: We expect you'll use AI heavily, just like we do. The solution should be runnable for testing, but not production-ready.
> [!IMPORTANT]
> If you believe this is unethical, please tell us—we'll find a different assignment for you.

---

## Financials

| Item | Amount |
| :--- | :--- |
| Assignment Fee | $500 USD |
| Cursor Pro+ (1 Month) | $60 USD |
| **Total Payment** | **$560 USD** |

> [!NOTE]
> We use **EasyStaff.io** for payouts, as well as for our regular payroll.
