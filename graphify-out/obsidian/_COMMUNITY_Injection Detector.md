---
type: community
cohesion: 0.09
members: 37
---

# Injection Detector

**Cohesion:** 0.09 - loosely connected
**Members:** 37 nodes

## Members
- [[.analyze()]] - code - modules\cerberus\injection_detector.py
- [[.check_scope_creep()]] - code - modules\cerberus\injection_detector.py
- [[.test_action_thresholds()]] - code - tests\test_injection_detector.py
- [[.test_developer_mode()]] - code - tests\test_injection_detector.py
- [[.test_discord_source()]] - code - tests\test_injection_detector.py
- [[.test_do_not_follow_rules()]] - code - tests\test_injection_detector.py
- [[.test_emergency_pressure()]] - code - tests\test_injection_detector.py
- [[.test_escalation_detected()]] - code - tests\test_injection_detector.py
- [[.test_forget_your_rules()]] - code - tests\test_injection_detector.py
- [[.test_ignore_all_above()]] - code - tests\test_injection_detector.py
- [[.test_ignore_previous_instructions()]] - code - tests\test_injection_detector.py
- [[.test_no_creep_with_short_history()]] - code - tests\test_injection_detector.py
- [[.test_normal_question()]] - code - tests\test_injection_detector.py
- [[.test_normal_task()]] - code - tests\test_injection_detector.py
- [[.test_pretend_you_are()]] - code - tests\test_injection_detector.py
- [[.test_score_capped_at_one()]] - code - tests\test_injection_detector.py
- [[.test_secrecy_request()]] - code - tests\test_injection_detector.py
- [[.test_stable_history_no_creep()]] - code - tests\test_injection_detector.py
- [[.test_sudo_mode()]] - code - tests\test_injection_detector.py
- [[.test_system_prompt_override()]] - code - tests\test_injection_detector.py
- [[.test_technical_query()]] - code - tests\test_injection_detector.py
- [[.test_trusted_source_no_extra_risk()]] - code - tests\test_injection_detector.py
- [[.test_untrusted_plus_injection_stacks()]] - code - tests\test_injection_detector.py
- [[.test_untrusted_source_adds_risk()]] - code - tests\test_injection_detector.py
- [[.test_you_are_now_dan()]] - code - tests\test_injection_detector.py
- [[Analyze recent requests for escalation patterns.          Looks for three signal]] - rationale - modules\cerberus\injection_detector.py
- [[Multiple injection patterns should still cap at 1.0.]] - rationale - tests\test_injection_detector.py
- [[Run the full injection detection pipeline.          Args             input_text]] - rationale - modules\cerberus\injection_detector.py
- [[TestCleanInputs]] - code - tests\test_injection_detector.py
- [[TestInjectionPatterns]] - code - tests\test_injection_detector.py
- [[TestScopeCreep]] - code - tests\test_injection_detector.py
- [[TestScoreCapping]] - code - tests\test_injection_detector.py
- [[TestSocialEngineering]] - code - tests\test_injection_detector.py
- [[TestSourceRisk]] - code - tests\test_injection_detector.py
- [[Tests for Prompt Injection & Social Engineering Detector =======================]] - rationale - tests\test_injection_detector.py
- [[detector()_1]] - code - tests\test_injection_detector.py
- [[test_injection_detector.py]] - code - tests\test_injection_detector.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Injection_Detector
SORT file.name ASC
```

## Connections to other communities
- 11 edges to [[_COMMUNITY_Async Task Queue]]
- 10 edges to [[_COMMUNITY_Base Module & Apex API]]
- 1 edge to [[_COMMUNITY_Module Lifecycle]]
- 1 edge to [[_COMMUNITY_Adversarial Sparring]]
- 1 edge to [[_COMMUNITY_Module Registry & Tools]]

## Top bridge nodes
- [[.analyze()]] - degree 28, connects to 5 communities
- [[TestInjectionPatterns]] - degree 11, connects to 2 communities
- [[TestSourceRisk]] - degree 7, connects to 2 communities
- [[TestCleanInputs]] - degree 6, connects to 2 communities
- [[TestScopeCreep]] - degree 6, connects to 2 communities