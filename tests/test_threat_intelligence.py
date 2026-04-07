"""Tests for Sentinel Threat Intelligence module."""

from __future__ import annotations

import pytest

from modules.sentinel.threat_intelligence import ThreatIntelligence


@pytest.fixture
def ti() -> ThreatIntelligence:
    """ThreatIntelligence instance without Grimoire."""
    return ThreatIntelligence()


class TestAnalyzeAttackPattern:
    """Tests for analyze_attack_pattern."""

    def test_sql_injection_complete(self, ti: ThreatIntelligence) -> None:
        """SQL injection analysis returns all required fields."""
        result = ti.analyze_attack_pattern("sql_injection")
        assert "error" not in result
        assert result["name"] == "SQL Injection"
        assert result["category"] == "application"
        assert result["how_it_works"]
        assert len(result["indicators"]) > 0
        assert len(result["detection_methods"]) > 0
        assert len(result["defense_strategies"]) > 0
        assert len(result["tools_for_detection"]) > 0
        assert result["example_signature"]

    def test_brute_force_complete(self, ti: ThreatIntelligence) -> None:
        """Brute force analysis returns all required fields."""
        result = ti.analyze_attack_pattern("brute_force")
        assert "error" not in result
        assert result["name"] == "Brute Force Authentication Attack"
        assert result["category"] == "auth"
        assert result["how_it_works"]
        assert len(result["indicators"]) > 0
        assert len(result["defense_strategies"]) > 0

    def test_shadow_relevance_included(self, ti: ThreatIntelligence) -> None:
        """Attack patterns include shadow_relevance assessment."""
        result = ti.analyze_attack_pattern("prompt_injection")
        assert "shadow_relevance" in result
        relevance = result["shadow_relevance"]
        assert relevance["level"] in ("high", "medium", "low")
        assert relevance["reason"]

    def test_unknown_pattern_returns_error(self, ti: ThreatIntelligence) -> None:
        """Unknown patterns return error with available list."""
        result = ti.analyze_attack_pattern("nonexistent_attack")
        assert "error" in result
        assert "available_patterns" in result
        assert len(result["available_patterns"]) > 0


class TestAnalyzeLogPattern:
    """Tests for analyze_log_pattern."""

    def test_detects_brute_force(self, ti: ThreatIntelligence) -> None:
        """Detects brute force from auth log entries."""
        log_text = (
            "Jan  5 12:01:01 server sshd[1234]: Failed password for root from 192.168.1.100 port 22\n"
            "Jan  5 12:01:02 server sshd[1235]: Failed password for root from 192.168.1.100 port 22\n"
            "Jan  5 12:01:03 server sshd[1236]: Failed password for root from 192.168.1.100 port 22\n"
            "Jan  5 12:01:04 server sshd[1237]: Failed password for root from 192.168.1.100 port 22\n"
            "Jan  5 12:01:05 server sshd[1238]: Failed password for root from 192.168.1.100 port 22\n"
        )
        result = ti.analyze_log_pattern(log_text)
        assert result["threat_detected"] is True
        assert result["threat_type"] == "brute_force"
        assert result["severity"] >= 3
        assert "192.168.1.100" in result["source_ips"]

    def test_detects_port_scanning(self, ti: ThreatIntelligence) -> None:
        """Detects port scanning from firewall log entries."""
        log_text = "\n".join(
            f"Jan  5 12:00:{i:02d} server kernel: DROP IN=eth0 SRC=10.0.0.5 "
            f"DST=192.168.1.1 DPT={port} SYN"
            for i, port in enumerate([22, 80, 443, 3306, 5432, 8080, 8443, 9090, 11434, 3389])
        )
        result = ti.analyze_log_pattern(log_text)
        assert result["threat_detected"] is True
        assert result["threat_type"] == "port_scan"
        assert "10.0.0.5" in result["source_ips"]

    def test_clean_logs_return_false(self, ti: ThreatIntelligence) -> None:
        """Clean log entries return no threats."""
        log_text = (
            "Jan  5 12:00:00 server sshd[1234]: Accepted publickey for admin from 192.168.1.10 port 22\n"
            "Jan  5 12:01:00 server sshd[1235]: Accepted publickey for admin from 192.168.1.10 port 22\n"
        )
        result = ti.analyze_log_pattern(log_text)
        assert result["threat_detected"] is False
        assert result["severity"] == 0

    def test_empty_log_returns_false(self, ti: ThreatIntelligence) -> None:
        """Empty log text returns no threats."""
        result = ti.analyze_log_pattern("")
        assert result["threat_detected"] is False


class TestBuildDefenseProfile:
    """Tests for build_defense_profile."""

    def test_generates_firewall_rules(self, ti: ThreatIntelligence) -> None:
        """Defense profile generates network layer rules."""
        result = ti.build_defense_profile(["brute_force", "port_scanning"])
        assert "error" not in result
        assert len(result["network_layer"]) > 0
        assert len(result["monitoring_layer"]) > 0

    def test_prioritizes_by_shadow_relevance(self, ti: ThreatIntelligence) -> None:
        """Threats are prioritized by shadow_relevance."""
        result = ti.build_defense_profile(["xss", "prompt_injection", "brute_force"])
        assert "error" not in result
        priorities = result["priority_order"]
        # prompt_injection and brute_force are "high", xss is "low"
        # High-relevance threats should come before low
        xss_idx = priorities.index("Cross-Site Scripting (XSS)")
        # At least one high-relevance threat should be before XSS
        assert xss_idx > 0

    def test_empty_list_returns_error(self, ti: ThreatIntelligence) -> None:
        """Empty threat list returns error."""
        result = ti.build_defense_profile([])
        assert "error" in result


