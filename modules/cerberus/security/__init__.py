"""Cerberus security subpackage.

Absorbed from the standalone Sentinel module during Phase A
consolidation. Houses the security-surface logic that Cerberus
exposes through its existing tool-dispatch path: firewall analysis,
threat intelligence, file integrity, network scanning, quarantine.

Public surface (after the port commits land):
    SecuritySurface  — handler for the 24 absorbed security tools
    SecurityAnalyzer — firewall config parser/evaluator/generator
    ThreatIntelligence — attack pattern + log + malware analysis

Cerberus owns lifecycle. SecuritySurface holds no lockfile of its
own (per addendum 1, decision a) and tags new Grimoire writes with
source_module="cerberus.security" (per addendum 2, decision b).
"""
