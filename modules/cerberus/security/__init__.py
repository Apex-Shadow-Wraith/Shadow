"""Cerberus security subpackage.

Absorbed from the standalone Sentinel module during Phase A
consolidation. Houses the security-surface logic that Cerberus
exposes through its existing tool-dispatch path: firewall analysis,
threat intelligence, file integrity, network scanning, quarantine.

Public surface:
    SecuritySurface    — handler for the 24 absorbed security tools
    SECURITY_TOOLS     — frozenset of the 24 absorbed tool names
    SecurityAnalyzer   — firewall config parser/evaluator/generator
    ThreatIntelligence — attack pattern + log + malware analysis

Cerberus owns lifecycle. SecuritySurface holds no lockfile of its
own (per addendum 1, decision a) and tags new Grimoire writes with
source_module="cerberus.security" (per addendum 2, decision b).
"""

from modules.cerberus.security.analyzer import SecurityAnalyzer
from modules.cerberus.security.core import SECURITY_TOOLS, SecuritySurface
from modules.cerberus.security.threat_intelligence import ThreatIntelligence

__all__ = [
    "SecuritySurface",
    "SECURITY_TOOLS",
    "SecurityAnalyzer",
    "ThreatIntelligence",
]
