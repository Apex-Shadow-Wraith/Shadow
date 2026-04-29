"""Cerberus security core — placeholder.

Filled in commit 4 with the absorbed Sentinel dispatch logic
(network scan, file integrity, breach check, threat assess,
quarantine, security_alert, firewall_status, etc.) lifted out of
the old Sentinel.execute() async wrapper into a synchronous
SecuritySurface.handle(tool_name, params) helper that Cerberus
delegates to from its execute() branch.
"""
