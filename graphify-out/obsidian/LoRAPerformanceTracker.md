---
source_file: "modules\shadow\lora_tracker.py"
type: "code"
community: "Confidence Calibration"
location: "L57"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# LoRAPerformanceTracker

## Connections
- [[.__init__()_70]] - `calls` [INFERRED]
- [[.__init__()_71]] - `method` [EXTRACTED]
- [[._check_needs_retrain()]] - `method` [EXTRACTED]
- [[._init_db()_6]] - `method` [EXTRACTED]
- [[.detect_overlap()]] - `method` [EXTRACTED]
- [[.get_adapter_profile()]] - `method` [EXTRACTED]
- [[.get_all_profiles()]] - `method` [EXTRACTED]
- [[.get_performance_trend()]] - `method` [EXTRACTED]
- [[.get_retrain_candidates()]] - `method` [EXTRACTED]
- [[.get_tracker_summary()]] - `method` [EXTRACTED]
- [[.recommend_adapter()]] - `method` [EXTRACTED]
- [[.record()_1]] - `method` [EXTRACTED]
- [[.test_db_created_on_init()_2]] - `calls` [INFERRED]
- [[A registered LoRA adapter with metadata.]] - `uses` [INFERRED]
- [[Adapter that was good but is getting worse needs retrain.]] - `uses` [INFERRED]
- [[Check if an adapter has positive performance for a task type.          If the tr]] - `uses` [INFERRED]
- [[Create a tracker with a temporary database.]] - `uses` [INFERRED]
- [[Determine which adapter to load for a given task.          Priority module-spec]] - `uses` [INFERRED]
- [[Direct module lookup for adapter.          Args             module_name Name o]] - `uses` [INFERRED]
- [[Filter adapters by domain.          Args             domain Domain to filter b]] - `uses` [INFERRED]
- [[Generate the commandconfig needed to load an adapter.          Args]] - `uses` [INFERRED]
- [[LoRA Manager — Domain-Specific Adapter Selection & Stacking ====================]] - `uses` [INFERRED]
- [[LoRAAdapter]] - `uses` [INFERRED]
- [[LoRAManager]] - `uses` [INFERRED]
- [[Manage domain-specific LoRA adapter selection and stacking.      Tracks which ad]] - `uses` [INFERRED]
- [[Mark an adapter as the currently active one.          Only one adapter can be ac]] - `uses` [INFERRED]
- [[Re-scan adapters directory for new adapter files.          Auto-registers any ne]] - `uses` [INFERRED]
- [[Register a new LoRA adapter.          Args             name Unique adapter nam]] - `uses` [INFERRED]
- [[Register pre-configured adapters if their paths exist.]] - `uses` [INFERRED]
- [[Return all registered adapters.]] - `uses` [INFERRED]
- [[Return the currently active adapter, if any.]] - `uses` [INFERRED]
- [[TestEdgeCases_12]] - `uses` [INFERRED]
- [[TestMaintenance]] - `uses` [INFERRED]
- [[TestOverlap]] - `uses` [INFERRED]
- [[TestProfiles]] - `uses` [INFERRED]
- [[TestRecommendations]] - `uses` [INFERRED]
- [[TestRecording_1]] - `uses` [INFERRED]
- [[TestReporting_1]] - `uses` [INFERRED]
- [[Tests for LoRA Performance Tracker.]] - `uses` [INFERRED]
- [[Track and analyze LoRA adapter performance across tasks.]] - `rationale_for` [EXTRACTED]
- [[Tracker pre-loaded with sample data across multiple adapters.]] - `uses` [INFERRED]
- [[lora_tracker.py]] - `contains` [EXTRACTED]
- [[tracker()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Confidence_Calibration