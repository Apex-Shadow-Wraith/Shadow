"""Cerberus Security Analyzer — firewall configuration analysis and learning pipeline.

Parses, evaluates, compares, and generates firewall configurations across
iptables, nftables, ufw, and pf syntaxes.  Stores learned knowledge in
Grimoire for long-term reference.

Absorbed from modules/sentinel/security_analyzer.py during Phase A
consolidation. Behavior preserved verbatim. New Grimoire writes tag
source_module="cerberus.security"; historical "sentinel"-tagged
entries remain queryable via the writer-side validator allowlist.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firewall type constants
# ---------------------------------------------------------------------------
IPTABLES = "iptables"
NFTABLES = "nftables"
UFW = "ufw"
PF = "pf"
SUPPORTED_TYPES = {IPTABLES, NFTABLES, UFW, PF}

# ---------------------------------------------------------------------------
# Grading scale for evaluate_firewall
# ---------------------------------------------------------------------------
_GRADE_THRESHOLDS = [
    (27, "A"),  # 9 checks × 3 max = 27
    (23, "B"),
    (18, "C"),
    (13, "D"),
]

# ---------------------------------------------------------------------------
# Firewall concept knowledge base
# ---------------------------------------------------------------------------
_CONCEPTS: dict[str, dict[str, str]] = {
    "stateful_vs_stateless": {
        "explanation": (
            "Stateful firewalls track the state of network connections (NEW, "
            "ESTABLISHED, RELATED) and make decisions based on context. "
            "Stateless firewalls evaluate each packet independently using "
            "only header fields."
        ),
        "how_it_works": (
            "Connection tracking (conntrack in Linux) maintains a table of "
            "active connections. When a packet arrives, the firewall checks "
            "if it belongs to an existing connection before evaluating rules."
        ),
        "when_to_use": (
            "Use stateful for almost all modern deployments. Stateless only "
            "for extremely high-throughput edge routers where per-packet "
            "overhead matters."
        ),
        "shadow_relevance": (
            "Shadow's Ubuntu server should always use stateful inspection to "
            "allow established connections while blocking unsolicited inbound."
        ),
        "example_config": (
            "iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT"
        ),
    },
    "dmz": {
        "explanation": (
            "A DMZ (demilitarized zone) is a network segment that sits "
            "between the internal network and the internet, hosting "
            "public-facing services while isolating them from the LAN."
        ),
        "how_it_works": (
            "Typically implemented with two firewall interfaces: one facing "
            "the internet, one facing the DMZ. Internal hosts cannot be "
            "reached directly from the DMZ."
        ),
        "when_to_use": (
            "When running public services (web, mail, DNS) that must be "
            "internet-accessible but should not have direct LAN access."
        ),
        "shadow_relevance": (
            "If Shadow exposes any API endpoints externally, they should "
            "run in a DMZ-style network segment."
        ),
        "example_config": (
            "# nftables DMZ example\n"
            "table inet filter {\n"
            "  chain forward {\n"
            "    type filter hook forward priority 0; policy drop;\n"
            "    iifname \"eth1\" oifname \"eth0\" accept  # DMZ -> internet\n"
            "    iifname \"eth0\" oifname \"eth1\" ct state established accept\n"
            "  }\n"
            "}"
        ),
    },
    "port_knocking": {
        "explanation": (
            "Port knocking is a stealth technique where a service port "
            "remains closed until the client sends a specific sequence of "
            "connection attempts to predetermined ports."
        ),
        "how_it_works": (
            "A daemon (e.g. knockd) monitors firewall logs. When it sees "
            "the correct sequence of SYN packets to specific ports in "
            "order, it temporarily opens the real service port for that IP."
        ),
        "when_to_use": (
            "For SSH on public-facing servers where you want an extra "
            "layer beyond key-based auth. Not a replacement for proper "
            "authentication."
        ),
        "shadow_relevance": (
            "Could protect Shadow's SSH access on Ubuntu with an additional "
            "layer of obscurity on top of key-based authentication."
        ),
        "example_config": (
            "# knockd.conf\n"
            "[openSSH]\n"
            "  sequence = 7000,8000,9000\n"
            "  seq_timeout = 5\n"
            "  command = /sbin/iptables -A INPUT -s %IP% -p tcp --dport 22 "
            "-j ACCEPT\n"
            "  tcpflags = syn"
        ),
    },
    "fail2ban": {
        "explanation": (
            "Fail2ban monitors log files for repeated authentication "
            "failures and dynamically adds firewall rules to ban the "
            "offending IP addresses for a configurable duration."
        ),
        "how_it_works": (
            "Fail2ban reads log files (auth.log, nginx access.log), "
            "matches lines against regex filters, counts failures per IP "
            "within a time window, and executes ban actions (iptables "
            "rules, nftables sets, or firewalld rich rules)."
        ),
        "when_to_use": (
            "On any internet-facing server with SSH, web, or mail services. "
            "Essential for brute-force protection."
        ),
        "shadow_relevance": (
            "Critical for Shadow's Ubuntu server. Should protect SSH, "
            "Ollama API port, and any web endpoints."
        ),
        "example_config": (
            "# /etc/fail2ban/jail.local\n"
            "[sshd]\n"
            "enabled = true\n"
            "port = ssh\n"
            "filter = sshd\n"
            "logpath = /var/log/auth.log\n"
            "maxretry = 3\n"
            "bantime = 3600\n"
            "findtime = 600"
        ),
    },
    "connection_tracking": {
        "explanation": (
            "Connection tracking (conntrack) is the kernel subsystem that "
            "maintains a table of all active network connections, enabling "
            "stateful packet filtering."
        ),
        "how_it_works": (
            "The conntrack module in Linux netfilter tracks each connection "
            "through states: NEW, ESTABLISHED, RELATED, INVALID. Rules can "
            "match on these states to allow return traffic without explicit "
            "rules for each direction."
        ),
        "when_to_use": (
            "Always. Connection tracking is fundamental to modern firewall "
            "configurations and should be enabled by default."
        ),
        "shadow_relevance": (
            "Shadow's firewall must use conntrack to allow established "
            "connections (API responses, package updates) while blocking "
            "unsolicited inbound traffic."
        ),
        "example_config": (
            "iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT\n"
            "iptables -A INPUT -m conntrack --ctstate INVALID -j DROP"
        ),
    },
    "nat_types": {
        "explanation": (
            "NAT (Network Address Translation) remaps IP addresses between "
            "networks. Types: SNAT (source NAT), DNAT (destination NAT), "
            "masquerade (dynamic SNAT), and port forwarding."
        ),
        "how_it_works": (
            "SNAT rewrites source addresses on outbound packets (used for "
            "sharing a public IP). DNAT rewrites destination addresses on "
            "inbound packets (used for port forwarding to internal hosts). "
            "Masquerade is SNAT that auto-detects the outbound IP."
        ),
        "when_to_use": (
            "SNAT/masquerade for internet sharing. DNAT for exposing "
            "internal services. Port forwarding for specific service access."
        ),
        "shadow_relevance": (
            "If Shadow needs to expose Ollama or web services from behind "
            "NAT, DNAT/port forwarding rules will be needed."
        ),
        "example_config": (
            "# iptables masquerade for NAT\n"
            "iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE\n"
            "# Port forward 8080 -> internal:80\n"
            "iptables -t nat -A PREROUTING -p tcp --dport 8080 "
            "-j DNAT --to-destination 192.168.1.10:80"
        ),
    },
    "bridge_vs_route": {
        "explanation": (
            "Bridge mode operates at Layer 2 (data link), forwarding "
            "frames by MAC address. Route mode operates at Layer 3 "
            "(network), forwarding packets by IP address."
        ),
        "how_it_works": (
            "A bridge firewall is transparent — hosts on both sides share "
            "the same subnet. A routing firewall separates subnets and "
            "makes forwarding decisions based on IP routing tables."
        ),
        "when_to_use": (
            "Bridge for transparent inline filtering (IDS/IPS). Route "
            "for network segmentation and NAT."
        ),
        "shadow_relevance": (
            "Shadow's server should use routing mode for proper network "
            "segmentation between services."
        ),
        "example_config": (
            "# Bridge firewall with nftables\n"
            "table bridge filter {\n"
            "  chain forward {\n"
            "    type filter hook forward priority 0; policy accept;\n"
            "    ether type arp accept\n"
            "    ip protocol icmp accept\n"
            "  }\n"
            "}"
        ),
    },
    "zone_based": {
        "explanation": (
            "Zone-based firewalls group interfaces into security zones "
            "(trust, untrust, DMZ) and apply policies to traffic flowing "
            "between zones rather than per-interface rules."
        ),
        "how_it_works": (
            "Each interface is assigned to a zone. Policies define what "
            "traffic is allowed between zone pairs. Traffic within the "
            "same zone is typically allowed; inter-zone traffic is denied "
            "by default."
        ),
        "when_to_use": (
            "For complex networks with multiple security levels. "
            "Firewalld on Linux uses this model."
        ),
        "shadow_relevance": (
            "If Shadow's server has multiple network interfaces (LAN, "
            "IoT, management), zone-based policies simplify management."
        ),
        "example_config": (
            "# firewalld zone example\n"
            "firewall-cmd --zone=trusted --add-interface=lo\n"
            "firewall-cmd --zone=public --add-interface=eth0\n"
            "firewall-cmd --zone=internal --add-interface=eth1\n"
            "firewall-cmd --zone=public --add-service=ssh"
        ),
    },
    "application_layer_filtering": {
        "explanation": (
            "Application layer (Layer 7) filtering inspects packet "
            "payloads to make decisions based on application protocols "
            "(HTTP methods, DNS queries, TLS SNI)."
        ),
        "how_it_works": (
            "Deep packet inspection (DPI) engines parse application "
            "protocols. Can block specific URLs, detect malware signatures, "
            "or enforce protocol compliance. More CPU-intensive than L3/L4."
        ),
        "when_to_use": (
            "When you need to filter based on content, not just "
            "addresses and ports. Web application firewalls (WAF), "
            "intrusion prevention systems (IPS)."
        ),
        "shadow_relevance": (
            "Shadow could use application-layer filtering to inspect "
            "API requests to Ollama and block malicious prompts at the "
            "network level."
        ),
        "example_config": (
            "# nftables with layer 7 matching (requires nft + nfqueue)\n"
            "table inet filter {\n"
            "  chain input {\n"
            "    tcp dport 80 queue num 0  # Send to userspace DPI\n"
            "  }\n"
            "}"
        ),
    },
    "iptables_vs_nftables": {
        "explanation": (
            "iptables is the legacy Linux firewall framework using "
            "separate tools (iptables, ip6tables, arptables, ebtables). "
            "nftables is its modern replacement with a unified syntax, "
            "better performance, and atomic rule updates."
        ),
        "how_it_works": (
            "Both use the netfilter kernel framework. iptables uses "
            "predefined tables and chains. nftables uses a custom "
            "scripting language with user-defined tables, chains, sets, "
            "and maps for more flexible rule organization."
        ),
        "when_to_use": (
            "nftables for all new deployments (default since Debian 10, "
            "Ubuntu 20.10+). iptables only for legacy compatibility."
        ),
        "shadow_relevance": (
            "Shadow's Ubuntu server should use nftables as the primary "
            "firewall framework. Learn both syntaxes for analysis."
        ),
        "example_config": (
            "# iptables\n"
            "iptables -A INPUT -p tcp --dport 22 -j ACCEPT\n\n"
            "# nftables equivalent\n"
            "nft add rule inet filter input tcp dport 22 accept"
        ),
    },
}

# ---------------------------------------------------------------------------
# Standard service port mappings
# ---------------------------------------------------------------------------
_SERVICE_PORTS: dict[str, dict[str, Any]] = {
    "ssh": {"port": 22, "protocol": "tcp"},
    "http": {"port": 80, "protocol": "tcp"},
    "https": {"port": 443, "protocol": "tcp"},
    "dns": {"port": 53, "protocol": "tcp/udp"},
    "ollama": {"port": 11434, "protocol": "tcp"},
    "smtp": {"port": 25, "protocol": "tcp"},
    "imap": {"port": 993, "protocol": "tcp"},
    "ntp": {"port": 123, "protocol": "udp"},
    "postgres": {"port": 5432, "protocol": "tcp"},
    "mysql": {"port": 3306, "protocol": "tcp"},
    "redis": {"port": 6379, "protocol": "tcp"},
}


class SecurityAnalyzer:
    """Firewall configuration analyzer and learning engine (Cerberus security surface)."""

    def __init__(self, grimoire: Any | None = None) -> None:
        self._grimoire = grimoire

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def analyze_firewall_config(
        self,
        config_text: str,
        firewall_type: str = "auto",
    ) -> dict[str, Any]:
        """Parse and analyse a firewall configuration.

        Args:
            config_text: Raw config text (iptables -L output, nft list, etc.)
            firewall_type: One of iptables, nftables, ufw, pf, or "auto".

        Returns:
            Structured analysis dict.
        """
        if firewall_type == "auto":
            firewall_type = self._detect_type(config_text)

        parsers = {
            IPTABLES: self._parse_iptables,
            NFTABLES: self._parse_nftables,
            UFW: self._parse_ufw,
            PF: self._parse_pf,
        }

        parser = parsers.get(firewall_type)
        if parser is None:
            return {
                "error": f"Unsupported firewall type: {firewall_type}",
                "supported": list(SUPPORTED_TYPES),
            }

        analysis = parser(config_text)
        analysis["firewall_type"] = firewall_type
        analysis["raw_length"] = len(config_text)
        return analysis

    def evaluate_firewall(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Score a firewall config against security best practices.

        Args:
            analysis: Output of analyse_firewall_config.

        Returns:
            Dict with scores, grade, and recommendations.
        """
        if "error" in analysis:
            return {"error": analysis["error"]}

        checks: dict[str, dict[str, Any]] = {}
        rules = analysis.get("rules", [])
        default_policies = analysis.get("default_policy", {})
        open_ports = analysis.get("open_ports", [])
        nat_rules = analysis.get("nat_rules", [])
        logging_info = analysis.get("logging", [])

        # 1. Default deny
        deny_chains = sum(
            1 for p in default_policies.values()
            if p.lower() in ("drop", "deny", "reject")
        )
        total_chains = len(default_policies) or 1
        if deny_chains == total_chains and total_chains > 0:
            checks["default_deny"] = {"score": 3, "status": "pass"}
        elif deny_chains > 0:
            checks["default_deny"] = {
                "score": 2,
                "status": "partial",
                "recommendation": (
                    "Not all chains default to deny. Set default policy "
                    "to DROP on INPUT and FORWARD chains."
                ),
            }
        else:
            checks["default_deny"] = {
                "score": 1,
                "status": "fail",
                "recommendation": (
                    "Default policy is ACCEPT — all unmatched traffic is "
                    "allowed. Change to DROP immediately."
                ),
            }

        # 2. Minimal exposure
        port_count = len(open_ports)
        if port_count <= 3:
            checks["minimal_exposure"] = {"score": 3, "status": "pass"}
        elif port_count <= 8:
            checks["minimal_exposure"] = {
                "score": 2,
                "status": "partial",
                "recommendation": (
                    f"{port_count} ports open. Review if all are necessary."
                ),
            }
        else:
            checks["minimal_exposure"] = {
                "score": 1,
                "status": "fail",
                "recommendation": (
                    f"{port_count} ports open — excessive exposure. "
                    "Close unnecessary ports."
                ),
            }

        # 3. Egress filtering
        egress_rules = [
            r for r in rules
            if r.get("chain", "").upper() in ("OUTPUT", "FORWARD", "egress")
            and r.get("action", "").upper() in ("DROP", "REJECT", "DENY")
        ]
        output_default = default_policies.get("OUTPUT", "").upper()
        if output_default in ("DROP", "DENY", "REJECT"):
            checks["egress_filtering"] = {"score": 3, "status": "pass"}
        elif egress_rules:
            checks["egress_filtering"] = {
                "score": 2,
                "status": "partial",
                "recommendation": (
                    "Some egress rules exist but default OUTPUT policy is not deny. "
                    "Consider default-deny egress with explicit allows."
                ),
            }
        else:
            checks["egress_filtering"] = {
                "score": 1,
                "status": "fail",
                "recommendation": (
                    "No egress filtering detected. Outbound traffic is "
                    "unrestricted — a compromised process can phone home freely."
                ),
            }

        # 4. Logging coverage
        if logging_info:
            log_drop = any(
                "drop" in str(l).lower() or "reject" in str(l).lower()
                for l in logging_info
            )
            if log_drop:
                checks["logging_coverage"] = {"score": 3, "status": "pass"}
            else:
                checks["logging_coverage"] = {
                    "score": 2,
                    "status": "partial",
                    "recommendation": "Logging exists but doesn't cover dropped packets.",
                }
        else:
            checks["logging_coverage"] = {
                "score": 1,
                "status": "fail",
                "recommendation": (
                    "No logging rules found. Add LOG targets for dropped "
                    "and rejected packets."
                ),
            }

        # 5. Rate limiting
        rate_rules = [
            r for r in rules
            if "limit" in str(r).lower() or "rate" in str(r).lower()
        ]
        if rate_rules:
            checks["rate_limiting"] = {"score": 3, "status": "pass"}
        else:
            checks["rate_limiting"] = {
                "score": 1,
                "status": "fail",
                "recommendation": (
                    "No rate limiting detected. Add rate limits for SSH "
                    "and other exposed services."
                ),
            }

        # 6. Anti-spoofing
        spoof_rules = [
            r for r in rules
            if any(
                net in str(r.get("source", ""))
                for net in ("10.0.0.0", "172.16.", "192.168.", "127.0.0.0")
            )
            and r.get("action", "").upper() in ("DROP", "REJECT", "DENY")
        ]
        if spoof_rules:
            checks["anti_spoofing"] = {"score": 3, "status": "pass"}
        else:
            checks["anti_spoofing"] = {
                "score": 1,
                "status": "fail",
                "recommendation": (
                    "No anti-spoofing rules found. Block inbound packets "
                    "with private source addresses on public interfaces."
                ),
            }

        # 7. ICMP handling
        icmp_rules = [
            r for r in rules if r.get("protocol", "").lower() == "icmp"
        ]
        icmp_blanket_drop = any(
            r.get("action", "").upper() in ("DROP", "REJECT")
            and not r.get("port")
            and "type" not in str(r).lower()
            for r in icmp_rules
        )
        if icmp_rules and not icmp_blanket_drop:
            checks["icmp_handling"] = {"score": 3, "status": "pass"}
        elif icmp_rules:
            checks["icmp_handling"] = {
                "score": 2,
                "status": "partial",
                "recommendation": (
                    "ICMP is blanket-blocked. Allow essential types "
                    "(echo-reply, destination-unreachable, time-exceeded)."
                ),
            }
        else:
            checks["icmp_handling"] = {
                "score": 1,
                "status": "fail",
                "recommendation": "No ICMP rules. Add explicit ICMP handling.",
            }

        # 8. Stateful inspection
        stateful_rules = [
            r for r in rules
            if any(
                kw in str(r).lower()
                for kw in ("established", "related", "conntrack", "state", "ct state")
            )
        ]
        if stateful_rules:
            checks["stateful_inspection"] = {"score": 3, "status": "pass"}
        else:
            checks["stateful_inspection"] = {
                "score": 1,
                "status": "fail",
                "recommendation": (
                    "No connection tracking rules. Add stateful inspection "
                    "to allow ESTABLISHED,RELATED connections."
                ),
            }

        # 9. Loopback protection
        lo_rules = [
            r for r in rules
            if "lo" in str(r.get("source", "")) + str(r.get("destination", ""))
            or "loopback" in str(r).lower()
            or "127.0.0.1" in str(r.get("source", "")) + str(r.get("destination", ""))
        ]
        if lo_rules:
            checks["loopback_protection"] = {"score": 3, "status": "pass"}
        else:
            checks["loopback_protection"] = {
                "score": 1,
                "status": "fail",
                "recommendation": (
                    "No loopback rules. Allow all traffic on lo interface "
                    "and block external packets claiming 127.0.0.0/8."
                ),
            }

        total = sum(c["score"] for c in checks.values())
        grade = "F"
        for threshold, letter in _GRADE_THRESHOLDS:
            if total >= threshold:
                grade = letter
                break
        else:
            if total >= 9:
                grade = "D"

        recommendations = [
            {"check": k, "recommendation": v["recommendation"]}
            for k, v in checks.items()
            if "recommendation" in v
        ]

        return {
            "checks": checks,
            "total_score": total,
            "max_score": 27,
            "grade": grade,
            "recommendations": recommendations,
        }

    def compare_firewalls(self, configs: list[dict[str, Any]]) -> dict[str, Any]:
        """Compare multiple firewall analyses side by side.

        Args:
            configs: List of analysis dicts from analyse_firewall_config.

        Returns:
            Comparison table and recommendation.
        """
        if len(configs) < 2:
            return {"error": "Need at least 2 configs to compare."}

        evaluations = []
        for i, cfg in enumerate(configs):
            ev = self.evaluate_firewall(cfg)
            ev["index"] = i
            ev["firewall_type"] = cfg.get("firewall_type", "unknown")
            ev["open_port_count"] = len(cfg.get("open_ports", []))
            ev["rule_count"] = cfg.get("rule_count", {})
            ev["has_egress"] = ev.get("checks", {}).get(
                "egress_filtering", {}
            ).get("status") in ("pass", "partial")
            ev["has_logging"] = ev.get("checks", {}).get(
                "logging_coverage", {}
            ).get("status") in ("pass", "partial")
            evaluations.append(ev)

        most_restrictive = min(evaluations, key=lambda e: e["open_port_count"])
        most_open = max(evaluations, key=lambda e: e["open_port_count"])
        best_logging = max(
            evaluations,
            key=lambda e: e.get("checks", {}).get("logging_coverage", {}).get("score", 0),
        )
        missing_egress = [
            e for e in evaluations if not e["has_egress"]
        ]
        best_overall = max(evaluations, key=lambda e: e["total_score"])

        return {
            "comparison": [
                {
                    "index": e["index"],
                    "firewall_type": e["firewall_type"],
                    "grade": e["grade"],
                    "total_score": e["total_score"],
                    "open_ports": e["open_port_count"],
                    "has_egress": e["has_egress"],
                    "has_logging": e["has_logging"],
                }
                for e in evaluations
            ],
            "most_restrictive": most_restrictive["index"],
            "most_open_ports": most_open["index"],
            "best_logging": best_logging["index"],
            "missing_egress": [e["index"] for e in missing_egress],
            "best_overall": best_overall["index"],
            "recommendation": (
                f"Config {best_overall['index']} ({best_overall['firewall_type']}) "
                f"scored highest (grade {best_overall['grade']}). "
                "For Shadow's always-on Ubuntu server, use nftables with "
                "default-deny on INPUT/FORWARD/OUTPUT, stateful inspection, "
                "rate-limited SSH, and comprehensive logging."
            ),
        }

    def explain_rule(
        self, rule_text: str, firewall_type: str,
    ) -> dict[str, Any]:
        """Explain a single firewall rule in plain English.

        Args:
            rule_text: The raw rule text.
            firewall_type: iptables, nftables, ufw, or pf.

        Returns:
            Dict with explanation, concerns, and equivalents.
        """
        rule_text = rule_text.strip()
        explanation = ""
        concerns: list[str] = []
        equivalents: dict[str, str] = {}

        if firewall_type == IPTABLES:
            explanation, concerns, equivalents = self._explain_iptables_rule(rule_text)
        elif firewall_type == NFTABLES:
            explanation, concerns, equivalents = self._explain_nftables_rule(rule_text)
        elif firewall_type == UFW:
            explanation, concerns, equivalents = self._explain_ufw_rule(rule_text)
        elif firewall_type == PF:
            explanation, concerns, equivalents = self._explain_pf_rule(rule_text)
        else:
            explanation = f"Cannot explain rule for unknown type: {firewall_type}"

        return {
            "original": rule_text,
            "firewall_type": firewall_type,
            "explanation": explanation,
            "concerns": concerns,
            "equivalents": equivalents,
        }

    def generate_firewall(self, requirements: dict[str, Any]) -> dict[str, Any]:
        """Generate a complete firewall config from requirements.

        Args:
            requirements: Dict with services, default_policy, enable_logging,
                rate_limit_ssh, allowed_ips, firewall_type, etc.

        Returns:
            Dict with config_text, explanation, and security_score.
        """
        fw_type = requirements.get("firewall_type", NFTABLES)
        services = requirements.get("services", ["ssh"])
        default_policy = requirements.get("default_policy", "deny")
        enable_logging = requirements.get("enable_logging", True)
        rate_limit_ssh = requirements.get("rate_limit_ssh", True)
        allowed_ips = requirements.get("allowed_ips", [])

        generators = {
            NFTABLES: self._generate_nftables,
            IPTABLES: self._generate_iptables,
        }

        generator = generators.get(fw_type, self._generate_nftables)
        config_text, explanation = generator(
            services, default_policy, enable_logging, rate_limit_ssh, allowed_ips,
        )

        # Score the generated config
        analysis = self.analyze_firewall_config(config_text, fw_type)
        evaluation = self.evaluate_firewall(analysis)

        return {
            "config_text": config_text,
            "firewall_type": fw_type,
            "explanation": explanation,
            "security_score": evaluation.get("total_score", 0),
            "grade": evaluation.get("grade", "?"),
        }

    def learn_firewall_concepts(self, topic: str) -> dict[str, Any]:
        """Study and explain a firewall concept.

        Args:
            topic: Concept name from the known topics list.

        Returns:
            Structured knowledge dict.
        """
        concept = _CONCEPTS.get(topic)
        if concept is None:
            return {
                "error": f"Unknown topic: {topic}",
                "available_topics": list(_CONCEPTS.keys()),
            }

        return {
            "topic": topic,
            "explanation": concept["explanation"],
            "how_it_works": concept["how_it_works"],
            "when_to_use": concept["when_to_use"],
            "shadow_relevance": concept["shadow_relevance"],
            "example_config": concept["example_config"],
        }

    def store_security_knowledge(
        self, knowledge: dict[str, Any], source: str,
    ) -> int:
        """Store analysed knowledge in Grimoire.

        Args:
            knowledge: Dict with at least 'topic' and 'explanation'.
            source: Where the knowledge came from.

        Returns:
            Count of items stored (0 if duplicate or no Grimoire).
        """
        if self._grimoire is None:
            logger.warning("No Grimoire available — knowledge not stored.")
            return 0

        topic = knowledge.get("topic", "unknown")
        content = (
            f"Firewall concept: {topic}\n\n"
            f"{knowledge.get('explanation', '')}\n\n"
            f"How it works: {knowledge.get('how_it_works', '')}\n\n"
            f"When to use: {knowledge.get('when_to_use', '')}\n\n"
            f"Shadow relevance: {knowledge.get('shadow_relevance', '')}"
        )

        category = knowledge.get("category", "security_knowledge")
        try:
            mem_id = self._grimoire.remember(
                content=content,
                source="research",
                source_module="cerberus.security",
                category=category,
                trust_level=0.7,  # TRUST_OFFICIAL_SOURCE / reference level
                confidence=0.8,
                tags=["firewall", "security", topic],
                metadata={"source": source, "topic": topic},
                check_duplicates=True,
            )
            if mem_id:
                logger.info("Stored security knowledge: %s (id=%s)", topic, mem_id)
                return 1
        except Exception as e:
            logger.error("Failed to store knowledge: %s", e)
        return 0

    # -----------------------------------------------------------------------
    # Type detection
    # -----------------------------------------------------------------------

    @staticmethod
    def _detect_type(config_text: str) -> str:
        """Auto-detect firewall type from config text."""
        text = config_text.lower()
        # iptables detection
        if "chain input" in text or "chain output" in text or "chain forward" in text:
            if "target" in text and "prot" in text:
                return IPTABLES
        if re.search(r"iptables\s+-[A-Z]", config_text):
            return IPTABLES
        # nftables detection
        if "table inet" in text or "table ip " in text or "nft " in text:
            return NFTABLES
        if re.search(r"chain\s+\w+\s*\{", config_text):
            return NFTABLES
        # ufw detection
        if "status:" in text or re.search(r"\d+\s+ALLOW\s", config_text):
            return UFW
        if "ufw" in text:
            return UFW
        # pf detection
        if "pass in" in text or "block in" in text or "pass out" in text:
            return PF
        if re.search(r"^(set|scrub|antispoof)\s", config_text, re.MULTILINE):
            return PF
        return IPTABLES  # default fallback

    # -----------------------------------------------------------------------
    # iptables parser
    # -----------------------------------------------------------------------

    def _parse_iptables(self, config_text: str) -> dict[str, Any]:
        """Parse iptables -L or iptables-save output."""
        rules: list[dict[str, Any]] = []
        default_policy: dict[str, str] = {}
        open_ports: list[int | str] = []
        blocked_ports: list[int | str] = []
        nat_rules: list[dict[str, Any]] = []
        logging_rules: list[str] = []
        zones: list[str] = []
        rule_count: dict[str, int] = {}

        current_chain = ""

        for line in config_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Chain header: "Chain INPUT (policy DROP)"
            chain_match = re.match(
                r"Chain\s+(\S+)\s+\(policy\s+(\w+)\)", line,
            )
            if chain_match:
                current_chain = chain_match.group(1)
                default_policy[current_chain] = chain_match.group(2)
                rule_count[current_chain] = 0
                continue

            # Skip header rows
            if line.startswith("target") or line.startswith("num"):
                continue

            # iptables-save format: -A CHAIN ...
            save_match = re.match(r"-A\s+(\S+)\s+(.*)", line)
            if save_match:
                current_chain = save_match.group(1)
                rest = save_match.group(2)
                rule = self._parse_iptables_rule_tokens(current_chain, rest)
                rules.append(rule)
                rule_count[current_chain] = rule_count.get(current_chain, 0) + 1

                if rule["action"].upper() == "LOG":
                    logging_rules.append(line)
                if rule["action"].upper() in ("ACCEPT",) and rule.get("port"):
                    open_ports.append(rule["port"])
                if rule["action"].upper() in ("DROP", "REJECT") and rule.get("port"):
                    blocked_ports.append(rule["port"])
                continue

            # iptables -L verbose format
            parts = line.split()
            if len(parts) >= 4 and current_chain:
                rule = self._parse_iptables_list_line(current_chain, parts, line)
                if rule:
                    rules.append(rule)
                    rule_count[current_chain] = rule_count.get(current_chain, 0) + 1

                    if rule["action"].upper() == "LOG":
                        logging_rules.append(line)
                    if rule["action"].upper() in ("ACCEPT",) and rule.get("port"):
                        open_ports.append(rule["port"])
                    if rule["action"].upper() in ("DROP", "REJECT") and rule.get("port"):
                        blocked_ports.append(rule["port"])

        # Detect interfaces as zones
        for r in rules:
            for field in ("source", "destination"):
                val = r.get(field, "")
                if val and val not in ("anywhere", "0.0.0.0/0", ""):
                    if val not in zones:
                        zones.append(val)

        return {
            "default_policy": default_policy,
            "rules": rules,
            "open_ports": sorted(set(open_ports)),
            "blocked_ports": sorted(set(blocked_ports)),
            "zones": zones,
            "nat_rules": nat_rules,
            "logging": logging_rules,
            "rule_count": rule_count,
        }

    def _parse_iptables_rule_tokens(
        self, chain: str, rest: str,
    ) -> dict[str, Any]:
        """Parse an iptables-save style rule line after -A CHAIN."""
        rule: dict[str, Any] = {
            "chain": chain,
            "protocol": "",
            "source": "",
            "destination": "",
            "port": "",
            "action": "",
            "comment": "",
            "raw": f"-A {chain} {rest}",
        }
        tokens = rest.split()
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok == "-p" and i + 1 < len(tokens):
                rule["protocol"] = tokens[i + 1]
                i += 2
            elif tok == "-s" and i + 1 < len(tokens):
                rule["source"] = tokens[i + 1]
                i += 2
            elif tok == "-d" and i + 1 < len(tokens):
                rule["destination"] = tokens[i + 1]
                i += 2
            elif tok == "--dport" and i + 1 < len(tokens):
                rule["port"] = tokens[i + 1]
                i += 2
            elif tok == "--sport" and i + 1 < len(tokens):
                rule["source_port"] = tokens[i + 1]
                i += 2
            elif tok == "-j" and i + 1 < len(tokens):
                rule["action"] = tokens[i + 1]
                i += 2
            elif tok == "-i" and i + 1 < len(tokens):
                rule["interface_in"] = tokens[i + 1]
                i += 2
            elif tok == "-o" and i + 1 < len(tokens):
                rule["interface_out"] = tokens[i + 1]
                i += 2
            elif tok == "--comment" and i + 1 < len(tokens):
                rule["comment"] = tokens[i + 1].strip('"')
                i += 2
            else:
                i += 1
        return rule

    @staticmethod
    def _parse_iptables_list_line(
        chain: str, parts: list[str], raw: str,
    ) -> dict[str, Any] | None:
        """Parse a line from iptables -L -v output."""
        # Typical: target prot opt source destination [extras]
        if len(parts) < 5:
            return None
        action = parts[0]
        protocol = parts[1]
        source = parts[3] if len(parts) > 3 else ""
        destination = parts[4] if len(parts) > 4 else ""

        port = ""
        port_match = re.search(r"dpt:(\S+)", raw)
        if port_match:
            port = port_match.group(1)

        return {
            "chain": chain,
            "protocol": protocol,
            "source": source,
            "destination": destination,
            "port": port,
            "action": action,
            "comment": "",
            "raw": raw,
        }

    # -----------------------------------------------------------------------
    # nftables parser
    # -----------------------------------------------------------------------

    def _parse_nftables(self, config_text: str) -> dict[str, Any]:
        """Parse nftables configuration."""
        rules: list[dict[str, Any]] = []
        default_policy: dict[str, str] = {}
        open_ports: list[int | str] = []
        blocked_ports: list[int | str] = []
        nat_rules: list[dict[str, Any]] = []
        logging_rules: list[str] = []
        zones: list[str] = []
        rule_count: dict[str, int] = {}

        current_chain = ""

        for line in config_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Chain definition with policy
            chain_match = re.match(
                r"type\s+\w+\s+hook\s+(\w+)\s+priority\s+\d+;\s*policy\s+(\w+);",
                stripped,
            )
            if chain_match:
                current_chain = chain_match.group(1)
                default_policy[current_chain] = chain_match.group(2)
                rule_count[current_chain] = 0
                continue

            # Chain name
            chain_name_match = re.match(r"chain\s+(\w+)\s*\{", stripped)
            if chain_name_match:
                current_chain = chain_name_match.group(1)
                if current_chain not in rule_count:
                    rule_count[current_chain] = 0
                continue

            # Rules with actions
            if any(
                action in stripped
                for action in ("accept", "drop", "reject", "log", "counter")
            ):
                rule = self._parse_nftables_rule(current_chain, stripped)
                if rule:
                    rules.append(rule)
                    rule_count[current_chain] = rule_count.get(current_chain, 0) + 1

                    if "log" in stripped.lower():
                        logging_rules.append(stripped)
                    if "accept" in stripped and rule.get("port"):
                        open_ports.append(rule["port"])
                    if ("drop" in stripped or "reject" in stripped) and rule.get("port"):
                        blocked_ports.append(rule["port"])
                    if "dnat" in stripped.lower() or "snat" in stripped.lower() or "masquerade" in stripped.lower():
                        nat_rules.append(rule)

            # Interface references
            iif_match = re.search(r'(?:iifname|oifname)\s+"?(\w+)"?', stripped)
            if iif_match:
                iface = iif_match.group(1)
                if iface not in zones:
                    zones.append(iface)

        return {
            "default_policy": default_policy,
            "rules": rules,
            "open_ports": sorted(set(open_ports)),
            "blocked_ports": sorted(set(blocked_ports)),
            "zones": zones,
            "nat_rules": nat_rules,
            "logging": logging_rules,
            "rule_count": rule_count,
        }

    @staticmethod
    def _parse_nftables_rule(
        chain: str, line: str,
    ) -> dict[str, Any] | None:
        """Parse a single nftables rule line."""
        rule: dict[str, Any] = {
            "chain": chain,
            "protocol": "",
            "source": "",
            "destination": "",
            "port": "",
            "action": "",
            "comment": "",
            "raw": line,
        }

        # Protocol
        proto_match = re.search(r"\b(tcp|udp|icmp|icmpv6)\b", line)
        if proto_match:
            rule["protocol"] = proto_match.group(1)

        # Port
        port_match = re.search(r"dport\s+(\S+)", line)
        if port_match:
            rule["port"] = port_match.group(1)

        # Source/dest
        src_match = re.search(r"saddr\s+(\S+)", line)
        if src_match:
            rule["source"] = src_match.group(1)
        dst_match = re.search(r"daddr\s+(\S+)", line)
        if dst_match:
            rule["destination"] = dst_match.group(1)

        # Action (last keyword)
        for action in ("accept", "drop", "reject", "log", "masquerade"):
            if action in line.lower():
                rule["action"] = action
                # Don't break — take the last meaningful action
        # But if log + drop, prefer drop
        if "drop" in line.lower():
            rule["action"] = "drop"
        elif "reject" in line.lower():
            rule["action"] = "reject"
        elif "accept" in line.lower():
            rule["action"] = "accept"

        # Comment
        comment_match = re.search(r'comment\s+"([^"]*)"', line)
        if comment_match:
            rule["comment"] = comment_match.group(1)

        return rule

    # -----------------------------------------------------------------------
    # ufw parser
    # -----------------------------------------------------------------------

    def _parse_ufw(self, config_text: str) -> dict[str, Any]:
        """Parse ufw status verbose output."""
        rules: list[dict[str, Any]] = []
        default_policy: dict[str, str] = {}
        open_ports: list[int | str] = []
        blocked_ports: list[int | str] = []
        logging_rules: list[str] = []
        zones: list[str] = []
        rule_count: dict[str, int] = {"INPUT": 0, "OUTPUT": 0}

        for line in config_text.splitlines():
            stripped = line.strip()

            # Default policies: "Default: deny (incoming), allow (outgoing), deny (routed)"
            default_match = re.search(
                r"Default:\s*(\w+)\s*\(incoming\).*?(\w+)\s*\(outgoing\)",
                stripped,
            )
            if default_match:
                default_policy["INPUT"] = default_match.group(1)
                default_policy["OUTPUT"] = default_match.group(2)
                routed = re.search(r"(\w+)\s*\(routed\)", stripped)
                if routed:
                    default_policy["FORWARD"] = routed.group(1)
                continue

            # Logging level
            log_match = re.search(r"Logging:\s*(\w+)\s*\((\w+)\)", stripped)
            if log_match:
                logging_rules.append(f"logging: {log_match.group(1)} ({log_match.group(2)})")
                continue

            # Rules: "22/tcp    ALLOW IN    Anywhere"
            rule_match = re.match(
                r"(\S+)\s+(ALLOW|DENY|REJECT|LIMIT)\s+(IN|OUT)?\s*(.*)",
                stripped,
            )
            if rule_match:
                port_proto = rule_match.group(1)
                action = rule_match.group(2)
                direction = rule_match.group(3) or "IN"
                source = rule_match.group(4).strip()

                port = port_proto.split("/")[0] if "/" in port_proto else port_proto
                protocol = port_proto.split("/")[1] if "/" in port_proto else ""

                chain = "INPUT" if direction == "IN" else "OUTPUT"

                rule = {
                    "chain": chain,
                    "protocol": protocol,
                    "source": source,
                    "destination": "",
                    "port": port,
                    "action": action,
                    "comment": "",
                    "raw": stripped,
                }
                rules.append(rule)
                rule_count[chain] = rule_count.get(chain, 0) + 1

                if action == "ALLOW" and port:
                    open_ports.append(port)
                elif action in ("DENY", "REJECT") and port:
                    blocked_ports.append(port)

                if "LIMIT" in action:
                    rule["rate_limit"] = True

        return {
            "default_policy": default_policy,
            "rules": rules,
            "open_ports": sorted(set(open_ports)),
            "blocked_ports": sorted(set(blocked_ports)),
            "zones": zones,
            "nat_rules": [],
            "logging": logging_rules,
            "rule_count": rule_count,
        }

    # -----------------------------------------------------------------------
    # pf parser (OpenBSD)
    # -----------------------------------------------------------------------

    def _parse_pf(self, config_text: str) -> dict[str, Any]:
        """Parse pf.conf configuration."""
        rules: list[dict[str, Any]] = []
        default_policy: dict[str, str] = {}
        open_ports: list[int | str] = []
        blocked_ports: list[int | str] = []
        nat_rules: list[dict[str, Any]] = []
        logging_rules: list[str] = []
        zones: list[str] = []
        rule_count: dict[str, int] = {}
        macros: dict[str, str] = {}

        for line in config_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Macros
            macro_match = re.match(r'(\w+)\s*=\s*"?(.+?)"?\s*$', stripped)
            if macro_match and not stripped.startswith(("pass", "block", "match", "set")):
                macros[macro_match.group(1)] = macro_match.group(2)
                continue

            # Set options
            if stripped.startswith("set"):
                continue

            # Block/pass rules
            rule_match = re.match(
                r"(block|pass)\s+(in|out)?\s*(log)?\s*(quick)?\s*(.*)",
                stripped,
            )
            if rule_match:
                action = rule_match.group(1)
                direction = rule_match.group(2) or ""
                has_log = rule_match.group(3) is not None
                rest = rule_match.group(5) or ""

                chain = "INPUT" if direction == "in" else "OUTPUT" if direction == "out" else "FILTER"
                rule_count[chain] = rule_count.get(chain, 0) + 1

                protocol = ""
                proto_m = re.search(r"proto\s+(\w+)", rest)
                if proto_m:
                    protocol = proto_m.group(1)

                port = ""
                port_m = re.search(r"port\s+(\S+)", rest)
                if port_m:
                    port = port_m.group(1)

                source = ""
                src_m = re.search(r"from\s+(\S+)", rest)
                if src_m:
                    source = src_m.group(1)

                destination = ""
                dst_m = re.search(r"to\s+(\S+)", rest)
                if dst_m:
                    destination = dst_m.group(1)

                # Interface as zone
                on_m = re.search(r"on\s+(\w+)", rest)
                if on_m:
                    iface = on_m.group(1)
                    if iface not in zones:
                        zones.append(iface)

                rule = {
                    "chain": chain,
                    "protocol": protocol,
                    "source": source,
                    "destination": destination,
                    "port": port,
                    "action": action.upper(),
                    "comment": "",
                    "raw": stripped,
                }
                rules.append(rule)

                if has_log:
                    logging_rules.append(stripped)
                if action == "pass" and port:
                    open_ports.append(port)
                if action == "block" and port:
                    blocked_ports.append(port)

            # Default block policy
            if re.match(r"block\s+(all|in\s+all|return\s+all)", stripped):
                default_policy["INPUT"] = "block"
                default_policy["FORWARD"] = "block"

            # NAT
            if stripped.startswith("match") and "nat-to" in stripped:
                nat_rules.append({
                    "raw": stripped,
                    "action": "nat",
                })

            # Antispoof
            if stripped.startswith("antispoof"):
                rules.append({
                    "chain": "INPUT",
                    "protocol": "",
                    "source": "10.0.0.0/8",
                    "destination": "",
                    "port": "",
                    "action": "DROP",
                    "comment": "antispoof",
                    "raw": stripped,
                })

        return {
            "default_policy": default_policy,
            "rules": rules,
            "open_ports": sorted(set(open_ports)),
            "blocked_ports": sorted(set(blocked_ports)),
            "zones": zones,
            "nat_rules": nat_rules,
            "logging": logging_rules,
            "rule_count": rule_count,
            "macros": macros,
        }

    # -----------------------------------------------------------------------
    # Rule explanation helpers
    # -----------------------------------------------------------------------

    def _explain_iptables_rule(
        self, rule_text: str,
    ) -> tuple[str, list[str], dict[str, str]]:
        """Explain an iptables rule."""
        concerns: list[str] = []

        # Parse tokens
        parts: dict[str, str] = {}
        tokens = rule_text.split()
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in ("-A", "-p", "-s", "-d", "-j", "-i", "-o", "--dport", "--sport", "-m"):
                if i + 1 < len(tokens):
                    parts[tok] = tokens[i + 1]
                    i += 2
                    continue
            i += 1

        chain = parts.get("-A", "unknown")
        protocol = parts.get("-p", "any")
        source = parts.get("-s", "anywhere")
        dest = parts.get("-d", "anywhere")
        dport = parts.get("--dport", "any")
        action = parts.get("-j", "unknown")
        iface_in = parts.get("-i", "")
        iface_out = parts.get("-o", "")

        # Build explanation
        direction = "incoming" if chain.upper() == "INPUT" else "outgoing" if chain.upper() == "OUTPUT" else "forwarded"
        proto_str = f" {protocol}" if protocol != "any" else ""
        port_str = f" on port {dport}" if dport != "any" else ""
        src_str = f" from {source}" if source != "anywhere" else ""
        dst_str = f" to {dest}" if dest != "anywhere" else ""
        iface_str = f" on interface {iface_in or iface_out}" if (iface_in or iface_out) else ""

        explanation = (
            f"This rule {action.upper()}s {direction}{proto_str} traffic"
            f"{src_str}{dst_str}{port_str}{iface_str} "
            f"in the {chain} chain."
        )

        # Concerns
        if source == "anywhere" and action.upper() == "ACCEPT":
            concerns.append("Accepts from any source — consider restricting to specific IPs.")
        if dport == "any" and action.upper() == "ACCEPT":
            concerns.append("No port restriction — allows traffic on all ports.")
        if protocol == "any" and action.upper() == "ACCEPT":
            concerns.append("No protocol restriction — matches TCP, UDP, and all others.")

        # Equivalents
        port_clause = f" port {dport}" if dport != "any" else ""
        proto_clause = f" {protocol}" if protocol != "any" else ""
        src_nft = f" saddr {source}" if source != "anywhere" else ""
        nft_action = action.lower()

        equivalents = {
            "iptables": rule_text,
            "nftables": f"nft add rule inet filter {chain.lower()}{proto_clause}{src_nft} dport {dport} {nft_action}" if dport != "any" else f"nft add rule inet filter {chain.lower()}{proto_clause}{src_nft} {nft_action}",
            "ufw": self._to_ufw_equivalent(action, dport, protocol, source),
        }

        return explanation, concerns, equivalents

    def _explain_nftables_rule(
        self, rule_text: str,
    ) -> tuple[str, list[str], dict[str, str]]:
        """Explain an nftables rule."""
        concerns: list[str] = []

        protocol = ""
        proto_m = re.search(r"\b(tcp|udp|icmp)\b", rule_text)
        if proto_m:
            protocol = proto_m.group(1)

        port = ""
        port_m = re.search(r"dport\s+(\S+)", rule_text)
        if port_m:
            port = port_m.group(1)

        source = ""
        src_m = re.search(r"saddr\s+(\S+)", rule_text)
        if src_m:
            source = src_m.group(1)

        action = "unknown"
        for a in ("accept", "drop", "reject"):
            if a in rule_text.lower():
                action = a

        has_limit = "limit" in rule_text.lower()
        has_ct = "ct state" in rule_text.lower()

        proto_str = f" {protocol}" if protocol else ""
        port_str = f" on port {port}" if port else ""
        src_str = f" from {source}" if source else ""
        limit_str = " with rate limiting" if has_limit else ""
        ct_str = " for tracked connections" if has_ct else ""

        explanation = (
            f"This nftables rule {action}s{proto_str} traffic"
            f"{src_str}{port_str}{limit_str}{ct_str}."
        )

        if not source and action == "accept":
            concerns.append("Accepts from any source.")
        if not port and action == "accept" and not has_ct:
            concerns.append("No port restriction on accept rule.")

        equivalents = {
            "nftables": rule_text,
            "iptables": self._nft_to_iptables(protocol, source, port, action),
            "ufw": self._to_ufw_equivalent(action, port, protocol, source),
        }

        return explanation, concerns, equivalents

    def _explain_ufw_rule(
        self, rule_text: str,
    ) -> tuple[str, list[str], dict[str, str]]:
        """Explain a ufw rule."""
        concerns: list[str] = []
        explanation = f"UFW rule: {rule_text}"

        match = re.match(r"ufw\s+(allow|deny|reject|limit)\s+(.*)", rule_text, re.IGNORECASE)
        if match:
            action = match.group(1)
            rest = match.group(2)
            explanation = f"This rule {action}s {rest} via ufw."
            if action.lower() == "allow" and "from" not in rest.lower():
                concerns.append("Allows from any source.")

        port_m = re.search(r"(\d+)(?:/(\w+))?", rule_text)
        port = port_m.group(1) if port_m else ""
        protocol = port_m.group(2) if port_m and port_m.group(2) else "tcp"

        equivalents = {
            "ufw": rule_text,
            "iptables": f"iptables -A INPUT -p {protocol} --dport {port} -j ACCEPT" if port else rule_text,
            "nftables": f"nft add rule inet filter input {protocol} dport {port} accept" if port else rule_text,
        }

        return explanation, concerns, equivalents

    def _explain_pf_rule(
        self, rule_text: str,
    ) -> tuple[str, list[str], dict[str, str]]:
        """Explain a pf rule."""
        concerns: list[str] = []

        action = "pass" if rule_text.startswith("pass") else "block"
        direction = "in" if " in " in rule_text else "out" if " out " in rule_text else ""
        proto_m = re.search(r"proto\s+(\w+)", rule_text)
        protocol = proto_m.group(1) if proto_m else ""
        port_m = re.search(r"port\s+(\S+)", rule_text)
        port = port_m.group(1) if port_m else ""
        src_m = re.search(r"from\s+(\S+)", rule_text)
        source = src_m.group(1) if src_m else "any"

        dir_str = f" {direction}bound" if direction else ""
        proto_str = f" {protocol}" if protocol else ""
        port_str = f" on port {port}" if port else ""
        src_str = f" from {source}" if source != "any" else ""

        explanation = (
            f"This pf rule {action}es{dir_str}{proto_str} traffic"
            f"{src_str}{port_str}."
        )

        if source == "any" and action == "pass":
            concerns.append("Passes traffic from any source.")

        iptables_action = "ACCEPT" if action == "pass" else "DROP"
        chain = "INPUT" if direction == "in" else "OUTPUT" if direction == "out" else "INPUT"

        equivalents = {
            "pf": rule_text,
            "iptables": f"iptables -A {chain} -p {protocol} --dport {port} -j {iptables_action}" if port else f"iptables -A {chain} -j {iptables_action}",
            "nftables": f"nft add rule inet filter {chain.lower()} {protocol} dport {port} {iptables_action.lower()}" if port else rule_text,
        }

        return explanation, concerns, equivalents

    # -----------------------------------------------------------------------
    # Firewall generation
    # -----------------------------------------------------------------------

    def _generate_nftables(
        self,
        services: list[str],
        default_policy: str,
        enable_logging: bool,
        rate_limit_ssh: bool,
        allowed_ips: list[str],
    ) -> tuple[str, str]:
        """Generate a complete nftables config."""
        policy = "drop" if default_policy == "deny" else "accept"
        lines = [
            "#!/usr/sbin/nft -f",
            "# Shadow Security Analyzer — generated nftables config",
            "# Flush existing rules",
            "flush ruleset",
            "",
            "table inet filter {",
            "",
            "  # Anti-spoofing set",
            "  set bogons {",
            "    type ipv4_addr",
            "    flags interval",
            "    elements = {",
            "      10.0.0.0/8,",
            "      172.16.0.0/12,",
            "      192.168.0.0/16,",
            "      127.0.0.0/8",
            "    }",
            "  }",
            "",
        ]

        # Allowed IPs set
        if allowed_ips:
            lines.extend([
                "  set allowed_ips {",
                "    type ipv4_addr",
                "    elements = {",
            ])
            for ip in allowed_ips:
                lines.append(f"      {ip},")
            lines.extend(["    }", "  }", ""])

        # INPUT chain
        lines.extend([
            "  chain input {",
            f"    type filter hook input priority 0; policy {policy};",
            "",
            "    # Loopback — accept all",
            '    iifname "lo" accept',
            "",
            "    # Connection tracking — stateful inspection",
            "    ct state established,related accept",
            "    ct state invalid drop",
            "",
            "    # Anti-spoofing — drop private IPs on public interface",
            '    iifname != "lo" ip saddr @bogons drop',
            "",
            "    # ICMP — allow essential types with rate limit",
            "    ip protocol icmp icmp type echo-request limit rate 5/second accept",
            "    ip protocol icmp icmp type { destination-unreachable, time-exceeded, echo-reply } accept",
            "",
        ])

        # Logging dropped packets
        if enable_logging:
            lines.extend([
                '    # Log dropped packets',
                '    log prefix "nft_drop: " counter drop',
                "",
            ])

        # SSH with rate limiting
        if "ssh" in services:
            if rate_limit_ssh:
                lines.extend([
                    "    # SSH — rate limited (brute-force protection)",
                    "    tcp dport 22 ct state new limit rate 4/minute accept",
                    '    tcp dport 22 ct state new log prefix "ssh_brute: " drop',
                    "",
                ])
            else:
                lines.append("    tcp dport 22 accept")
                lines.append("")

        # Other services
        for svc in services:
            if svc == "ssh":
                continue
            info = _SERVICE_PORTS.get(svc)
            if info:
                port = info["port"]
                proto = info["protocol"]
                if proto == "tcp/udp":
                    lines.append(f"    # {svc}")
                    lines.append(f"    tcp dport {port} accept")
                    lines.append(f"    udp dport {port} accept")
                else:
                    lines.append(f"    # {svc}")
                    if allowed_ips:
                        lines.append(f"    ip saddr @allowed_ips {proto} dport {port} accept")
                    else:
                        lines.append(f"    {proto} dport {port} accept")
                lines.append("")

        lines.extend(["  }", ""])

        # OUTPUT chain
        lines.extend([
            "  chain output {",
            f"    type filter hook output priority 0; policy {policy};",
            "",
            '    # Loopback',
            '    oifname "lo" accept',
            "",
            "    # Allow established",
            "    ct state established,related accept",
            "",
            "    # Allow DNS, HTTP/S, NTP for outbound",
            "    tcp dport { 53, 80, 443 } accept",
            "    udp dport { 53, 123 } accept",
            "",
        ])

        if enable_logging:
            lines.extend([
                '    # Log dropped outbound',
                '    log prefix "nft_out_drop: " counter drop',
                "",
            ])

        lines.extend(["  }", ""])

        # FORWARD chain
        lines.extend([
            "  chain forward {",
            f"    type filter hook forward priority 0; policy drop;",
            "    # No forwarding by default",
            "  }",
            "}",
        ])

        config_text = "\n".join(lines)

        explanation = (
            f"Generated nftables config with default {policy} policy. "
            f"Services: {', '.join(services)}. "
            f"Includes: anti-spoofing, stateful inspection, loopback, "
            f"ICMP rate limiting, {'SSH brute-force protection, ' if rate_limit_ssh and 'ssh' in services else ''}"
            f"{'logging, ' if enable_logging else ''}"
            f"egress filtering."
        )

        return config_text, explanation

    def _generate_iptables(
        self,
        services: list[str],
        default_policy: str,
        enable_logging: bool,
        rate_limit_ssh: bool,
        allowed_ips: list[str],
    ) -> tuple[str, str]:
        """Generate a complete iptables config."""
        policy = "DROP" if default_policy == "deny" else "ACCEPT"
        lines = [
            "#!/bin/bash",
            "# Shadow Security Analyzer — generated iptables config",
            "",
            "# Flush existing rules",
            "iptables -F",
            "iptables -X",
            "",
            "# Default policies",
            f"iptables -P INPUT {policy}",
            f"iptables -P FORWARD DROP",
            f"iptables -P OUTPUT {policy}",
            "",
            "# Loopback",
            "iptables -A INPUT -i lo -j ACCEPT",
            "iptables -A OUTPUT -o lo -j ACCEPT",
            "",
            "# Stateful inspection",
            "iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
            "iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
            "iptables -A INPUT -m conntrack --ctstate INVALID -j DROP",
            "",
            "# Anti-spoofing",
            "iptables -A INPUT -s 10.0.0.0/8 -i eth0 -j DROP",
            "iptables -A INPUT -s 172.16.0.0/12 -i eth0 -j DROP",
            "iptables -A INPUT -s 192.168.0.0/16 -i eth0 -j DROP",
            "iptables -A INPUT -s 127.0.0.0/8 -i eth0 -j DROP",
            "",
            "# ICMP",
            "iptables -A INPUT -p icmp --icmp-type echo-request -m limit --limit 5/s -j ACCEPT",
            "iptables -A INPUT -p icmp --icmp-type destination-unreachable -j ACCEPT",
            "iptables -A INPUT -p icmp --icmp-type time-exceeded -j ACCEPT",
            "",
        ]

        if "ssh" in services:
            if rate_limit_ssh:
                lines.extend([
                    "# SSH with rate limiting",
                    "iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW -m limit --limit 4/min -j ACCEPT",
                    "iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW -j DROP",
                    "",
                ])
            else:
                lines.extend(["iptables -A INPUT -p tcp --dport 22 -j ACCEPT", ""])

        for svc in services:
            if svc == "ssh":
                continue
            info = _SERVICE_PORTS.get(svc)
            if info:
                port = info["port"]
                proto = info["protocol"]
                if proto == "tcp/udp":
                    lines.append(f"# {svc}")
                    lines.append(f"iptables -A INPUT -p tcp --dport {port} -j ACCEPT")
                    lines.append(f"iptables -A INPUT -p udp --dport {port} -j ACCEPT")
                else:
                    lines.append(f"# {svc}")
                    lines.append(f"iptables -A INPUT -p {proto} --dport {port} -j ACCEPT")
                lines.append("")

        # Egress
        lines.extend([
            "# Outbound — DNS, HTTP/S, NTP",
            "iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT",
            "iptables -A OUTPUT -p udp --dport 53 -j ACCEPT",
            "iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT",
            "iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT",
            "iptables -A OUTPUT -p udp --dport 123 -j ACCEPT",
            "",
        ])

        if enable_logging:
            lines.extend([
                "# Log dropped",
                'iptables -A INPUT -j LOG --log-prefix "iptables_drop: "',
                'iptables -A OUTPUT -j LOG --log-prefix "iptables_out_drop: "',
                "",
            ])

        config_text = "\n".join(lines)
        explanation = (
            f"Generated iptables config with default {policy} policy. "
            f"Services: {', '.join(services)}. "
            f"Includes anti-spoofing, stateful inspection, ICMP handling, "
            f"{'SSH rate limiting, ' if rate_limit_ssh and 'ssh' in services else ''}"
            f"{'logging, ' if enable_logging else ''}egress filtering."
        )

        return config_text, explanation

    # -----------------------------------------------------------------------
    # Conversion helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _to_ufw_equivalent(
        action: str, port: str, protocol: str, source: str,
    ) -> str:
        """Build a ufw equivalent rule string."""
        ufw_action = "allow" if action.upper() in ("ACCEPT", "accept") else "deny"
        if not port:
            return f"ufw {ufw_action} from {source}" if source else f"ufw default {ufw_action} incoming"
        proto_str = f"/{protocol}" if protocol else ""
        src_str = f" from {source}" if source and source not in ("anywhere", "0.0.0.0/0") else ""
        return f"ufw {ufw_action}{src_str} to any port {port}{proto_str}"

    @staticmethod
    def _nft_to_iptables(
        protocol: str, source: str, port: str, action: str,
    ) -> str:
        """Convert nftables parameters to iptables rule."""
        ipt_action = "ACCEPT" if action == "accept" else "DROP" if action == "drop" else "REJECT"
        parts = ["iptables", "-A", "INPUT"]
        if protocol:
            parts.extend(["-p", protocol])
        if source:
            parts.extend(["-s", source])
        if port:
            parts.extend(["--dport", port])
        parts.extend(["-j", ipt_action])
        return " ".join(parts)
