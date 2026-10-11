"""Knowledge-base loader.

Ported from the standalone Copilot's `utils/knowledge_loader.py`
(KEEP, `docs/09_Migration_Analysis.md` §3.2). The issue-type → file
mapping and the general fallback are preserved exactly.

Category mapping (documented, preserved from the legacy code):
- The classifier emits: password_reset, vpn_issue, network_issue,
  hardware_issue, access_issue, security_issue.
- Dedicated knowledge files exist for: vpn_issue, password_reset,
  email_issue, printer_issue, m365_issue, active_directory_issue.
- Everything else — including network_issue, hardware_issue,
  access_issue, and security_issue — falls back to general_support.txt.
"""

from importlib.resources import files

KNOWLEDGE_FILES = {
    "vpn_issue": "vpn_guide.txt",
    "password_reset": "password_reset.txt",
    "email_issue": "outlook_guide.txt",
    "printer_issue": "printer_support.txt",
    "m365_issue": "m365_support.txt",
    "active_directory_issue": "active_directory.txt",
    "general": "general_support.txt",
}

_ASSET_ROOT = files("app.domains.support_copilot").joinpath("knowledge_base")


def load_knowledge(issue_type: str) -> str:
    """Return the knowledge-base content for `issue_type`.

    Falls back to the general support guide for unknown categories,
    preserving the legacy behavior.
    """
    file_name = KNOWLEDGE_FILES.get(issue_type, "general_support.txt")
    try:
        return _ASSET_ROOT.joinpath(file_name).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""
