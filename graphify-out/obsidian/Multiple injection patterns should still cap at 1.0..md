---
source_file: "tests\test_injection_detector.py"
type: "rationale"
community: "Injection Detector"
location: "L165"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Injection_Detector
---

# Multiple injection patterns should still cap at 1.0.

## Connections
- [[.test_score_capped_at_one()]] - `rationale_for` [EXTRACTED]
- [[InjectionResult]] - `uses` [INFERRED]
- [[PromptInjectionDetector]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Injection_Detector