class TestStudyMalwareFamily:
    """Tests for study_malware_family."""

    def test_returns_defensive_info(self, ti: ThreatIntelligence) -> None:
        """Malware study returns defensive info without executable code."""
        result = ti.study_malware_family("wannacry")
        assert "error" not in result
        assert result["name"] == "WannaCry"
        assert result["category"] == "ransomware"
        assert result["infection_vector"]
        assert result["behavior"]
        assert len(result["removal_steps"]) > 0
        assert len(result["prevention"]) > 0
        # Verify no executable code patterns
        all_text = str(result)
        assert "\\x" not in all_text or "\\x3C" in all_text  # Allow doc references
        assert "shellcode" not in all_text.lower()

    def test_includes_detection_and_prevention(self, ti: ThreatIntelligence) -> None:
        """Malware study includes detection signatures and prevention."""
        result = ti.study_malware_family("emotet")
        assert "error" not in result
        assert len(result["detection_signatures"]) > 0
        assert len(result["prevention"]) > 0
        assert len(result["persistence_methods"]) > 0

    def test_unknown_family_returns_error(self, ti: ThreatIntelligence) -> None:
        """Unknown malware family returns error with available list."""
        result = ti.study_malware_family("nonexistent_malware")
        assert "error" in result
        assert "available_families" in result


class TestGenerateDetectionRule:
    """Tests for generate_detection_rule."""

    def test_suricata_rule_syntax(self, ti: ThreatIntelligence) -> None:
        """Suricata rule has valid syntax structure."""
        result = ti.generate_detection_rule("brute_force", "suricata")
        assert "error" not in result
        rule = result["rule_text"]
        assert "alert" in rule
        assert "sid:" in rule
        assert "msg:" in rule
        assert result["explanation"]
        assert result["false_positive_risk"]

    def test_fail2ban_jail_config(self, ti: ThreatIntelligence) -> None:
        """fail2ban rule produces valid jail config."""
        result = ti.generate_detection_rule("brute_force", "fail2ban")
        assert "error" not in result
        rule = result["rule_text"]
        assert "[sshd]" in rule
        assert "enabled" in rule
        assert "maxretry" in rule
        assert "bantime" in rule

    def test_unsupported_format_returns_error(self, ti: ThreatIntelligence) -> None:
        """Unsupported rule format returns error."""
        result = ti.generate_detection_rule("brute_force", "invalid_format")
        assert "error" in result


class TestAssessShadowThreatSurface:
    """Tests for assess_shadow_threat_surface."""

    def test_identifies_key_risks(self, ti: ThreatIntelligence) -> None:
        """Assessment identifies Ollama, Telegram, and API keys as risks."""
        result = ti.assess_shadow_threat_surface()
        components = [t["component"] for t in result["threats"]]
        component_text = " ".join(components).lower()
        assert "ollama" in component_text
        assert "telegram" in component_text
        assert "api" in component_text or ".env" in component_text

    def test_returns_ranked_threats(self, ti: ThreatIntelligence) -> None:
        """Threats are ranked by risk score."""
        result = ti.assess_shadow_threat_surface()
        scores = [t["risk_score"] for t in result["threats"]]
        assert scores == sorted(scores, reverse=True)

    def test_has_immediate_actions(self, ti: ThreatIntelligence) -> None:
        """Assessment includes recommended immediate actions."""
        result = ti.assess_shadow_threat_surface()
        assert len(result["recommended_immediate_actions"]) > 0
        assert len(result["monitoring_priorities"]) > 0


class TestStoreThreatKnowledge:
    """Tests for store_threat_knowledge."""

    def test_no_grimoire_returns_zero(self, ti: ThreatIntelligence) -> None:
        """Without Grimoire, store returns 0."""
        result = ti.store_threat_knowledge(
            {"name": "test", "category": "test"},
            source="test",
        )
        assert result == 0

    def test_deduplicates_in_grimoire(self) -> None:
        """Grimoire deduplication prevents storing same knowledge twice."""

        class MockGrimoire:
            """Mock Grimoire that tracks calls and deduplicates."""

            def __init__(self) -> None:
                self.stored: list[str] = []

            def remember(self, content: str, **kwargs: object) -> str | None:
                if kwargs.get("check_duplicates") and content in self.stored:
                    return None
                self.stored.append(content)
                return "mock-id-123"

        grimoire = MockGrimoire()
        ti_with_grimoire = ThreatIntelligence(grimoire=grimoire)

        knowledge = {"name": "SQL Injection", "category": "application",
                      "how_it_works": "Injects SQL into queries"}

        count1 = ti_with_grimoire.store_threat_knowledge(knowledge, "test")
        assert count1 == 1

        count2 = ti_with_grimoire.store_threat_knowledge(knowledge, "test")
        assert count2 == 0  # Duplicate
