---
source_file: "modules\apex\training_data_pipeline.py"
type: "code"
community: "Apex API Providers"
location: "L37"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Apex_API_Providers
---

# TrainingDataPipeline

## Connections
- [[.__init__()_5]] - `method` [EXTRACTED]
- [[._sanitize()]] - `method` [EXTRACTED]
- [[.capture()]] - `method` [EXTRACTED]
- [[.export_for_lora()]] - `method` [EXTRACTED]
- [[.get_stats()_1]] - `method` [EXTRACTED]
- [[.initialize()]] - `calls` [INFERRED]
- [[.save()]] - `method` [EXTRACTED]
- [[.test_creates_output_dir()_1]] - `calls` [INFERRED]
- [[.test_existing_dir_no_error()_1]] - `calls` [INFERRED]
- [[API fallback to ClaudeOpenAI when local models fail.      Apex tracks every c]] - `uses` [INFERRED]
- [[Apex]] - `uses` [INFERRED]
- [[Apex — API Fallback and Active Learning =======================================]] - `uses` [INFERRED]
- [[Attach a teaching signal to an existing escalation log entry.          Args]] - `uses` [INFERRED]
- [[Call the Anthropic Claude API with conversation history.          Sends the fu]] - `uses` [INFERRED]
- [[Call the OpenAI API with conversation history.          Sends the full convers]] - `uses` [INFERRED]
- [[Capture Apex escalation exchanges as LoRA-ready training data.      Each success]] - `rationale_for` [EXTRACTED]
- [[Clear the conversation history.          Call on session end or when the user]] - `uses` [INFERRED]
- [[Create a TrainingDataPipeline with a temp output directory.]] - `uses` [INFERRED]
- [[Create a sample training entry via capture().]] - `uses` [INFERRED]
- [[Create the escalation log table if it doesn't exist.]] - `uses` [INFERRED]
- [[Dispatch a task to the selected API provider.          Sends the full conversa]] - `uses` [INFERRED]
- [[EscalationLog]] - `uses` [INFERRED]
- [[Estimate cost in USD for an API call.          Args             api claude]] - `uses` [INFERRED]
- [[Execute an Apex tool.          Args             tool_name Which tool to inv]] - `uses` [INFERRED]
- [[Export all training data as merged LoRA-ready JSONL.          Args]] - `uses` [INFERRED]
- [[Generate a spending report.          Args             params No required pa]] - `uses` [INFERRED]
- [[Get escalation statistics for the given time window.          Args]] - `uses` [INFERRED]
- [[Get escalation statistics.          Args             params Optional 'days']] - `uses` [INFERRED]
- [[Get recent escalations that have teaching signals.          Args]] - `uses` [INFERRED]
- [[Get recent teaching signals for review.          Args             params Op]] - `uses` [INFERRED]
- [[Get task types that frequently escalate.          Args             params N]] - `uses` [INFERRED]
- [[Get task types that keep escalating — learning priorities.          Args]] - `uses` [INFERRED]
- [[Get training data pipeline statistics.          Args             params No]] - `uses` [INFERRED]
- [[Initialize Apex.          Args             config Module configuration from]] - `uses` [INFERRED]
- [[Initialize escalation log.          Args             db_path Path to the SQ]] - `uses` [INFERRED]
- [[Inject a Grimoire reference for teaching signal storage.          Called by th]] - `uses` [INFERRED]
- [[Load call log from disk.]] - `uses` [INFERRED]
- [[Log an API usage entry manually.          Args             params 'entry' d]] - `uses` [INFERRED]
- [[Log an escalation event.          Args             task_type Category of th]] - `uses` [INFERRED]
- [[Mark that a similar task was later handled locally.          This is the key m]] - `uses` [INFERRED]
- [[Persist call log to disk.]] - `uses` [INFERRED]
- [[Record an escalation and extractstore teaching signal.          This is the c]] - `uses` [INFERRED]
- [[Request a teaching explanation from the API.          Architecture 'Shadow se]] - `uses` [INFERRED]
- [[Return Apex's tool definitions.]] - `uses` [INFERRED]
- [[SQLite-backed log of every Apex escalation.      Tracks what was escalated, wh]] - `uses` [INFERRED]
- [[Search Grimoire for prior teaching signals matching this task.          Called]] - `uses` [INFERRED]
- [[Select the best available API.          Claude is default. OpenAI is fallback.]] - `uses` [INFERRED]
- [[Send a task to a frontier API.          Makes real API calls when keys are pre]] - `uses` [INFERRED]
- [[Shut down Apex. Persist call log and clear conversation history.]] - `uses` [INFERRED]
- [[Start Apex. Load API keys from environment and config.env.]] - `uses` [INFERRED]
- [[Store an Apex transaction record in Grimoire for audit trail.          Args]] - `uses` [INFERRED]
- [[TestCapture]] - `uses` [INFERRED]
- [[TestDailyRotation]] - `uses` [INFERRED]
- [[TestExportForLora]] - `uses` [INFERRED]
- [[TestInit_3]] - `uses` [INFERRED]
- [[TestSanitization]] - `uses` [INFERRED]
- [[TestSave]] - `uses` [INFERRED]
- [[TestStats_4]] - `uses` [INFERRED]
- [[Tests for Training Data Pipeline — LoRA-Ready Dataset from Apex Escalations ====]] - `uses` [INFERRED]
- [[Tool handler clear conversation history.          Args             params]] - `uses` [INFERRED]
- [[Track daily spending.]] - `uses` [INFERRED]
- [[Trim conversation history to max_turns (pairs of user+assistant).          Eac]] - `uses` [INFERRED]
- [[pipeline()]] - `calls` [INFERRED]
- [[training_data_pipeline.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Apex_API_Providers