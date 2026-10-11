"""AI IT Support Copilot domain.

Ports the standalone Copilot (`github.com/akinselureabiola/AI-IT-Support-Copilot`)
into the AI Hub domain contract (`docs/09_Migration_Analysis.md` §3.3):
Pydantic/typed state, LangGraph workflow, versioned prompts, and API
schemas — reusing the existing logic, not rebuilding it.

Knowledge-base note: the ported `knowledge_base/` assets are the
standalone Copilot's seed content, preserved verbatim. They contain an
internal-looking placeholder (`Corporate VPN Gateway VPN-BERLIN-01` in
`vpn_guide.txt`) that must be reviewed and replaced with real
organization specifics before production use — no company-specific
facts were invented here.
"""
