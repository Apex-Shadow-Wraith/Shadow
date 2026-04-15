---
source_file: "tests\test_injection_detector.py"
type: "code"
community: "Injection Detector"
location: "L109"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Injection_Detector
---

# TestSourceRisk

## Connections
- [[.test_discord_source()]] - `method` [EXTRACTED]
- [[.test_trusted_source_no_extra_risk()]] - `method` [EXTRACTED]
- [[.test_untrusted_plus_injection_stacks()]] - `method` [EXTRACTED]
- [[.test_untrusted_source_adds_risk()]] - `method` [EXTRACTED]
- [[InjectionResult]] - `uses` [INFERRED]
- [[PromptInjectionDetector]] - `uses` [INFERRED]
- [[test_injection_detector.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Injection_Detector