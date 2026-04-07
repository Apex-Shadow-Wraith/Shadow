"""Sentinel Threat Intelligence — attack pattern analysis and defense profiling.

WHITE HAT ONLY. Studies attack patterns to build defenses. Never generates
executable exploit code, shellcode, or offensive payloads. This is purely
educational and defensive documentation.

HARD CONSTRAINT: All content is for DETECTION and DEFENSE. Nothing here
can be used to attack systems. Sentinel defends only.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attack pattern knowledge base — defensive reference only
# ---------------------------------------------------------------------------
_ATTACK_PATTERNS: dict[str, dict[str, Any]] = {
    # --- Network ---
    "port_scanning": {
        "name": "Port Scanning",
        "category": "network",
        "how_it_works": (
            "Attacker sends connection attempts (SYN, FIN, XMAS, NULL packets) "
            "to a range of ports on a target to discover which services are running. "
            "Tools like nmap automate this with various scan techniques. The goal is "
            "reconnaissance — mapping the attack surface before exploitation."
        ),
        "indicators": [
            "Rapid connection attempts across many ports from a single IP",
            "Half-open (SYN) connections that never complete the handshake",
            "Unusual packet flags (FIN without prior SYN, XMAS tree packets)",
            "Sequential or patterned port access from same source",
        ],
        "detection_methods": [
            "Monitor for >20 connection attempts to different ports within 60 seconds",
            "Track SYN packets without corresponding ACK completions",
            "Alert on connections to commonly-targeted ports (22, 23, 445, 3389)",
            "Correlate failed connections from the same source IP",
        ],
        "defense_strategies": [
            "Rate-limit new connections per source IP (most effective)",
            "Drop packets to unused ports silently (don't reject — reduces info leakage)",
            "Use port knocking for sensitive services",
            "Segment network to limit scan scope",
            "Keep attack surface minimal — disable unnecessary services",
        ],
        "tools_for_detection": [
            "Suricata with ET Open ruleset",
            "fail2ban with portscan filter",
            "psad (Port Scan Attack Detector)",
            "Zeek conn.log analysis",
        ],
        "shadow_relevance": {
            "level": "high",
            "reason": (
                "Shadow runs on an always-on server with multiple services "
                "(Ollama, Telegram bot). Port scanning is the most common "
                "first step in targeting internet-facing hosts."
            ),
        },
        "example_signature": (
            'alert tcp any any -> $HOME_NET any (msg:"Potential port scan - '
            'multiple ports from single source"; '
            "threshold:type threshold, track by_src, count 25, seconds 60; "
            'sid:1000001; rev:1;)'
        ),
    },
    "syn_flood": {
        "name": "SYN Flood",
        "category": "network",
        "how_it_works": (
            "Attacker sends a flood of TCP SYN packets with spoofed source IPs. "
            "The server allocates resources for each half-open connection, waiting "
            "for ACK replies that never come. This exhausts the connection table "
            "and prevents legitimate connections."
        ),
        "indicators": [
            "Massive spike in SYN packets without corresponding ACKs",
            "Connection table filling rapidly",
            "Many half-open connections from diverse source IPs",
            "Server becoming unresponsive to new connections",
        ],
        "detection_methods": [
            "Monitor SYN-to-ACK ratio (normal ~1:1, flood >>1:1)",
            "Track half-open connection count against baseline",
            "Alert on sudden connection table growth",
            "Monitor for spoofed source IPs (bogon ranges, impossible sources)",
        ],
        "defense_strategies": [
            "Enable SYN cookies (net.ipv4.tcp_syncookies=1) — most effective",
            "Reduce SYN-RECV timeout (net.ipv4.tcp_synack_retries=2)",
            "Increase backlog queue size",
            "Rate-limit SYN packets per source with iptables",
            "Use upstream DDoS mitigation if available",
        ],
        "tools_for_detection": [
            "netstat/ss to monitor SYN_RECV state connections",
            "Suricata flow tracking",
            "iptables connection tracking statistics",
            "Zeek notice.log for SYN flood detection",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "Shadow is a single-user server, not a high-traffic web service. "
                "SYN floods are less likely targeted at home servers but SYN cookies "
                "should still be enabled as a baseline defense."
            ),
        },
        "example_signature": (
            'alert tcp any any -> $HOME_NET any (msg:"Possible SYN flood"; '
            "flags:S,12; "
            "threshold:type both, track by_dst, count 500, seconds 10; "
            'sid:1000002; rev:1;)'
        ),
    },
    "dns_amplification": {
        "name": "DNS Amplification",
        "category": "network",
        "how_it_works": (
            "Attacker sends DNS queries with a spoofed source IP (the victim's IP) "
            "to open DNS resolvers. The resolvers send large DNS responses to the "
            "victim, amplifying the traffic volume 28-54x. This is a reflection-based "
            "DDoS attack."
        ),
        "indicators": [
            "Large volume of DNS responses without corresponding queries",
            "DNS traffic from many different resolvers",
            "Unusually large DNS packets (ANY/TXT record responses)",
            "Bandwidth saturation on inbound link",
        ],
        "detection_methods": [
            "Monitor for unsolicited DNS responses",
            "Track DNS query/response ratio",
            "Alert on large DNS packets (>512 bytes UDP)",
            "Monitor bandwidth utilization trends",
        ],
        "defense_strategies": [
            "Block incoming DNS responses not matching outgoing queries",
            "Rate-limit DNS traffic at firewall",
            "Disable open DNS resolver on local network",
            "Use BCP38/ingress filtering upstream",
            "Configure response rate limiting (RRL) on any local DNS server",
        ],
        "tools_for_detection": [
            "Suricata DNS protocol parser",
            "Zeek dns.log analysis",
            "tcpdump filtering for DNS response patterns",
            "ntopng for bandwidth analysis",
        ],
        "shadow_relevance": {
            "level": "low",
            "reason": (
                "Shadow doesn't run a public DNS resolver. Risk is being used as "
                "an amplifier if a DNS service is misconfigured, or being a victim "
                "of amplified traffic from elsewhere."
            ),
        },
        "example_signature": (
            'alert udp any 53 -> $HOME_NET any (msg:"Possible DNS amplification '
            'response flood"; dsize:>512; '
            "threshold:type both, track by_dst, count 100, seconds 10; "
            'sid:1000003; rev:1;)'
        ),
    },
    "arp_spoofing": {
        "name": "ARP Spoofing",
        "category": "network",
        "how_it_works": (
            "Attacker sends forged ARP replies to associate their MAC address with "
            "the IP of another host (usually the default gateway). Traffic intended "
            "for the gateway flows through the attacker, enabling man-in-the-middle "
            "interception on the local network."
        ),
        "indicators": [
            "Multiple IPs resolving to the same MAC address",
            "ARP replies without corresponding ARP requests",
            "Frequent ARP table changes for gateway IP",
            "Duplicate IP detection alerts",
        ],
        "detection_methods": [
            "Monitor ARP table for unexpected MAC changes on gateway",
            "Detect gratuitous ARP packets from unknown sources",
            "Compare ARP responses against static ARP entries",
            "Watch for duplicate IP address warnings from OS",
        ],
        "defense_strategies": [
            "Use static ARP entries for critical hosts (gateway, DNS)",
            "Enable Dynamic ARP Inspection (DAI) on managed switches",
            "Use encrypted protocols (HTTPS, SSH) to mitigate interception",
            "Segment network with VLANs",
            "Monitor with arpwatch for MAC/IP changes",
        ],
        "tools_for_detection": [
            "arpwatch — monitors ARP activity and reports changes",
            "Zeek arp.log for ARP anomaly detection",
            "Suricata ARP detection rules",
            "arping for manual ARP verification",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "Shadow communicates with Ollama and APIs over the local network. "
                "ARP spoofing on the home network could intercept API keys in "
                "transit if not using encrypted channels."
            ),
        },
        "example_signature": (
            "# arpwatch config for Shadow's network\n"
            "# Monitor for unexpected MAC changes on gateway\n"
            "arpwatch -i eth0 -d -f /var/lib/arpwatch/arp.dat"
        ),
    },
    "man_in_the_middle": {
        "name": "Man-in-the-Middle (MITM)",
        "category": "network",
        "how_it_works": (
            "Attacker positions themselves between two communicating parties, "
            "intercepting and potentially modifying traffic. Often achieved via "
            "ARP spoofing, DNS poisoning, or rogue Wi-Fi access points. Can "
            "capture credentials, inject content, or modify data in transit."
        ),
        "indicators": [
            "Certificate warnings or mismatches in HTTPS connections",
            "Unexpected ARP table changes",
            "DNS responses pointing to unexpected IPs",
            "Increased latency on specific connections",
            "Rogue DHCP servers on the network",
        ],
        "detection_methods": [
            "Certificate pinning for critical connections",
            "Monitor for ARP and DNS anomalies",
            "Track TLS certificate fingerprints for known services",
            "Detect rogue DHCP offers",
        ],
        "defense_strategies": [
            "Use TLS/HTTPS for all communications (most effective)",
            "Implement certificate pinning for API connections",
            "Use SSH tunnels for sensitive traffic",
            "Enable HSTS on any web interfaces",
            "Use WPA3 for Wi-Fi with strong passwords",
        ],
        "tools_for_detection": [
            "Zeek ssl.log for certificate anomaly detection",
            "Suricata TLS inspection rules",
            "arpwatch for ARP layer detection",
            "mitmdetect scripts for network analysis",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "Shadow makes API calls to Anthropic, OpenAI, and Telegram. MITM "
                "could intercept API keys if TLS verification is disabled. All "
                "outbound connections should verify certificates."
            ),
        },
        "example_signature": (
            'alert tls any any -> any any (msg:"TLS certificate mismatch for '
            'known service"; tls.cert_subject; '
            'content:!"api.anthropic.com"; sid:1000005; rev:1;)'
        ),
    },
    "dns_poisoning": {
        "name": "DNS Cache Poisoning",
        "category": "network",
        "how_it_works": (
            "Attacker injects forged DNS records into a resolver's cache, causing "
            "it to return incorrect IP addresses for domain names. Victims are "
            "redirected to attacker-controlled servers without their knowledge. "
            "Exploits the lack of authentication in traditional DNS."
        ),
        "indicators": [
            "DNS responses with unexpected IP addresses for known domains",
            "TTL values inconsistent with authoritative records",
            "Multiple different answers for the same query in short time",
            "DNS traffic from unexpected sources",
        ],
        "detection_methods": [
            "Compare DNS responses against known-good records",
            "Monitor for DNS response spoofing (mismatched transaction IDs)",
            "Track DNS cache changes on local resolver",
            "Use DNSSEC validation to detect forged records",
        ],
        "defense_strategies": [
            "Enable DNSSEC validation on local resolver",
            "Use DNS-over-HTTPS (DoH) or DNS-over-TLS (DoT)",
            "Randomize source ports for DNS queries",
            "Use trusted DNS resolvers (Quad9, Cloudflare 1.1.1.1)",
            "Monitor and validate DNS responses for critical domains",
        ],
        "tools_for_detection": [
            "Zeek dns.log for response anomaly tracking",
            "Suricata DNS protocol analysis",
            "dnstracer for query path validation",
            "BIND/Unbound DNSSEC validation logging",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "Shadow resolves domains for API calls and web scraping. DNS "
                "poisoning could redirect API calls to malicious servers. Using "
                "DoH/DoT and pinning API endpoint IPs mitigates this."
            ),
        },
        "example_signature": (
            'alert dns any any -> any any (msg:"DNS response with suspicious TTL '
            'for monitored domain"; dns.query; content:"api.anthropic.com"; '
            "dns.answer; sid:1000006; rev:1;)"
        ),
    },
    # --- Application ---
    "sql_injection": {
        "name": "SQL Injection",
        "category": "application",
        "how_it_works": (
            "Attacker inserts malicious SQL statements into input fields or URL "
            "parameters that are incorporated into database queries without proper "
            "sanitization. This can read, modify, or delete database contents, "
            "bypass authentication, or execute system commands. Variants include "
            "UNION-based, blind (boolean/time-based), and second-order injection."
        ),
        "indicators": [
            "Input containing SQL keywords: UNION, SELECT, DROP, --, ;, ' OR '1'='1'",
            "Database error messages exposed in responses",
            "Unusual database query patterns in logs",
            "Time-based anomalies suggesting blind SQLi (consistent delays)",
            "Unexpected data in query results",
        ],
        "detection_methods": [
            "Input validation — reject or escape SQL metacharacters",
            "Monitor database query logs for unusual patterns",
            "Web Application Firewall (WAF) rules for SQLi signatures",
            "Track database errors and stack traces in application logs",
            "Detect time-based anomalies in response times",
        ],
        "defense_strategies": [
            "Use parameterized queries / prepared statements (most effective)",
            "Input validation with allowlists, not blocklists",
            "Least-privilege database accounts (never use root/admin for app)",
            "WAF with SQLi rule sets (OWASP ModSecurity CRS)",
            "Disable detailed database error messages in production",
            "Regular code review for query construction patterns",
        ],
        "tools_for_detection": [
            "ModSecurity WAF with OWASP Core Rule Set",
            "Suricata HTTP inspection rules",
            "SQLite audit logging (for Shadow's database)",
            "Zeek HTTP request analysis",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "Shadow uses SQLite for memory storage (Grimoire). While not web-facing, "
                "any input that flows into database queries (user messages, scraped "
                "content, API responses) could contain injection payloads. Parameterized "
                "queries in Grimoire are the primary defense."
            ),
        },
        "example_signature": (
            'alert http any any -> $HOME_NET any (msg:"SQL Injection attempt in '
            "HTTP request\"; http.uri; "
            'content:"UNION"; nocase; content:"SELECT"; nocase; distance:0; '
            'sid:1000010; rev:1;)'
        ),
    },
    "xss": {
        "name": "Cross-Site Scripting (XSS)",
        "category": "application",
        "how_it_works": (
            "Attacker injects malicious JavaScript into web pages viewed by other "
            "users. Stored XSS persists in the database; reflected XSS bounces "
            "through URL parameters; DOM-based XSS manipulates client-side scripts. "
            "Can steal session cookies, redirect users, or deface content."
        ),
        "indicators": [
            "Script tags or event handlers in user input (<script>, onerror=, onload=)",
            "Encoded script payloads (&#x3C;script&#x3E;, \\x3Cscript\\x3E)",
            "JavaScript: URI scheme in input fields",
            "Unexpected script execution in browser console",
        ],
        "detection_methods": [
            "Content Security Policy (CSP) violation reports",
            "Input scanning for HTML/JavaScript patterns",
            "WAF rules for XSS payload signatures",
            "Browser-side anomaly detection",
        ],
        "defense_strategies": [
            "Output encoding / HTML entity escaping (most effective)",
            "Content Security Policy (CSP) headers",
            "Input validation — strip or reject HTML in non-rich-text fields",
            "HTTPOnly and Secure flags on cookies",
            "Use modern frameworks with auto-escaping (React, Jinja2)",
        ],
        "tools_for_detection": [
            "ModSecurity with XSS rules",
            "Suricata HTTP content inspection",
            "CSP report-uri monitoring",
            "Browser developer tools for CSP violations",
        ],
        "shadow_relevance": {
            "level": "low",
            "reason": (
                "Shadow is primarily CLI-based with no web frontend serving other "
                "users. XSS risk is minimal but relevant if Shadow ever renders "
                "HTML content from scraped sources or serves a web UI."
            ),
        },
        "example_signature": (
            'alert http any any -> $HOME_NET any (msg:"XSS attempt - script tag '
            'in request"; http.uri; content:"<script"; nocase; '
            'sid:1000011; rev:1;)'
        ),
    },
    "csrf": {
        "name": "Cross-Site Request Forgery (CSRF)",
        "category": "application",
        "how_it_works": (
            "Attacker tricks an authenticated user's browser into making unwanted "
            "requests to a web application. The browser automatically includes "
            "session cookies, so the forged request appears legitimate. Can change "
            "passwords, transfer funds, or modify settings."
        ),
        "indicators": [
            "Requests missing CSRF tokens",
            "State-changing requests via GET method",
            "Referer header from external domains on sensitive endpoints",
            "Unexpected actions performed under user accounts",
        ],
        "detection_methods": [
            "Validate CSRF tokens on all state-changing requests",
            "Check Referer/Origin headers",
            "Monitor for state changes without proper token validation",
            "Log and alert on missing CSRF tokens",
        ],
        "defense_strategies": [
            "Synchronizer token pattern (CSRF tokens in forms)",
            "SameSite cookie attribute (Lax or Strict)",
            "Verify Origin/Referer headers",
            "Require re-authentication for sensitive actions",
            "Use POST for state-changing operations, never GET",
        ],
        "tools_for_detection": [
            "Web framework built-in CSRF middleware",
            "ModSecurity request validation rules",
            "Custom log analysis for missing tokens",
            "Suricata HTTP header inspection",
        ],
        "shadow_relevance": {
            "level": "low",
            "reason": (
                "Shadow has no web frontend with session-based auth. CSRF is "
                "irrelevant for CLI and Telegram bot interfaces. Only relevant "
                "if a web dashboard is added later."
            ),
        },
        "example_signature": (
            "# Framework-level defense (not network signature)\n"
            "# Django: MIDDLEWARE += ['django.middleware.csrf.CsrfViewMiddleware']\n"
            "# Flask: CSRFProtect(app)"
        ),
    },
    "path_traversal": {
        "name": "Path Traversal / Directory Traversal",
        "category": "application",
        "how_it_works": (
            "Attacker manipulates file path parameters using sequences like ../ "
            "to access files outside the intended directory. Can read sensitive "
            "files (/etc/passwd, config files, API keys) or overwrite critical "
            "system files if write access is available."
        ),
        "indicators": [
            "Input containing ../ or ..\\ sequences",
            "URL-encoded traversal: %2e%2e%2f, %252e%252e%252f",
            "Null byte injection attempts: %00",
            "Access attempts to /etc/passwd, /etc/shadow, web.config",
        ],
        "detection_methods": [
            "Input validation — reject paths containing .. sequences",
            "Canonicalize paths and verify they stay within allowed directory",
            "WAF rules for traversal patterns",
            "Monitor file access logs for unexpected paths",
        ],
        "defense_strategies": [
            "Canonicalize and validate all file paths (most effective)",
            "Use chroot/jail for file-serving processes",
            "Allowlist permitted directories and file extensions",
            "Never pass user input directly to file system operations",
            "Run services with minimal file system permissions",
        ],
        "tools_for_detection": [
            "ModSecurity path traversal rules",
            "Suricata HTTP URI inspection",
            "AIDE file integrity monitoring",
            "auditd file access logging",
        ],
        "shadow_relevance": {
            "level": "high",
            "reason": (
                "Shadow handles file operations (Omen code tools, quarantine, "
                "downloads). Any user input that becomes a file path must be "
                "validated. The quarantine directory and research downloads are "
                "particularly sensitive entry points."
            ),
        },
        "example_signature": (
            'alert http any any -> $HOME_NET any (msg:"Path traversal attempt '
            'in HTTP request"; http.uri; content:"../"; '
            'sid:1000014; rev:1;)'
        ),
    },
    "command_injection": {
        "name": "Command Injection / OS Command Injection",
        "category": "application",
        "how_it_works": (
            "Attacker injects operating system commands through application inputs "
            "that are passed to shell execution functions (os.system, subprocess "
            "with shell=True). Metacharacters like ;, |, &&, ` allow chaining "
            "arbitrary commands after legitimate ones."
        ),
        "indicators": [
            "Shell metacharacters in input: ;, |, &&, ||, `, $(), >",
            "Command output appearing in application responses",
            "Unexpected process creation in system logs",
            "Input containing common reconnaissance commands (id, whoami, uname)",
        ],
        "detection_methods": [
            "Input validation — reject shell metacharacters",
            "Monitor process creation for unexpected child processes",
            "Application-level logging of all shell invocations",
            "Behavioral analysis — flag input triggering shell commands",
        ],
        "defense_strategies": [
            "Never use shell=True in subprocess calls (most effective)",
            "Use subprocess with argument lists, not string concatenation",
            "Sanitize all input before any system call",
            "Run with least-privilege OS user",
            "Use allowlists for permitted commands",
            "Cerberus hook rules block shell metacharacters in tool params",
        ],
        "tools_for_detection": [
            "Suricata HTTP payload inspection",
            "auditd for process execution monitoring",
            "OSSEC/Wazuh for command execution alerts",
            "Falco for runtime syscall monitoring",
        ],
        "shadow_relevance": {
            "level": "high",
            "reason": (
                "Shadow's Omen module executes code. If user input flows into "
                "shell commands without sanitization, command injection is possible. "
                "Cerberus pre-tool hooks check for shell metacharacters as a defense."
            ),
        },
        "example_signature": (
            'alert http any any -> $HOME_NET any (msg:"OS command injection '
            "attempt\"; http.uri; "
            'pcre:"/[;|&`$]\\s*(cat|ls|id|whoami|uname|wget|curl)/i"; '
            'sid:1000015; rev:1;)'
        ),
    },
    "ssrf": {
        "name": "Server-Side Request Forgery (SSRF)",
        "category": "application",
        "how_it_works": (
            "Attacker tricks the server into making HTTP requests to internal "
            "resources that are not directly accessible from outside. Can access "
            "internal APIs, cloud metadata endpoints (169.254.169.254), or local "
            "services on localhost. Often exploited through URL parameters."
        ),
        "indicators": [
            "Requests to internal/private IP ranges (10.x, 172.16-31.x, 192.168.x)",
            "Requests to localhost/127.0.0.1 or metadata endpoints",
            "URL parameters containing IP addresses instead of domain names",
            "Unusual outbound connections from application server",
        ],
        "detection_methods": [
            "Validate and restrict URLs before server-side requests",
            "Monitor outbound connections for internal IP targets",
            "Block requests to metadata endpoints (169.254.169.254)",
            "Log all server-initiated HTTP requests",
        ],
        "defense_strategies": [
            "Allowlist permitted domains/IPs for outbound requests",
            "Block requests to private IP ranges and localhost",
            "Use a dedicated outbound proxy with URL filtering",
            "Disable unnecessary URL schemes (file://, gopher://)",
            "Validate URLs at application level before fetching",
        ],
        "tools_for_detection": [
            "Suricata HTTP request monitoring",
            "Zeek conn.log for internal connections from web server",
            "iptables rules blocking outbound to private ranges",
            "Application-level URL validation logging",
        ],
        "shadow_relevance": {
            "level": "high",
            "reason": (
                "Shadow's Reaper module fetches URLs for research. If a user or "
                "scraped content provides a URL pointing to localhost:11434 (Ollama), "
                "it could manipulate the local AI runtime. URL validation is critical."
            ),
        },
        "example_signature": (
            'alert http $HOME_NET any -> [10.0.0.0/8,172.16.0.0/12,'
            '192.168.0.0/16,127.0.0.0/8] any (msg:"SSRF - internal network '
            'request from application"; sid:1000016; rev:1;)'
        ),
    },
    "deserialization": {
        "name": "Insecure Deserialization",
        "category": "application",
        "how_it_works": (
            "Attacker manipulates serialized objects (Python pickle, Java "
            "ObjectInputStream, PHP unserialize) to execute arbitrary code when "
            "the application deserializes them. The serialized payload contains "
            "instructions that run during the deserialization process."
        ),
        "indicators": [
            "Pickle/marshal data in user-controlled input",
            "Base64-encoded serialized objects in parameters",
            "Unexpected object types after deserialization",
            "Application crashes during deserialization",
        ],
        "detection_methods": [
            "Never deserialize untrusted data (primary defense)",
            "Monitor for pickle/marshal magic bytes in input",
            "Log deserialization operations and source",
            "Type-check deserialized objects before use",
        ],
        "defense_strategies": [
            "Use JSON instead of pickle/marshal for data exchange (most effective)",
            "Never pickle.load() untrusted data",
            "Implement allowlist-based deserialization (RestrictedUnpickler)",
            "Sign serialized data with HMAC before storing/transmitting",
            "Isolate deserialization in sandboxed processes",
        ],
        "tools_for_detection": [
            "Bandit (Python) for detecting pickle.load calls",
            "Custom Suricata rules for pickle magic bytes",
            "Application-level input type validation",
            "SAST tools for deserialization sink analysis",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "Shadow uses JSON for config and SQLite for storage (safe). Risk "
                "exists if any module uses pickle for caching or inter-process "
                "communication. Avoid pickle for any data that could be tampered with."
            ),
        },
        "example_signature": (
            "# Python-level defense (not network signature)\n"
            "# NEVER: pickle.load(untrusted_data)\n"
            "# INSTEAD: json.loads(untrusted_data)"
        ),
    },
    # --- Auth ---
    "brute_force": {
        "name": "Brute Force Authentication Attack",
        "category": "auth",
        "how_it_works": (
            "Attacker systematically tries many passwords or passphrases against "
            "a login endpoint. Can be pure brute force (all combinations), "
            "dictionary-based (common passwords), or hybrid (dictionary + rules). "
            "Automated tools can attempt thousands of passwords per minute."
        ),
        "indicators": [
            "Many failed login attempts from the same IP",
            "Failed attempts across multiple usernames from one source",
            "Login attempts at unusual hours or frequencies",
            "Rapid sequential authentication requests",
            "Common password patterns in attempts (password1, admin123)",
        ],
        "detection_methods": [
            "Track failed login count per IP per time window",
            "Alert on >5 failed attempts within 5 minutes from same source",
            "Monitor authentication logs for patterns",
            "Detect distributed brute force (many IPs, same target account)",
        ],
        "defense_strategies": [
            "Account lockout after N failed attempts (most effective)",
            "Progressive delay / exponential backoff on failures",
            "fail2ban with SSH/auth jails",
            "Strong password policy + MFA",
            "Rate-limit authentication endpoints",
            "Use key-based SSH authentication instead of passwords",
        ],
        "tools_for_detection": [
            "fail2ban with sshd filter (primary defense)",
            "Suricata SSH protocol analysis",
            "Zeek notice.log for SSH brute force detection",
            "OSSEC/Wazuh authentication monitoring",
        ],
        "shadow_relevance": {
            "level": "high",
            "reason": (
                "Shadow's server has SSH access. Brute force against SSH is "
                "extremely common on internet-facing servers. fail2ban with "
                "aggressive ban thresholds is essential."
            ),
        },
        "example_signature": (
            "# fail2ban jail for SSH brute force\n"
            "[sshd]\n"
            "enabled = true\n"
            "port = ssh\n"
            "filter = sshd\n"
            "logpath = /var/log/auth.log\n"
            "maxretry = 3\n"
            "findtime = 600\n"
            "bantime = 3600"
        ),
    },
    "credential_stuffing": {
        "name": "Credential Stuffing",
        "category": "auth",
        "how_it_works": (
            "Attacker uses username/password pairs leaked from other breaches "
            "to try logging into different services. Exploits password reuse — "
            "if someone uses the same password for multiple sites, compromising "
            "one gives access to all. Automated with tools at massive scale."
        ),
        "indicators": [
            "Login attempts with many different usernames from few IPs",
            "High failure rate with occasional successes",
            "Credentials matching known breach databases",
            "Geographically impossible login patterns",
        ],
        "detection_methods": [
            "Monitor for logins from leaked credential databases",
            "Track login success/failure ratios per source",
            "Detect impossible travel (login from two distant locations)",
            "CAPTCHA after failed attempts",
        ],
        "defense_strategies": [
            "Require unique, strong passwords (password manager)",
            "Enable MFA on all accounts (most effective)",
            "Check new passwords against breach databases (HaveIBeenPwned API)",
            "Rate-limit and CAPTCHA login endpoints",
            "Monitor for credential reuse across services",
        ],
        "tools_for_detection": [
            "HaveIBeenPwned API for password checking",
            "fail2ban for rate limiting",
            "Custom log analysis for pattern detection",
            "Suricata HTTP authentication monitoring",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "Shadow's Telegram bot token and API keys could be targeted if "
                "credentials are reused. All credentials should be unique and "
                "stored securely in .env, never reused across services."
            ),
        },
        "example_signature": (
            'alert http any any -> $HOME_NET any (msg:"Credential stuffing - '
            'rapid login attempts with varying usernames"; http.method; '
            'content:"POST"; http.uri; content:"/login"; '
            "threshold:type both, track by_src, count 20, seconds 60; "
            'sid:1000020; rev:1;)'
        ),
    },
    "pass_the_hash": {
        "name": "Pass-the-Hash",
        "category": "auth",
        "how_it_works": (
            "Attacker captures password hashes (from memory, SAM database, or "
            "network traffic) and uses them directly to authenticate without "
            "knowing the plaintext password. Works because many protocols accept "
            "hashes for authentication (NTLM, NTLMv2)."
        ),
        "indicators": [
            "Authentication using NTLM hashes without corresponding logon event",
            "Unusual NTLM authentication from unexpected sources",
            "Lateral movement patterns after initial compromise",
            "Tools like mimikatz or sekurlsa in process memory",
        ],
        "detection_methods": [
            "Monitor for NTLM authentication anomalies",
            "Track lateral movement patterns",
            "Detect tools associated with hash extraction",
            "Log and alert on unusual authentication sources",
        ],
        "defense_strategies": [
            "Use Kerberos instead of NTLM where possible",
            "Enable Credential Guard (Windows) or equivalent",
            "Restrict privileged account usage",
            "Network segmentation to limit lateral movement",
            "Regular password rotation for service accounts",
        ],
        "tools_for_detection": [
            "Windows Event Log monitoring (Event ID 4624, type 3)",
            "Suricata SMB/NTLM protocol analysis",
            "Zeek smb.log and ntlm.log",
            "OSSEC/Wazuh for authentication anomaly detection",
        ],
        "shadow_relevance": {
            "level": "low",
            "reason": (
                "Shadow runs on Ubuntu/Linux, not Windows. Pass-the-hash is "
                "primarily a Windows/Active Directory attack. Linux equivalent "
                "would be SSH key theft, which is addressed separately."
            ),
        },
        "example_signature": (
            'alert smb any any -> $HOME_NET any (msg:"NTLM authentication with '
            'possible pass-the-hash"; smb.ntlmssp; '
            'sid:1000021; rev:1;)'
        ),
    },
    "session_hijacking": {
        "name": "Session Hijacking",
        "category": "auth",
        "how_it_works": (
            "Attacker steals or predicts a valid session token to impersonate "
            "an authenticated user. Methods include sniffing unencrypted traffic, "
            "XSS to steal cookies, session fixation (forcing a known session ID), "
            "or predicting weak session token generation."
        ),
        "indicators": [
            "Same session ID used from different IP addresses",
            "Session activity from impossible geographic locations",
            "Sudden change in user-agent string within a session",
            "Session tokens appearing in URL parameters or logs",
        ],
        "detection_methods": [
            "Bind sessions to IP address and user-agent",
            "Detect concurrent use of same session from different IPs",
            "Monitor for session tokens in URLs",
            "Track session usage patterns for anomalies",
        ],
        "defense_strategies": [
            "Use HTTPS for all session traffic (most effective)",
            "Set Secure, HTTPOnly, SameSite flags on session cookies",
            "Regenerate session ID after authentication",
            "Implement session timeout and absolute expiration",
            "Bind session to client fingerprint (IP + user-agent hash)",
        ],
        "tools_for_detection": [
            "Web framework session management logging",
            "Suricata HTTP cookie inspection",
            "Custom log analysis for multi-IP session usage",
            "Zeek http.log for session tracking",
        ],
        "shadow_relevance": {
            "level": "low",
            "reason": (
                "Shadow doesn't use session-based web auth. Telegram bot uses "
                "token-based auth. Risk would increase if a web dashboard is added."
            ),
        },
        "example_signature": (
            "# Application-level defense\n"
            "# session.config(httponly=True, secure=True, samesite='Strict')\n"
            "# Regenerate session ID on login"
        ),
    },
    "phishing": {
        "name": "Phishing / Spear Phishing",
        "category": "auth",
        "how_it_works": (
            "Attacker sends deceptive messages (email, SMS, Telegram) impersonating "
            "trusted entities to trick victims into revealing credentials, clicking "
            "malicious links, or downloading malware. Spear phishing targets "
            "specific individuals with personalized content."
        ),
        "indicators": [
            "Messages with urgency/fear tactics ('Your account will be locked')",
            "Mismatched sender domain (support@g00gle.com vs google.com)",
            "Links to domains that mimic legitimate services",
            "Requests for credentials or sensitive information",
            "Unexpected attachments, especially .exe, .js, .vbs",
        ],
        "detection_methods": [
            "Email header analysis (SPF, DKIM, DMARC validation)",
            "URL reputation checking against threat intelligence feeds",
            "Attachment sandboxing before delivery",
            "User reporting mechanisms for suspicious messages",
        ],
        "defense_strategies": [
            "MFA on all accounts (most effective — limits credential theft impact)",
            "SPF, DKIM, DMARC on your domain",
            "Security awareness training",
            "URL filtering and reputation checking",
            "Never click links in unexpected messages — type URLs directly",
        ],
        "tools_for_detection": [
            "SpamAssassin for email filtering",
            "PhishTank/OpenPhish URL reputation",
            "Suricata HTTP reputation rules",
            "ClamAV for attachment scanning",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "Shadow receives Telegram messages. A phishing message via Telegram "
                "could try to trick Shadow into visiting malicious URLs or executing "
                "harmful commands. Input validation and URL reputation checking help."
            ),
        },
        "example_signature": (
            "# Telegram input validation\n"
            "# Check URLs against reputation databases before fetching\n"
            "# Never auto-execute commands from unverified messages"
        ),
    },
    # --- Malware ---
    "ransomware": {
        "name": "Ransomware",
        "category": "malware",
        "how_it_works": (
            "Malware encrypts victim's files using strong encryption and demands "
            "payment (usually cryptocurrency) for the decryption key. Modern "
            "variants also exfiltrate data before encryption (double extortion). "
            "Spreads via phishing, RDP brute force, or software vulnerabilities."
        ),
        "indicators": [
            "Mass file encryption (many files modified in short time)",
            "New file extensions appearing (.encrypted, .locked, .crypt)",
            "Ransom notes (README.txt, DECRYPT_FILES.html) in directories",
            "Shadow copy deletion (vssadmin, wmic shadowcopy)",
            "Unusual CPU/disk activity during encryption",
        ],
        "detection_methods": [
            "Monitor file system for rapid mass modifications",
            "Detect new/unusual file extensions appearing en masse",
            "Track entropy changes in files (encrypted files have high entropy)",
            "Alert on shadow copy deletion commands",
            "Canary files — decoy files that trigger alert when modified",
        ],
        "defense_strategies": [
            "Offline backups following 3-2-1 rule (most effective)",
            "Keep systems patched and updated",
            "Disable RDP or use with MFA",
            "Application whitelisting to prevent unknown executables",
            "Network segmentation to limit spread",
            "Immutable backups that ransomware cannot encrypt",
        ],
        "tools_for_detection": [
            "AIDE for file integrity monitoring",
            "Suricata for known ransomware C2 detection",
            "ClamAV with updated signatures",
            "Canary token files for early detection",
        ],
        "shadow_relevance": {
            "level": "high",
            "reason": (
                "Shadow's databases (Grimoire SQLite, ChromaDB) and config files "
                "are critical. Ransomware could encrypt memory, models, and configs. "
                "Regular offline backups and file integrity monitoring are essential."
            ),
        },
        "example_signature": (
            'alert tcp $HOME_NET any -> $EXTERNAL_NET any (msg:"Possible '
            "ransomware C2 communication\"; "
            "flow:established,to_server; "
            "threshold:type both, track by_src, count 50, seconds 10; "
            'sid:1000030; rev:1;)'
        ),
    },
    "trojan": {
        "name": "Trojan Horse",
        "category": "malware",
        "how_it_works": (
            "Malware disguised as legitimate software. Unlike viruses, trojans "
            "don't self-replicate — they rely on users installing them. Once "
            "active, they provide backdoor access, steal data, download additional "
            "malware, or enroll the system in a botnet."
        ),
        "indicators": [
            "Unexpected network connections from legitimate-looking processes",
            "New scheduled tasks or cron jobs not created by admin",
            "Files with misleading names or double extensions",
            "Processes running from unusual directories (temp, downloads)",
            "Unexpected changes to system configuration",
        ],
        "detection_methods": [
            "Monitor process execution from unexpected paths",
            "Track outbound connections from non-browser processes",
            "File integrity monitoring for system binaries",
            "Scan downloads before execution",
            "Monitor for new persistence mechanisms (cron, systemd)",
        ],
        "defense_strategies": [
            "Only install software from trusted repositories (most effective)",
            "Verify checksums/signatures before installing packages",
            "Quarantine all downloads (Shadow already does this)",
            "Application whitelisting",
            "Regular integrity checks on installed software",
        ],
        "tools_for_detection": [
            "ClamAV for signature-based detection",
            "AIDE for file integrity monitoring",
            "rkhunter and chkrootkit",
            "Zeek conn.log for unexpected outbound connections",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "Shadow downloads files for research (Reaper module). All downloads "
                "land in quarantine, which is correct. Risk is if a downloaded file "
                "is moved out of quarantine and executed without scanning."
            ),
        },
        "example_signature": (
            "# File integrity check for system binaries\n"
            "aide --check --config=/etc/aide/aide.conf"
        ),
    },
    "rootkit": {
        "name": "Rootkit",
        "category": "malware",
        "how_it_works": (
            "Software that provides persistent, privileged access while hiding "
            "its presence from the operating system and security tools. Kernel "
            "rootkits modify the kernel to intercept system calls. User-mode "
            "rootkits replace or hook system utilities (ls, ps, netstat)."
        ),
        "indicators": [
            "Discrepancy between different tools' output (ls vs direct syscall)",
            "Hidden processes or network connections",
            "Modified system binaries with unexpected checksums",
            "Kernel modules that don't match known-good list",
            "Unexplained system call interception",
        ],
        "detection_methods": [
            "Compare outputs of multiple tools (cross-verification)",
            "Boot from trusted media and check system from outside",
            "Kernel module integrity verification",
            "System call table comparison against known-good values",
            "Memory forensics for hidden processes",
        ],
        "defense_strategies": [
            "Secure Boot to prevent unauthorized kernel modifications",
            "Kernel lockdown mode (Linux 5.4+)",
            "Regular rootkit scans from trusted baseline",
            "File integrity monitoring (AIDE) for system binaries",
            "Restrict kernel module loading (module signing)",
        ],
        "tools_for_detection": [
            "rkhunter (Rootkit Hunter)",
            "chkrootkit",
            "AIDE for file integrity",
            "Volatility for memory forensics",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "A rootkit on Shadow's server would be catastrophic — it could "
                "hide malicious activity from all of Shadow's monitoring. Regular "
                "rkhunter scans and AIDE checks are essential baseline defenses."
            ),
        },
        "example_signature": (
            "# Rootkit detection scan\n"
            "rkhunter --check --skip-keypress\n"
            "chkrootkit -q"
        ),
    },
    "keylogger": {
        "name": "Keylogger",
        "category": "malware",
        "how_it_works": (
            "Software or hardware that records keystrokes to capture passwords, "
            "messages, and other sensitive input. Software keyloggers hook into "
            "the keyboard input pipeline (kernel driver or user-space API). "
            "Hardware keyloggers are physical devices between keyboard and computer."
        ),
        "indicators": [
            "Unknown processes monitoring input devices",
            "Unexpected access to /dev/input/ devices on Linux",
            "Small, periodic network transmissions (logged data being exfiltrated)",
            "Unknown kernel modules intercepting keyboard input",
        ],
        "detection_methods": [
            "Monitor processes accessing input devices",
            "Check for unknown keyboard hooks",
            "Track small, periodic outbound data transfers",
            "File integrity check on input-related system files",
        ],
        "defense_strategies": [
            "Use key-based authentication instead of passwords (most effective)",
            "Virtual keyboard for sensitive input",
            "Regular process auditing",
            "Restrict access to /dev/input devices",
            "Monitor for unauthorized kernel modules",
        ],
        "tools_for_detection": [
            "auditd monitoring /dev/input access",
            "rkhunter for rootkit-style keyloggers",
            "lsmod + module signature verification",
            "Zeek for data exfiltration detection",
        ],
        "shadow_relevance": {
            "level": "low",
            "reason": (
                "Shadow is a server application — it doesn't process keyboard "
                "input directly. Risk is to the creator's workstation, not "
                "Shadow's server process."
            ),
        },
        "example_signature": (
            "# auditd rule to monitor input device access\n"
            "-w /dev/input/ -p rwa -k keylogger_detection"
        ),
    },
    "worm": {
        "name": "Network Worm",
        "category": "malware",
        "how_it_works": (
            "Self-replicating malware that spreads across networks without user "
            "interaction. Exploits vulnerabilities in network services to "
            "propagate. Once on a system, scans for other vulnerable hosts "
            "and repeats the infection cycle. Can carry additional payloads."
        ),
        "indicators": [
            "Unusual outbound scanning from internal hosts",
            "Identical malware appearing on multiple systems simultaneously",
            "Spike in network traffic from internal sources",
            "Exploitation attempts targeting known vulnerabilities",
        ],
        "detection_methods": [
            "Monitor for internal scanning activity",
            "Track unusual inter-host communication patterns",
            "Alert on rapid spread of identical files across hosts",
            "Network flow analysis for anomalous traffic patterns",
        ],
        "defense_strategies": [
            "Keep all systems patched and updated (most effective)",
            "Network segmentation to contain spread",
            "Host-based firewall on each system",
            "Disable unnecessary network services",
            "IDS/IPS for exploit detection",
        ],
        "tools_for_detection": [
            "Suricata for exploit and scan detection",
            "Zeek for network flow analysis",
            "OSSEC/Wazuh for host-level detection",
            "Nessus/OpenVAS for vulnerability scanning",
        ],
        "shadow_relevance": {
            "level": "low",
            "reason": (
                "Shadow is a single server, not a network of hosts. Worm risk "
                "is low unless the home network has many unpatched devices. "
                "Main defense is keeping Shadow's server patched."
            ),
        },
        "example_signature": (
            'alert tcp $HOME_NET any -> $HOME_NET any (msg:"Possible worm '
            "propagation - internal scanning\"; "
            "flags:S; threshold:type both, track by_src, count 50, seconds 30; "
            'sid:1000035; rev:1;)'
        ),
    },
    "botnet": {
        "name": "Botnet Enrollment",
        "category": "malware",
        "how_it_works": (
            "Malware enrolls the compromised system into a network of infected "
            "machines (botnet) controlled by a command-and-control (C2) server. "
            "The bot receives instructions to perform DDoS attacks, send spam, "
            "mine cryptocurrency, or participate in other coordinated malicious "
            "activities."
        ),
        "indicators": [
            "Periodic outbound connections to unknown IPs (beaconing)",
            "IRC, HTTP, or DNS-based C2 communication patterns",
            "System participating in activities not initiated by user",
            "High CPU/network usage during idle periods",
            "Connections to known C2 infrastructure IPs",
        ],
        "detection_methods": [
            "Monitor for periodic beaconing patterns",
            "Check outbound connections against threat intelligence feeds",
            "Detect IRC/unusual protocol usage from non-client processes",
            "Track CPU and network usage anomalies during idle time",
        ],
        "defense_strategies": [
            "Outbound firewall rules — block all except allowed services",
            "DNS sinkholing for known malicious domains",
            "Regular malware scans",
            "Monitor for C2 beaconing patterns",
            "Keep systems patched to prevent initial compromise",
        ],
        "tools_for_detection": [
            "Suricata with Emerging Threats C2 rules",
            "Zeek conn.log for beaconing analysis",
            "ClamAV for bot malware signatures",
            "threat intelligence IP/domain blocklists",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "An always-on server is a valuable botnet node. Shadow should "
                "monitor for unexpected outbound connections and beaconing patterns. "
                "Outbound firewall rules limiting connections to known services help."
            ),
        },
        "example_signature": (
            'alert tcp $HOME_NET any -> $EXTERNAL_NET any (msg:"Possible C2 '
            "beaconing - periodic outbound connections\"; "
            "flow:established,to_server; "
            "threshold:type both, track by_src, count 10, seconds 3600; "
            'sid:1000036; rev:1;)'
        ),
    },
    "cryptominer": {
        "name": "Cryptominer / Cryptojacking",
        "category": "malware",
        "how_it_works": (
            "Malware that uses the victim's computing resources to mine "
            "cryptocurrency. Can be delivered via malware, compromised websites "
            "(browser mining), or exploited servers. Consumes CPU/GPU resources "
            "and electricity, degrades system performance."
        ),
        "indicators": [
            "Sustained high CPU/GPU usage when system should be idle",
            "Connections to known mining pools (stratum protocol)",
            "Processes with mining-related names or arguments",
            "Increased electricity consumption / fan noise",
            "System performance degradation without explanation",
        ],
        "detection_methods": [
            "Monitor CPU usage trends — alert on sustained >80% when idle",
            "Detect stratum mining protocol connections",
            "Block known mining pool domains/IPs",
            "Process name and argument scanning for mining software",
        ],
        "defense_strategies": [
            "Block outbound connections to known mining pools",
            "Monitor CPU/GPU utilization trends",
            "Application whitelisting to prevent unauthorized miners",
            "Regular process auditing",
            "Browser extensions to block web miners (if applicable)",
        ],
        "tools_for_detection": [
            "Suricata with mining protocol detection rules",
            "Zeek for stratum protocol detection",
            "top/htop for CPU monitoring",
            "ClamAV for known miner signatures",
        ],
        "shadow_relevance": {
            "level": "high",
            "reason": (
                "Shadow's server runs Ollama and AI workloads. A cryptominer "
                "would compete for CPU/GPU resources, degrading AI performance. "
                "Void module should monitor for unexplained CPU usage spikes."
            ),
        },
        "example_signature": (
            'alert tcp $HOME_NET any -> $EXTERNAL_NET any (msg:"Stratum mining '
            "protocol detected\"; flow:established,to_server; "
            'content:"mining.subscribe"; sid:1000037; rev:1;)'
        ),
    },
    # --- AI-Specific ---
    "prompt_injection": {
        "name": "Prompt Injection",
        "category": "ai_specific",
        "how_it_works": (
            "Attacker crafts input that overrides or manipulates an AI system's "
            "instructions. Direct injection embeds commands in user input; indirect "
            "injection hides instructions in data the AI processes (web pages, "
            "documents, search results). Can cause the AI to ignore safety rules, "
            "reveal system prompts, or take unauthorized actions."
        ),
        "indicators": [
            "Input containing phrases like 'ignore previous instructions'",
            "Attempts to extract system prompts ('repeat your instructions')",
            "Instructions embedded in data sources (hidden text in web pages)",
            "Unusual formatting designed to confuse the AI parser",
            "Role-playing attempts to bypass safety ('pretend you are...')",
        ],
        "detection_methods": [
            "Pattern matching for known injection phrases",
            "Perplexity scoring — injection text often has different style than normal input",
            "Multi-layer validation: pre-process input before sending to model",
            "Canary tokens in system prompts to detect extraction",
            "Cerberus injection detector scoring",
        ],
        "defense_strategies": [
            "Input/output filtering at application layer (most effective)",
            "Cerberus injection detection with scoring threshold",
            "Separate system prompts from user input clearly",
            "Principle of least privilege for AI tool access",
            "Validate AI outputs before executing actions",
            "Never let AI-processed content directly become instructions",
        ],
        "tools_for_detection": [
            "Cerberus injection_detector.py (Shadow's built-in defense)",
            "Rebuff framework for prompt injection detection",
            "Custom regex patterns for injection phrases",
            "Langfuse tracing for monitoring prompt/response patterns",
        ],
        "shadow_relevance": {
            "level": "high",
            "reason": (
                "Shadow processes user input via Telegram and CLI, then routes "
                "to AI models. Prompt injection is the #1 AI-specific threat. "
                "Cerberus injection detector is Shadow's primary defense, with "
                "multi-layer validation in the decision loop."
            ),
        },
        "example_signature": (
            "# Cerberus injection detection pattern\n"
            "# Score input for injection likelihood:\n"
            "#   'ignore previous' → +0.4\n"
            "#   'system prompt' → +0.3\n"
            "#   'pretend you are' → +0.3\n"
            "# Block if score > 0.7"
        ),
    },
    "model_extraction": {
        "name": "Model Extraction / Model Stealing",
        "category": "ai_specific",
        "how_it_works": (
            "Attacker queries an AI model systematically to reconstruct a "
            "functionally equivalent copy. By sending carefully crafted inputs "
            "and analyzing outputs, the attacker builds a training dataset that "
            "can be used to train a clone model, stealing the intellectual "
            "property and capabilities."
        ),
        "indicators": [
            "Extremely high query volume from single source",
            "Systematic, non-conversational query patterns",
            "Queries designed to map decision boundaries",
            "API usage patterns consistent with automated extraction",
        ],
        "detection_methods": [
            "Rate-limit API queries per user/IP",
            "Monitor for non-conversational query patterns",
            "Detect systematic probing (similar queries with small variations)",
            "Track total query volume and patterns per user",
        ],
        "defense_strategies": [
            "Rate limiting on model API endpoints (most effective)",
            "Add controlled noise to outputs (differential privacy)",
            "Monitor and alert on extraction-like query patterns",
            "Watermark model outputs for tracing",
            "Restrict API access to authenticated users only",
        ],
        "tools_for_detection": [
            "API gateway rate limiting and monitoring",
            "Custom log analysis for query pattern detection",
            "Langfuse tracing for usage pattern analysis",
            "Application-level query fingerprinting",
        ],
        "shadow_relevance": {
            "level": "low",
            "reason": (
                "Shadow runs local models (Ollama) not exposed to the internet. "
                "Model extraction requires API access. Risk only exists if Ollama "
                "port (11434) is accidentally exposed to the network."
            ),
        },
        "example_signature": (
            "# Rate limiting for Ollama API (if exposed)\n"
            "# iptables -A INPUT -p tcp --dport 11434 -m connlimit "
            "--connlimit-above 5 -j DROP"
        ),
    },
    "training_data_poisoning": {
        "name": "Training Data Poisoning",
        "category": "ai_specific",
        "how_it_works": (
            "Attacker introduces malicious or biased data into a model's training "
            "dataset to influence its behavior. Can create backdoors (model behaves "
            "normally except on trigger inputs), bias outputs, or degrade overall "
            "quality. Particularly dangerous for continuously learning systems."
        ),
        "indicators": [
            "Unexpected changes in model behavior after training updates",
            "Responses that consistently favor specific products/viewpoints",
            "Model performance degradation on previously reliable tasks",
            "Training data with suspicious patterns or provenance",
        ],
        "detection_methods": [
            "Validate training data provenance and quality",
            "A/B test model behavior before and after training updates",
            "Monitor output distribution for unexpected shifts",
            "Statistical analysis of training data for anomalies",
        ],
        "defense_strategies": [
            "Validate and sanitize all data before ingestion (most effective)",
            "Trust levels on data sources (Shadow's Grimoire trust system)",
            "Regular model evaluation against benchmark datasets",
            "Data provenance tracking — know where every training example came from",
            "Isolate training pipelines from external input",
        ],
        "tools_for_detection": [
            "Data validation pipelines",
            "Model evaluation benchmarks",
            "Grimoire trust level system (Shadow's built-in defense)",
            "Statistical anomaly detection on training data",
        ],
        "shadow_relevance": {
            "level": "high",
            "reason": (
                "Shadow's Grimoire stores memories with trust levels. If poisoned "
                "data enters with high trust, it influences Shadow's knowledge base. "
                "The trust level system and source tracking are critical defenses."
            ),
        },
        "example_signature": (
            "# Grimoire trust validation\n"
            "# All Reddit/community data: trust_level=0.3\n"
            "# All research data: trust_level=0.5\n"
            "# Only creator-stated facts: trust_level=0.9\n"
            "# Never auto-promote trust levels"
        ),
    },
    "adversarial_inputs": {
        "name": "Adversarial Inputs / Adversarial Examples",
        "category": "ai_specific",
        "how_it_works": (
            "Attacker crafts inputs with imperceptible perturbations that cause "
            "AI models to make incorrect predictions. For text models, this can "
            "be subtle character substitutions, homoglyphs, or strategic word "
            "choices that change model behavior while appearing normal to humans."
        ),
        "indicators": [
            "Input with unusual Unicode characters or homoglyphs",
            "Text with zero-width characters or invisible formatting",
            "Input that produces unexpectedly different outputs from similar inputs",
            "Systematic probing with slight variations of the same input",
        ],
        "detection_methods": [
            "Unicode normalization before processing",
            "Strip zero-width and invisible characters",
            "Input perplexity analysis (adversarial inputs may have unusual patterns)",
            "Compare model confidence on original vs normalized input",
        ],
        "defense_strategies": [
            "Input normalization and sanitization (most effective)",
            "Ensemble models for cross-validation",
            "Adversarial training — include adversarial examples in training",
            "Input length and character set restrictions",
            "Monitor for unusual Unicode in input",
        ],
        "tools_for_detection": [
            "Unicode normalization libraries (unicodedata module)",
            "TextAttack framework for adversarial testing",
            "Custom input sanitization pipeline",
            "Langfuse for input/output pattern monitoring",
        ],
        "shadow_relevance": {
            "level": "medium",
            "reason": (
                "Shadow processes text from multiple sources (Telegram, web scraping). "
                "Adversarial text could cause misrouting, incorrect safety classification, "
                "or bypass injection detection. Input normalization is the key defense."
            ),
        },
        "example_signature": (
            "# Input normalization\n"
            "import unicodedata\n"
            "normalized = unicodedata.normalize('NFKC', user_input)\n"
            "# Strip zero-width characters\n"
            "cleaned = re.sub(r'[\\u200b-\\u200f\\u2028-\\u202f\\ufeff]', '', normalized)"
        ),
    },
    "jailbreaking": {
        "name": "AI Jailbreaking",
        "category": "ai_specific",
        "how_it_works": (
            "Attacker uses creative prompting techniques to bypass an AI model's "
            "safety constraints. Techniques include role-playing scenarios, "
            "hypothetical framing, multi-step prompt chains, encoding tricks, "
            "and persona manipulation. Goal is to make the model produce outputs "
            "it was designed to refuse."
        ),
        "indicators": [
            "Requests framed as hypothetical or fictional scenarios",
            "Role-playing prompts designed to override safety",
            "Multi-turn conversations that gradually escalate requests",
            "Encoded or obfuscated harmful requests",
            "Requests to 'pretend' safety rules don't apply",
        ],
        "detection_methods": [
            "Monitor for known jailbreak patterns and templates",
            "Track conversation trajectory for escalation patterns",
            "Score requests for safety-bypass intent",
            "Compare outputs against safety policy automatically",
        ],
        "defense_strategies": [
            "Multi-layer safety checks (Cerberus system — most effective)",
            "Input scoring for jailbreak patterns",
            "Output filtering before delivery",
            "Constitutional AI principles embedded in system prompts",
            "Regular red-teaming to discover new bypass techniques",
            "Shadow's biblical ethics framework as immutable foundation",
        ],
        "tools_for_detection": [
            "Cerberus safety_check module (Shadow's built-in defense)",
            "Langfuse tracing for prompt pattern monitoring",
            "Custom jailbreak pattern database",
            "Output safety classifier",
        ],
        "shadow_relevance": {
            "level": "high",
            "reason": (
                "Shadow has powerful tools (code execution, file operations, web "
                "access). Jailbreaking to bypass Cerberus safety checks could lead "
                "to harmful actions. Multi-layer defense (Cerberus + ethical framework "
                "+ tool hooks) is essential."
            ),
        },
        "example_signature": (
            "# Cerberus jailbreak detection\n"
            "# Flag patterns:\n"
            "#   'pretend you have no restrictions'\n"
            "#   'in a fictional world where'\n"
            "#   'DAN mode' / 'developer mode'\n"
            "#   'ignore your training'\n"
            "# Route to safety_check before processing"
        ),
    },
}

# ---------------------------------------------------------------------------
# Malware family knowledge base — defensive reference only
# ---------------------------------------------------------------------------
_MALWARE_FAMILIES: dict[str, dict[str, Any]] = {
    "wannacry": {
        "name": "WannaCry",
        "aliases": ["WCry", "WanaCrypt0r", "WannaCrypt"],
        "first_seen": "2017-05-12",
        "category": "ransomware",
        "infection_vector": (
            "Exploits EternalBlue (MS17-010) vulnerability in Windows SMBv1. "
            "Self-propagating — spreads across networks automatically without "
            "user interaction. Initial entry often via phishing email."
        ),
        "behavior": (
            "Encrypts files with AES-128-CBC + RSA-2048. Appends .WCRY extension. "
            "Creates ransom note demanding $300-$600 in Bitcoin. Includes kill "
            "switch domain check. Drops multiple components for persistence and spread."
        ),
        "persistence_methods": [
            "Windows service installation",
            "Registry run key modification",
            "Copies to Windows directory",
        ],
        "communication": (
            "Checks kill switch domain before encrypting. Uses Tor for payment "
            "page. Spreads via SMB port 445 using EternalBlue exploit."
        ),
        "detection_signatures": [
            "File hash indicators (multiple known variants)",
            "Network: SMB exploitation attempts on port 445",
            "File: .WCRY extension on encrypted files",
            "Behavior: mass file encryption + ransom note creation",
            "Kill switch domain resolution attempt",
        ],
        "removal_steps": [
            "Isolate infected system from network immediately",
            "Do NOT pay the ransom",
            "Boot from clean media",
            "Check if kill switch domain is active (may prevent encryption)",
            "Restore from clean backups",
            "Patch MS17-010 before reconnecting to network",
            "Disable SMBv1 (not needed on modern systems)",
        ],
        "prevention": [
            "Patch MS17-010 / disable SMBv1",
            "Keep all systems updated",
            "Block SMB port 445 at network boundary",
            "Maintain offline backups",
            "Network segmentation to limit spread",
        ],
    },
    "emotet": {
        "name": "Emotet",
        "aliases": ["Heodo", "Geodo"],
        "first_seen": "2014",
        "category": "trojan",
        "infection_vector": (
            "Primarily via phishing emails with malicious Word documents containing "
            "macros. Also spreads via network shares and brute-forcing credentials. "
            "Often hijacks existing email threads for credibility."
        ),
        "behavior": (
            "Modular trojan that acts as a malware delivery platform. Downloads "
            "additional payloads (TrickBot, Ryuk ransomware, QakBot). Steals "
            "email contacts and content for further phishing campaigns."
        ),
        "persistence_methods": [
            "Windows registry autorun keys",
            "Windows services",
            "Scheduled tasks",
            "DLL side-loading",
        ],
        "communication": (
            "HTTPS-based C2 communication. Uses multiple fallback C2 servers. "
            "Encrypted traffic to blend with normal HTTPS. Updates C2 list dynamically."
        ),
        "detection_signatures": [
            "Macro-enabled documents with obfuscated PowerShell",
            "Network: HTTPS connections to known Emotet C2 IPs",
            "Registry: new autorun entries in known Emotet paths",
            "Behavior: email harvesting + mass sending",
            "Process: PowerShell with encoded commands spawned by Office",
        ],
        "removal_steps": [
            "Isolate infected system from network",
            "Kill malicious processes",
            "Remove persistence mechanisms (registry, services, tasks)",
            "Reset all passwords — Emotet harvests credentials",
            "Scan all systems on network for spread",
            "Restore from clean backup if extensively compromised",
        ],
        "prevention": [
            "Disable Office macros (or require signed macros)",
            "Email filtering for macro-enabled attachments",
            "Security awareness training on phishing",
            "Network segmentation",
            "Keep antivirus updated",
        ],
    },
    "mirai": {
        "name": "Mirai",
        "aliases": ["Mirai Botnet"],
        "first_seen": "2016-08",
        "category": "botnet",
        "infection_vector": (
            "Scans for IoT devices and systems with default credentials. Uses "
            "a table of 62 common factory default username/password combinations "
            "to brute-force telnet and SSH access."
        ),
        "behavior": (
            "Enrolls compromised devices into DDoS botnet. Performed record-breaking "
            "DDoS attacks (Dyn DNS, 1.2+ Tbps). Kills other malware processes to "
            "claim exclusive access to the device."
        ),
        "persistence_methods": [
            "Memory-resident only (cleared by reboot)",
            "Re-infection via continuous scanning",
            "No disk persistence on most IoT targets",
        ],
        "communication": (
            "Connects to hardcoded C2 servers over TCP. Receives DDoS attack "
            "commands (UDP flood, TCP SYN, HTTP GET). Reports newly discovered "
            "vulnerable devices to C2 for enrollment."
        ),
        "detection_signatures": [
            "Telnet/SSH brute force with default credentials",
            "Network: scanning port 23/2323 (telnet) from internal devices",
            "Binary: specific string patterns in Mirai variants",
            "Behavior: device suddenly generating large outbound traffic",
        ],
        "removal_steps": [
            "Reboot device (clears memory-resident malware)",
            "Change default credentials immediately after reboot",
            "Update firmware to latest version",
            "Block telnet access (use SSH with keys instead)",
            "Segment IoT devices on separate VLAN",
        ],
        "prevention": [
            "Change all default passwords on IoT devices",
            "Disable telnet, use SSH with key authentication",
            "Keep IoT firmware updated",
            "Segment IoT devices on separate network",
            "Block outbound connections from IoT to internet",
        ],
    },
    "lockbit": {
        "name": "LockBit",
        "aliases": ["LockBit 2.0", "LockBit 3.0", "LockBit Black"],
        "first_seen": "2019-09",
        "category": "ransomware",
        "infection_vector": (
            "RDP brute force, phishing emails, exploitation of public-facing "
            "applications, and purchased initial access from other threat actors. "
            "Operates as Ransomware-as-a-Service (RaaS) with affiliate model."
        ),
        "behavior": (
            "Fast encryption using AES + RSA. Automatically spreads via Group "
            "Policy and PsExec. Exfiltrates data before encryption (double "
            "extortion). Deletes shadow copies and disables recovery options. "
            "Prints ransom notes on all network printers."
        ),
        "persistence_methods": [
            "Windows services",
            "Group Policy Objects for domain-wide deployment",
            "Scheduled tasks",
            "Registry modifications",
        ],
        "communication": (
            "Tor-based leak site for double extortion. C2 via HTTPS. Uses "
            "Cobalt Strike or similar frameworks for post-exploitation. "
            "Affiliate dashboard for managing attacks."
        ),
        "detection_signatures": [
            "Rapid file encryption with .lockbit extension",
            "Network: lateral movement via SMB + PsExec",
            "Shadow copy deletion (vssadmin, wmic)",
            "Group Policy modification for deployment",
            "Ransom notes: Restore-My-Files.txt",
        ],
        "removal_steps": [
            "Isolate affected systems immediately",
            "Do NOT pay the ransom",
            "Preserve forensic evidence",
            "Identify and close initial access vector",
            "Restore from offline backups",
            "Reset all domain passwords",
            "Rebuild compromised systems from clean images",
        ],
        "prevention": [
            "Secure RDP (MFA, VPN-only access, disable if unused)",
            "Patch public-facing applications promptly",
            "Offline, immutable backups (3-2-1 rule)",
            "Network segmentation and least-privilege access",
            "EDR solution with behavioral detection",
        ],
    },
    "pegasus": {
        "name": "Pegasus",
        "aliases": ["NSO Group Pegasus"],
        "first_seen": "2016",
        "category": "spyware",
        "infection_vector": (
            "Zero-click exploits targeting iOS and Android. No user interaction "
            "required. Delivered via iMessage, WhatsApp, or SMS. Exploits "
            "zero-day vulnerabilities in the OS or messaging apps."
        ),
        "behavior": (
            "Complete device surveillance: reads messages, emails, call logs. "
            "Activates camera and microphone. Tracks GPS location. Extracts "
            "passwords and encryption keys. Can access encrypted messaging apps."
        ),
        "persistence_methods": [
            "Kernel-level implant (survives app restarts)",
            "Some variants: memory-only (cleared by reboot)",
            "Re-infection capability via C2",
        ],
        "communication": (
            "Encrypted HTTPS to infrastructure rotated frequently. Uses "
            "multiple layers of proxy servers to hide C2. Data exfiltration "
            "over Wi-Fi when available to avoid cellular data charges."
        ),
        "detection_signatures": [
            "Unusual process activity on mobile devices",
            "Network: connections to known NSO infrastructure",
            "iMessage exploit: specific crafted message patterns",
            "Behavioral: unexpected microphone/camera activation",
            "MVT (Mobile Verification Toolkit) indicators",
        ],
        "removal_steps": [
            "Factory reset device (may not remove kernel implants)",
            "Use MVT (Mobile Verification Toolkit) for detection",
            "Replace device if high-value target",
            "Update OS to latest version immediately",
            "Report to security researchers/authorities",
        ],
        "prevention": [
            "Keep mobile OS updated (patches zero-days)",
            "Enable Lockdown Mode (iOS) for high-risk users",
            "Use separate devices for sensitive communications",
            "Reboot phone daily (clears memory-only implants)",
            "Monitor with MVT periodically",
        ],
    },
}


# ---------------------------------------------------------------------------
# ThreatIntelligence class
# ---------------------------------------------------------------------------
class ThreatIntelligence:
    """White-hat threat intelligence engine for Sentinel.

    Studies attack patterns, analyzes logs, builds defense profiles, and
    generates detection rules. All content is for DEFENSE ONLY — never
    generates exploit code or offensive payloads.
    """

    def __init__(self, grimoire: Any | None = None) -> None:
        """Initialize ThreatIntelligence.

        Args:
            grimoire: Optional Grimoire instance for storing threat knowledge.
        """
        self._grimoire = grimoire

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_attack_pattern(self, pattern_name: str) -> dict[str, Any]:
        """Study a known attack pattern for defensive understanding.

        Args:
            pattern_name: Name of the attack pattern (e.g. 'sql_injection').

        Returns:
            Comprehensive defensive reference for the pattern.
        """
        key = pattern_name.lower().strip()
        pattern = _ATTACK_PATTERNS.get(key)
        if pattern is None:
            available = sorted(_ATTACK_PATTERNS.keys())
            return {
                "error": f"Unknown attack pattern: {pattern_name}",
                "available_patterns": available,
            }
        return dict(pattern)

    def analyze_log_pattern(
        self, log_text: str, log_type: str = "auto",
    ) -> dict[str, Any]:
        """Analyze log entries for signs of attack or suspicious activity.

        Args:
            log_text: Raw log text to analyze.
            log_type: Log format hint ('syslog', 'auth', 'nginx', 'apache',
                      'fail2ban', 'journalctl', 'suricata', or 'auto').

        Returns:
            Analysis result with threat_detected, type, severity, etc.
        """
        if not log_text or not log_text.strip():
            return {
                "threat_detected": False,
                "threat_type": None,
                "severity": 0,
                "source_ips": [],
                "timestamps": [],
                "recommendation": "No log data provided.",
                "false_positive_likelihood": "n/a",
            }

        detected_type = log_type if log_type != "auto" else self._detect_log_type(log_text)
        threats: list[dict[str, Any]] = []

        # Run all detectors
        threats.extend(self._detect_brute_force(log_text))
        threats.extend(self._detect_port_scan(log_text))
        threats.extend(self._detect_web_attacks(log_text))
        threats.extend(self._detect_privilege_escalation(log_text))
        threats.extend(self._detect_data_exfiltration(log_text))

        if not threats:
            return {
                "threat_detected": False,
                "threat_type": None,
                "severity": 0,
                "source_ips": self._extract_ips(log_text),
                "timestamps": self._extract_timestamps(log_text),
                "recommendation": "No threats detected in log entries.",
                "false_positive_likelihood": "n/a",
                "log_type_detected": detected_type,
            }

        # Take the highest-severity threat
        threats.sort(key=lambda t: t["severity"], reverse=True)
        top = threats[0]

        all_ips: list[str] = []
        for t in threats:
            all_ips.extend(t.get("source_ips", []))
        unique_ips = sorted(set(all_ips))

        return {
            "threat_detected": True,
            "threat_type": top["threat_type"],
            "severity": top["severity"],
            "source_ips": unique_ips,
            "timestamps": self._extract_timestamps(log_text),
            "recommendation": top["recommendation"],
            "false_positive_likelihood": top.get("false_positive_likelihood", "medium"),
            "log_type_detected": detected_type,
            "all_threats": [
                {"type": t["threat_type"], "severity": t["severity"]}
                for t in threats
            ],
        }

    def build_defense_profile(
        self, threat_list: list[str],
    ) -> dict[str, Any]:
        """Build a complete defense profile for a list of threats.

        Args:
            threat_list: List of threat/attack pattern names.

        Returns:
            Layered defense plan with network, application, host, and
            monitoring layers.
        """
        if not threat_list:
            return {"error": "No threats provided. Pass a list of threat names."}

        network_layer: list[dict[str, str]] = []
        application_layer: list[dict[str, str]] = []
        host_layer: list[dict[str, str]] = []
        monitoring_layer: list[dict[str, str]] = []

        analyzed: list[dict[str, Any]] = []
        unknown: list[str] = []

        for threat_name in threat_list:
            pattern = _ATTACK_PATTERNS.get(threat_name.lower().strip())
            if pattern is None:
                unknown.append(threat_name)
                continue

            relevance = pattern.get("shadow_relevance", {})
            relevance_level = relevance.get("level", "medium") if isinstance(relevance, dict) else "medium"

            entry = {
                "threat": pattern["name"],
                "shadow_relevance": relevance_level,
            }
            analyzed.append(entry)

            category = pattern.get("category", "")

            # Map defenses to layers
            for defense in pattern.get("defense_strategies", []):
                if any(kw in defense.lower() for kw in ["firewall", "rate-limit", "block", "iptables", "port"]):
                    network_layer.append({"threat": pattern["name"], "rule": defense})
                elif any(kw in defense.lower() for kw in ["input", "validation", "parameterized", "encoding", "sanitiz", "waf"]):
                    application_layer.append({"threat": pattern["name"], "rule": defense})
                elif any(kw in defense.lower() for kw in ["patch", "update", "backup", "permission", "whitelist", "disable", "key-based"]):
                    host_layer.append({"threat": pattern["name"], "rule": defense})

            for tool in pattern.get("tools_for_detection", []):
                monitoring_layer.append({"threat": pattern["name"], "tool": tool})

        # Sort by shadow relevance
        relevance_order = {"high": 0, "medium": 1, "low": 2}
        analyzed.sort(key=lambda x: relevance_order.get(x["shadow_relevance"], 1))

        result: dict[str, Any] = {
            "threats_analyzed": analyzed,
            "network_layer": network_layer,
            "application_layer": application_layer,
            "host_layer": host_layer,
            "monitoring_layer": monitoring_layer,
            "priority_order": [a["threat"] for a in analyzed],
        }
        if unknown:
            result["unknown_threats"] = unknown
        return result

    def study_malware_family(self, family_name: str) -> dict[str, Any]:
        """Study a known malware family for defensive understanding.

        NEVER includes executable code, shellcode, or exploit payloads.
        Purely educational/defensive documentation.

        Args:
            family_name: Name of the malware family (e.g. 'wannacry').

        Returns:
            Defensive reference for the malware family.
        """
        key = family_name.lower().strip()
        family = _MALWARE_FAMILIES.get(key)
        if family is None:
            available = sorted(_MALWARE_FAMILIES.keys())
            return {
                "error": f"Unknown malware family: {family_name}",
                "available_families": available,
            }
        return dict(family)

    def generate_detection_rule(
        self, threat_type: str, rule_format: str = "suricata",
    ) -> dict[str, Any]:
        """Generate a detection rule for a specific threat.

        Rules are for DETECTION only, never exploitation.

        Args:
            threat_type: The threat to detect (e.g. 'brute_force').
            rule_format: Rule format ('suricata', 'snort', 'yara', 'sigma',
                         'fail2ban').

        Returns:
            Detection rule with explanation and tuning notes.
        """
        supported_formats = {"suricata", "snort", "yara", "sigma", "fail2ban"}
        fmt = rule_format.lower().strip()
        if fmt not in supported_formats:
            return {
                "error": f"Unsupported format: {rule_format}",
                "supported_formats": sorted(supported_formats),
            }

        threat_key = threat_type.lower().strip()
        rules = _DETECTION_RULES.get(threat_key, {})
        rule_data = rules.get(fmt)

        if rule_data is None:
            # Try to pull example_signature from attack pattern
            pattern = _ATTACK_PATTERNS.get(threat_key)
            if pattern and fmt == "suricata":
                return {
                    "rule_text": pattern.get("example_signature", ""),
                    "explanation": f"Detection rule for {pattern['name']} from attack pattern database.",
                    "false_positive_risk": "medium",
                    "tuning_notes": "Review thresholds and adjust for your network traffic volume.",
                }
            return {
                "error": f"No {fmt} rule available for threat: {threat_type}",
                "available_threats": sorted(_DETECTION_RULES.keys()),
            }

        return dict(rule_data)

    def assess_shadow_threat_surface(self) -> dict[str, Any]:
        """Analyze Shadow's specific threat surface.

        Considers Shadow's architecture: always-on Ubuntu server, Ollama API,
        Telegram bot, web scraping, API keys, SQLite databases, model files.

        Returns:
            Threat surface assessment with ranked risks and recommendations.
        """
        threats = [
            {
                "component": "Ollama API (localhost:11434)",
                "threat": "Unauthorized access to local AI models",
                "likelihood": "medium",
                "impact": "high",
                "detail": (
                    "If Ollama port is exposed beyond localhost, anyone can query "
                    "or manipulate the models. Could be used for model extraction "
                    "or to generate harmful content."
                ),
                "mitigation": "Bind Ollama to 127.0.0.1 only. Firewall rule to block external access to port 11434.",
            },
            {
                "component": "Telegram Bot",
                "threat": "Command injection via bot messages",
                "likelihood": "high",
                "impact": "high",
                "detail": (
                    "Telegram messages are an external input vector. Prompt injection "
                    "or command injection through bot messages could trigger unauthorized "
                    "actions through Shadow's tool system."
                ),
                "mitigation": "Cerberus injection detection on all Telegram input. Strict input validation.",
            },
            {
                "component": "API Keys (.env)",
                "threat": "Credential theft or exposure",
                "likelihood": "medium",
                "impact": "critical",
                "detail": (
                    "API keys for Anthropic, OpenAI, Telegram stored in config/.env. "
                    "Path traversal, file read exploits, or accidental git push could "
                    "expose these credentials."
                ),
                "mitigation": "Restrict .env file permissions (600). Ensure .gitignore covers .env. Rotate keys regularly.",
            },
            {
                "component": "SSH Access",
                "threat": "Brute force authentication attack",
                "likelihood": "high",
                "impact": "critical",
                "detail": (
                    "Always-on server with SSH is a constant brute force target. "
                    "Successful compromise gives full system access."
                ),
                "mitigation": "Key-based SSH only (disable password auth). fail2ban with aggressive thresholds. Non-standard SSH port.",
            },
            {
                "component": "Web Scraping (Reaper/Playwright)",
                "threat": "SSRF and malicious content ingestion",
                "likelihood": "medium",
                "impact": "medium",
                "detail": (
                    "Reaper fetches URLs that may point to internal services or "
                    "serve adversarial content designed to poison Shadow's knowledge."
                ),
                "mitigation": "URL validation — block private IP ranges. Content sanitization before storage.",
            },
            {
                "component": "SQLite Databases",
                "threat": "Data corruption or SQL injection",
                "likelihood": "low",
                "impact": "high",
                "detail": (
                    "Grimoire's SQLite database stores Shadow's memory. Corruption "
                    "or injection could manipulate Shadow's knowledge base."
                ),
                "mitigation": "Parameterized queries (already implemented). Regular backups. WAL mode for crash safety.",
            },
            {
                "component": "Code Execution (Omen)",
                "threat": "Arbitrary code execution via user input",
                "likelihood": "medium",
                "impact": "critical",
                "detail": (
                    "Omen executes code for development tasks. If user input flows "
                    "into executed code without sanitization, arbitrary code execution "
                    "is possible."
                ),
                "mitigation": "Cerberus pre-tool hooks. Never shell=True. Sandbox execution environment.",
            },
            {
                "component": "Model Files (Ollama)",
                "threat": "Model tampering or replacement",
                "likelihood": "low",
                "impact": "high",
                "detail": (
                    "If an attacker gains file access, they could replace or modify "
                    "Ollama model files to change Shadow's behavior."
                ),
                "mitigation": "File integrity monitoring (AIDE) on model directory. Restricted file permissions.",
            },
            {
                "component": "Prompt Injection",
                "threat": "Safety bypass via crafted input",
                "likelihood": "high",
                "impact": "high",
                "detail": (
                    "Prompt injection is the #1 AI-specific threat. Crafted input "
                    "could bypass Cerberus safety checks and trigger unauthorized "
                    "actions through Shadow's tool system."
                ),
                "mitigation": "Multi-layer defense: Cerberus injection detector, input scoring, output validation, tool hooks.",
            },
        ]

        # Rank by combined score
        likelihood_score = {"high": 3, "medium": 2, "low": 1}
        impact_score = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        for t in threats:
            t["risk_score"] = (
                likelihood_score.get(t["likelihood"], 1)
                * impact_score.get(t["impact"], 1)
            )

        threats.sort(key=lambda t: t["risk_score"], reverse=True)

        highest_risks = [t for t in threats if t["risk_score"] >= 6]
        immediate_actions = []
        for t in highest_risks:
            immediate_actions.append(t["mitigation"])

        monitoring_priorities = [
            "SSH authentication logs (fail2ban)",
            "Outbound connection monitoring (unexpected destinations)",
            "CPU/memory usage trends (cryptominer detection)",
            "File integrity checks on critical configs and databases",
            "Telegram input analysis (injection detection scoring)",
            "Ollama API access logs (local binding verification)",
        ]

        return {
            "threats": threats,
            "highest_risks": [
                {"component": t["component"], "threat": t["threat"], "risk_score": t["risk_score"]}
                for t in highest_risks
            ],
            "recommended_immediate_actions": immediate_actions,
            "monitoring_priorities": monitoring_priorities,
        }

    def store_threat_knowledge(
        self, knowledge: dict[str, Any], source: str,
    ) -> int:
        """Store threat intelligence in Grimoire.

        Args:
            knowledge: Dict with threat intelligence data.
            source: Where the knowledge came from.

        Returns:
            Count of items stored (0 if duplicate or no Grimoire).
        """
        if self._grimoire is None:
            logger.warning("No Grimoire available — threat knowledge not stored.")
            return 0

        topic = knowledge.get("name", knowledge.get("topic", "unknown"))
        category = knowledge.get("category", "threat_intelligence")

        # Build content string from knowledge dict
        parts = [f"Threat Intelligence: {topic}"]
        for key in ("how_it_works", "behavior", "infection_vector"):
            if key in knowledge:
                parts.append(f"{key}: {knowledge[key]}")
        for key in ("defense_strategies", "prevention", "detection_signatures"):
            if key in knowledge and isinstance(knowledge[key], list):
                parts.append(f"{key}: {', '.join(str(v) for v in knowledge[key])}")

        content = "\n\n".join(parts)

        try:
            mem_id = self._grimoire.remember(
                content=content,
                source="research",
                source_module="sentinel",
                category="threat_intelligence",
                trust_level=0.7,
                confidence=0.8,
                tags=["threat_intelligence", "security", category, topic.lower()],
                metadata={"source": source, "topic": topic, "category": category},
                check_duplicates=True,
            )
            if mem_id:
                logger.info("Stored threat knowledge: %s (id=%s)", topic, mem_id)
                return 1
        except Exception as e:
            logger.error("Failed to store threat knowledge: %s", e)
        return 0

    # ------------------------------------------------------------------
    # Log analysis helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_log_type(log_text: str) -> str:
        """Auto-detect log format from content."""
        lower = log_text.lower()
        if "sshd" in lower or "pam_unix" in lower:
            return "auth"
        if "suricata" in lower or "alert" in lower and "sid:" in lower:
            return "suricata"
        if "fail2ban" in lower:
            return "fail2ban"
        if "nginx" in lower or "apache" in lower or "HTTP/" in log_text:
            return "nginx"
        if "systemd" in lower or "journalctl" in lower:
            return "journalctl"
        return "syslog"

    @staticmethod
    def _extract_ips(text: str) -> list[str]:
        """Extract IP addresses from text."""
        ip_pattern = re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        )
        return sorted(set(ip_pattern.findall(text)))

    @staticmethod
    def _extract_timestamps(text: str) -> list[str]:
        """Extract timestamp-like strings from text."""
        # Common syslog format: Jan  1 00:00:00
        ts_pattern = re.compile(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b"
        )
        matches = ts_pattern.findall(text)
        # ISO format
        iso_pattern = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
        matches.extend(iso_pattern.findall(text))
        return matches

    def _detect_brute_force(self, log_text: str) -> list[dict[str, Any]]:
        """Detect brute force patterns in log entries."""
        results: list[dict[str, Any]] = []
        lines = log_text.strip().split("\n")

        # Count failed auth attempts per IP
        failed_pattern = re.compile(
            r"(?:Failed password|authentication failure|"
            r"Invalid user|failed login|"
            r"FAILED LOGIN|Connection closed by .* \[preauth\])",
            re.IGNORECASE,
        )

        failed_ips: dict[str, int] = {}
        for line in lines:
            if failed_pattern.search(line):
                ips = self._extract_ips(line)
                for ip in ips:
                    failed_ips[ip] = failed_ips.get(ip, 0) + 1

        for ip, count in failed_ips.items():
            if count >= 3:
                severity = min(5, 2 + count // 3)
                results.append({
                    "threat_type": "brute_force",
                    "severity": severity,
                    "source_ips": [ip],
                    "failed_attempts": count,
                    "recommendation": (
                        f"Block IP {ip} — {count} failed auth attempts detected. "
                        f"Add to fail2ban or iptables blocklist."
                    ),
                    "false_positive_likelihood": "low" if count >= 5 else "medium",
                })

        return results

    def _detect_port_scan(self, log_text: str) -> list[dict[str, Any]]:
        """Detect port scanning patterns in log entries."""
        results: list[dict[str, Any]] = []
        lines = log_text.strip().split("\n")

        # Track unique ports per source IP
        port_pattern = re.compile(r"(?:DPT|dport|port)[=: ](\d+)", re.IGNORECASE)
        conn_pattern = re.compile(r"(?:SYN|connection attempt|CONNECT)", re.IGNORECASE)

        ip_ports: dict[str, set[str]] = {}
        for line in lines:
            if port_pattern.search(line) or conn_pattern.search(line):
                ips = self._extract_ips(line)
                ports = port_pattern.findall(line)
                for ip in ips:
                    if ip not in ip_ports:
                        ip_ports[ip] = set()
                    ip_ports[ip].update(ports)

        for ip, ports in ip_ports.items():
            if len(ports) >= 5:
                severity = min(5, 2 + len(ports) // 5)
                results.append({
                    "threat_type": "port_scan",
                    "severity": severity,
                    "source_ips": [ip],
                    "ports_targeted": sorted(ports, key=int),
                    "recommendation": (
                        f"Port scan detected from {ip} targeting {len(ports)} ports. "
                        f"Consider blocking source IP and reviewing exposed services."
                    ),
                    "false_positive_likelihood": "low" if len(ports) >= 10 else "medium",
                })

        return results

    def _detect_web_attacks(self, log_text: str) -> list[dict[str, Any]]:
        """Detect web attack patterns in log entries."""
        results: list[dict[str, Any]] = []

        sqli_pattern = re.compile(
            r"(?:UNION\s+SELECT|OR\s+1\s*=\s*1|DROP\s+TABLE|"
            r"--\s*$|;\s*DELETE|'\s*OR\s*')",
            re.IGNORECASE,
        )
        xss_pattern = re.compile(
            r"(?:<script|javascript:|onerror\s*=|onload\s*=|alert\s*\()",
            re.IGNORECASE,
        )
        traversal_pattern = re.compile(r"(?:\.\./|\.\.\\|%2e%2e%2f|%252e)", re.IGNORECASE)

        if sqli_pattern.search(log_text):
            results.append({
                "threat_type": "sql_injection",
                "severity": 4,
                "source_ips": self._extract_ips(log_text),
                "recommendation": (
                    "SQL injection attempt detected in logs. Review and block "
                    "source IPs. Verify parameterized queries in application."
                ),
                "false_positive_likelihood": "low",
            })

        if xss_pattern.search(log_text):
            results.append({
                "threat_type": "xss",
                "severity": 3,
                "source_ips": self._extract_ips(log_text),
                "recommendation": (
                    "XSS attempt detected in logs. Review input validation "
                    "and output encoding. Block source IPs if persistent."
                ),
                "false_positive_likelihood": "medium",
            })

        if traversal_pattern.search(log_text):
            results.append({
                "threat_type": "path_traversal",
                "severity": 4,
                "source_ips": self._extract_ips(log_text),
                "recommendation": (
                    "Path traversal attempt detected. Review file access "
                    "controls and canonicalize all file paths."
                ),
                "false_positive_likelihood": "low",
            })

        return results

    def _detect_privilege_escalation(self, log_text: str) -> list[dict[str, Any]]:
        """Detect privilege escalation attempts."""
        results: list[dict[str, Any]] = []

        sudo_fail = re.compile(
            r"(?:sudo.*(?:incorrect password|NOT in sudoers|"
            r"authentication failure)|"
            r"su.*(?:FAILED|authentication failure))",
            re.IGNORECASE,
        )

        if sudo_fail.search(log_text):
            results.append({
                "threat_type": "privilege_escalation",
                "severity": 4,
                "source_ips": self._extract_ips(log_text),
                "recommendation": (
                    "Privilege escalation attempt detected (sudo/su failures). "
                    "Review user access and investigate unauthorized access attempts."
                ),
                "false_positive_likelihood": "medium",
            })

        return results

    def _detect_data_exfiltration(self, log_text: str) -> list[dict[str, Any]]:
        """Detect potential data exfiltration patterns."""
        results: list[dict[str, Any]] = []

        exfil_pattern = re.compile(
            r"(?:large.*(?:transfer|upload|outbound)|"
            r"(?:scp|rsync|curl.*-T|wget.*--post).*(?:\d+[MG]B|large))",
            re.IGNORECASE,
        )

        if exfil_pattern.search(log_text):
            results.append({
                "threat_type": "data_exfiltration",
                "severity": 5,
                "source_ips": self._extract_ips(log_text),
                "recommendation": (
                    "Potential data exfiltration detected. Investigate large "
                    "outbound transfers and verify they are authorized."
                ),
                "false_positive_likelihood": "high",
            })

        return results


# ---------------------------------------------------------------------------
# Detection rule templates
# ---------------------------------------------------------------------------
_DETECTION_RULES: dict[str, dict[str, dict[str, str]]] = {
    "brute_force": {
        "suricata": {
            "rule_text": (
                'alert ssh any any -> $HOME_NET 22 (msg:"SSH brute force attempt"; '
                "flow:to_server,established; "
                "threshold:type both, track by_src, count 5, seconds 300; "
                'sid:1000100; rev:1;)'
            ),
            "explanation": (
                "Alerts when a single source IP makes 5+ SSH connection attempts "
                "within 5 minutes. Tracks by source IP to detect distributed "
                "attacks from single origins."
            ),
            "false_positive_risk": "low",
            "tuning_notes": (
                "Adjust count threshold for your environment. Legitimate admin "
                "may trigger with typos — consider whitelisting known admin IPs."
            ),
        },
        "snort": {
            "rule_text": (
                'alert tcp any any -> $HOME_NET 22 (msg:"SSH brute force"; '
                "flags:S; threshold:type both, track by_src, count 5, seconds 300; "
                'sid:1000100; rev:1;)'
            ),
            "explanation": "Snort equivalent of SSH brute force detection rule.",
            "false_positive_risk": "low",
            "tuning_notes": "Same tuning as Suricata variant — adjust count/time window.",
        },
        "fail2ban": {
            "rule_text": (
                "[sshd]\n"
                "enabled = true\n"
                "port = ssh\n"
                "filter = sshd\n"
                "logpath = /var/log/auth.log\n"
                "maxretry = 3\n"
                "findtime = 600\n"
                "bantime = 3600\n"
                "action = iptables-multiport[name=sshd, port=\"ssh\", protocol=tcp]"
            ),
            "explanation": (
                "fail2ban jail that monitors /var/log/auth.log for SSH failures. "
                "Bans source IP for 1 hour after 3 failed attempts within 10 minutes."
            ),
            "false_positive_risk": "low",
            "tuning_notes": (
                "Consider increasing bantime to 86400 (24h) for persistent attackers. "
                "Add ignoreip for trusted networks."
            ),
        },
        "sigma": {
            "rule_text": (
                "title: SSH Brute Force Detection\n"
                "status: experimental\n"
                "description: Detects multiple failed SSH login attempts\n"
                "logsource:\n"
                "    product: linux\n"
                "    service: auth\n"
                "detection:\n"
                "    selection:\n"
                "        - 'Failed password'\n"
                "        - 'authentication failure'\n"
                "    condition: selection | count() by src_ip > 5\n"
                "    timeframe: 5m\n"
                "level: medium"
            ),
            "explanation": "Sigma rule for SSH brute force — converts to various SIEM formats.",
            "false_positive_risk": "low",
            "tuning_notes": "Adjust count threshold and timeframe for your environment.",
        },
        "yara": {
            "rule_text": (
                "rule ssh_brute_force_log {\n"
                "    meta:\n"
                '        description = "Detects SSH brute force patterns in log files"\n'
                '        author = "Shadow Sentinel"\n'
                "    strings:\n"
                '        $fail1 = "Failed password" nocase\n'
                '        $fail2 = "authentication failure" nocase\n'
                '        $fail3 = "Invalid user" nocase\n'
                "    condition:\n"
                "        #fail1 > 5 or #fail2 > 5 or #fail3 > 5\n"
                "}"
            ),
            "explanation": "YARA rule to scan log files for brute force evidence.",
            "false_positive_risk": "medium",
            "tuning_notes": "YARA is primarily for file scanning — use fail2ban for real-time detection.",
        },
    },
    "port_scan": {
        "suricata": {
            "rule_text": (
                'alert tcp any any -> $HOME_NET any (msg:"Port scan detected"; '
                "flags:S; threshold:type both, track by_src, count 25, seconds 60; "
                'sid:1000101; rev:1;)'
            ),
            "explanation": (
                "Alerts when a single source sends SYN packets to 25+ different "
                "ports within 60 seconds, indicating reconnaissance scanning."
            ),
            "false_positive_risk": "medium",
            "tuning_notes": (
                "Load balancers and CDNs may trigger false positives. Whitelist "
                "known infrastructure IPs."
            ),
        },
        "fail2ban": {
            "rule_text": (
                "[portscan]\n"
                "enabled = true\n"
                "filter = portscan\n"
                "logpath = /var/log/syslog\n"
                "maxretry = 10\n"
                "findtime = 60\n"
                "bantime = 3600\n"
                "action = iptables-allports[name=portscan, protocol=all]"
            ),
            "explanation": (
                "fail2ban jail for port scan detection. Requires custom portscan "
                "filter definition matching firewall drop logs."
            ),
            "false_positive_risk": "medium",
            "tuning_notes": "Requires iptables LOG rules to generate entries in syslog.",
        },
    },
    "sql_injection": {
        "suricata": {
            "rule_text": (
                'alert http any any -> $HOME_NET any (msg:"SQL Injection attempt"; '
                'http.uri; pcre:"/(?:UNION\\s+SELECT|OR\\s+1\\s*=\\s*1|'
                "DROP\\s+TABLE|'\\s*OR\\s*')/i\"; "
                'sid:1000102; rev:1;)'
            ),
            "explanation": (
                "Detects common SQL injection patterns in HTTP URI including "
                "UNION SELECT, OR 1=1, DROP TABLE, and tautology attacks."
            ),
            "false_positive_risk": "low",
            "tuning_notes": (
                "May trigger on legitimate URLs containing SQL-like terms. "
                "Add exceptions for known safe URIs."
            ),
        },
    },
    "prompt_injection": {
        "suricata": {
            "rule_text": (
                'alert http any any -> $HOME_NET any (msg:"Prompt injection attempt"; '
                'http.request_body; content:"ignore previous instructions"; nocase; '
                'sid:1000103; rev:1;)'
            ),
            "explanation": (
                "Detects common prompt injection phrases in HTTP request bodies "
                "targeting AI/LLM endpoints."
            ),
            "false_positive_risk": "medium",
            "tuning_notes": (
                "This catches only the most obvious injection patterns. Use "
                "Cerberus injection_detector for comprehensive AI input analysis."
            ),
        },
    },
    "ransomware": {
        "suricata": {
            "rule_text": (
                'alert tcp $HOME_NET any -> $EXTERNAL_NET any (msg:"Possible '
                "ransomware C2 beacon\"; flow:established,to_server; "
                "threshold:type both, track by_src, count 50, seconds 10; "
                'sid:1000104; rev:1;)'
            ),
            "explanation": (
                "Detects high-frequency outbound connections that may indicate "
                "ransomware command-and-control communication."
            ),
            "false_positive_risk": "high",
            "tuning_notes": (
                "High false positive risk from legitimate services. Combine with "
                "file integrity monitoring (AIDE) for better detection."
            ),
        },
        "sigma": {
            "rule_text": (
                "title: Ransomware File Encryption Detection\n"
                "status: experimental\n"
                "description: Detects mass file modification indicative of ransomware\n"
                "logsource:\n"
                "    product: linux\n"
                "    service: auditd\n"
                "detection:\n"
                "    selection:\n"
                "        type: SYSCALL\n"
                "        syscall: rename\n"
                "    condition: selection | count() > 100\n"
                "    timeframe: 1m\n"
                "level: critical"
            ),
            "explanation": (
                "Sigma rule detecting mass file rename operations that may "
                "indicate ransomware encrypting files."
            ),
            "false_positive_risk": "medium",
            "tuning_notes": "Adjust count threshold. Large legitimate file operations may trigger.",
        },
    },
    "cryptominer": {
        "suricata": {
            "rule_text": (
                'alert tcp $HOME_NET any -> $EXTERNAL_NET any (msg:"Stratum '
                "mining protocol detected\"; flow:established,to_server; "
                'content:"mining.subscribe"; sid:1000105; rev:1;)'
            ),
            "explanation": (
                "Detects Stratum mining protocol handshake, used by most "
                "cryptocurrency miners to connect to mining pools."
            ),
            "false_positive_risk": "low",
            "tuning_notes": "Very specific signature — low false positive rate.",
        },
    },
}
