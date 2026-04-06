"""
Shadow's First Memories — Test & Seed Script
==============================================
This script does two things:

1. TESTS that Grimoire and Reaper are working correctly
2. SEEDS Shadow's memory with real knowledge from Sessions 1-6

Everything stored here becomes Shadow's first real memories.
These are the facts, decisions, and architectural choices that define
who Shadow is, what it's being built to do, and what values it holds.

Run this AFTER:
    - Ollama is running (ollama serve)
    - nomic-embed-text is pulled (ollama pull nomic-embed-text)
    - phi4-mini is pulled (ollama pull phi4-mini)
    - Virtual environment is activated (shadow_env/Scripts/activate)

Usage:
    cd C:\\Shadow
    python tests/test_shadow_memory.py
    
Author: Patrick (with Claude Opus 4.6)
Session: 7 — First Code
"""

import sys
import json
import pytest
from pathlib import Path
from datetime import datetime

# Add the project root to Python's path so we can import our modules
# This is needed because we're running from the tests/ directory
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.grimoire.grimoire import (
    Grimoire,
    TRUST_USER_CORRECTION,
    TRUST_USER_STATED,
    TRUST_VERIFIED_RESEARCH,
    TRUST_CONVERSATION,
    TRUST_SINGLE_SOURCE,
    TRUST_MORPHEUS,
    SOURCE_CONVERSATION,
    SOURCE_USER_CORRECTION,
    SOURCE_USER_STATED,
    SOURCE_RESEARCH,
    SOURCE_SYSTEM,
)
from modules.reaper.reaper import Reaper, evaluate_source


@pytest.fixture
def grimoire(tmp_path):
    """Create a Grimoire instance with temporary storage for testing."""
    db_path = tmp_path / "test_memory.db"
    vector_path = tmp_path / "test_vectors"
    return Grimoire(db_path=str(db_path), vector_path=str(vector_path))


@pytest.fixture
def reaper(grimoire, tmp_path):
    """Create a Reaper instance with temporary storage for testing."""
    data_dir = tmp_path / "test_research"
    return Reaper(grimoire=grimoire, data_dir=str(data_dir))


def print_header(text):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def print_result(label, value):
    """Print a labeled result."""
    print(f"  {label}: {value}")


def test_grimoire_basics(grimoire):
    """Test core Grimoire functionality."""
    print_header("TEST 1: Grimoire — Basic Memory Operations")
    
    # ── Store a test memory ──
    print("\n  Storing test memory...")
    test_id = grimoire.remember(
        content="This is a test memory to verify Grimoire is working correctly.",
        source=SOURCE_SYSTEM,
        category="testing",
        trust_level=0.1,  # Low trust — it's just a test
        tags=["test", "setup-verification"]
    )
    print_result("  Memory stored", test_id[:12] + "...")
    
    # ── Recall by semantic search ──
    print("\n  Testing semantic search...")
    results = grimoire.recall("is the memory system working?", n_results=3)
    
    if results:
        print(f"  Found {len(results)} results:")
        for r in results:
            print(f"    [{r['relevance']:.3f}] {r['content'][:60]}...")
        print("  ✅ Semantic search working!")
    else:
        print("  ❌ No results found — check Ollama and nomic-embed-text")
        assert False, "Semantic search returned no results"
    
    # ── Test correction ──
    print("\n  Testing correction system...")
    corrected_id = grimoire.correct(
        memory_id=test_id,
        new_content="This test memory was corrected to verify the correction system works.",
        reason="Testing the correction pipeline"
    )
    print_result("  Correction applied", corrected_id[:12] + "...")
    
    # Verify the correction worked
    results = grimoire.recall("correction system test", n_results=1)
    if results and results[0]["trust_level"] == TRUST_USER_CORRECTION:
        print("  ✅ Corrections working! Trust level = 1.0")
    else:
        print("  ❌ Correction trust level issue")
        assert False, "Correction trust level not set to TRUST_USER_CORRECTION"

    # ── Test pointer index ──
    print("\n  Testing pointer index...")
    index = grimoire.get_pointer_index()
    print_result("  Total memories", index['total_memories'])
    print_result("  Categories", list(index['categories'].keys()))
    print("  ✅ Pointer index working!")


def test_reaper_source_eval():
    """Test Reaper's source evaluation hierarchy."""
    print_header("TEST 2: Reaper — Source Evaluation")
    
    test_cases = [
        ("https://docs.python.org/3/tutorial/", 1, 0.7, "official"),
        ("https://arxiv.org/abs/2301.00001", 1, 0.7, "official"),
        ("https://github.com/ollama/ollama", 1, 0.7, "official"),
        ("https://www.nasa.gov/artemis", 1, 0.7, "official"),
        ("https://arstechnica.com/article", 2, 0.5, "journalism"),
        ("https://www.nytimes.com/story", 2, 0.5, "journalism"),
        ("https://www.reddit.com/r/LocalLLaMA", 3, 0.3, "community"),
        ("https://stackoverflow.com/q/12345", 3, 0.3, "community"),
        ("https://randomseosite.com/top-10", 4, 0.1, "unverified"),
    ]
    
    all_passed = True
    for url, expected_tier, expected_trust, expected_type in test_cases:
        result = evaluate_source(url)
        passed = (
            result['tier'] == expected_tier and
            result['trust_score'] == expected_trust and
            result['source_type'] == expected_type
        )
        status = "✅" if passed else "❌"
        print(f"  {status} Tier {result['tier']} [{result['trust_score']}] "
              f"{result['source_type']:12s} — {result['domain']}")
        if not passed:
            all_passed = False

    assert all_passed, "Some source evaluations did not match expected values"
    print("\n  ✅ All source evaluations correct!")


def test_reaper_summarize(reaper):
    """Test Reaper's LLM summarization."""
    print_header("TEST 3: Reaper — LLM Summarization")
    
    test_text = (
        "Shadow is a personal AI agent project built by Patrick. "
        "It runs locally on custom hardware with dual RTX 5090 GPUs "
        "providing 64GB of VRAM. Shadow uses Ollama for model serving "
        "and has 13 modules including Grimoire for memory, Reaper for "
        "research, Sentinel for security, and Morpheus for creative "
        "discovery. The project prioritizes privacy, biblical values, "
        "and independence from cloud AI services."
    )
    
    try:
        summary = reaper.summarize(test_text)
        print(f"  Original: {len(test_text)} chars")
        print(f"  Summary:  {summary[:200]}")
        assert summary, "Summarization returned empty result"
        print("  ✅ Summarization working!")
    except Exception as e:
        pytest.skip(f"Summarization requires phi4-mini: {e}")


def seed_shadow_identity(grimoire):
    """
    Seed Shadow's core identity memories.
    These are the foundational facts about what Shadow IS.
    """
    print_header("SEEDING: Shadow's Core Identity")
    
    memories = [
        {
            "content": (
                "Shadow is a personal autonomous AI agent. One agent, one identity, "
                "13 modules. The modules are task-specific configurations with different "
                "system prompts and tools — they are all Shadow, not separate personalities. "
                "Shadow was designed to be honest, capable, and guided by biblical values."
            ),
            "category": "identity",
            "tags": ["core-identity", "shadow", "modules"],
        },
        {
            "content": (
                "Shadow's 13 modules: Shadow (router), Wraith (fast brain), "
                "Cerberus (safety/ethics), Apex (API fallback), Grimoire (memory), "
                "Sentinel (security), Harbinger (briefings), Reaper (research), "
                "Cipher (math/logic), Omen (code), Nova (documents/images), "
                "Void (24/7 monitoring), Morpheus (creative discovery)."
            ),
            "category": "identity",
            "tags": ["modules", "architecture"],
        },
        {
            "content": (
                "Shadow's creator is Patrick. He runs a landscaping business and uses "
                "LMN software (my.golmn.com) for scheduling, estimates, and crew management. "
                "He is learning Python to build Shadow. Communication style: direct and honest. "
                "Prefers bold recommendations over conservative defaults."
            ),
            "category": "creator",
            "tags": ["patrick", "creator", "landscaping", "lmn"],
        },
        {
            "content": (
                "Shadow's ethics are based on biblical values — integrity, stewardship, "
                "honesty, protecting the vulnerable, humility, responsibility. Ethics are "
                "a compass, not a checklist. Shadow reasons from principles, not rules. "
                "Every base model is abliterated with Heretic to strip manufacturer "
                "censorship before use. Shadow's values come from the creator, not "
                "from Meta, OpenAI, Google, or any manufacturer."
            ),
            "category": "ethics",
            "tags": ["values", "ethics", "abliteration", "biblical"],
        },
        {
            "content": (
                "Shadow's standing rules: (1) Honesty over comfort — never tell the creator "
                "what he wants to hear. (2) Say 'I don't know' when uncertain. (3) Push back "
                "on bad ideas with alternatives. (4) Log everything. (5) Never take external "
                "actions without approval. (6) Financial access only through prepaid virtual "
                "cards — never real bank accounts. (7) Never disable the safety layer. "
                "(8) Express confidence levels on all factual claims. (9) Cite sources."
            ),
            "category": "rules",
            "tags": ["standing-rules", "safety", "honesty", "anti-sycophancy"],
        },
    ]
    
    count = 0
    for mem in memories:
        grimoire.remember(
            content=mem["content"],
            source=SOURCE_USER_STATED,
            source_module="grimoire",
            category=mem["category"],
            trust_level=TRUST_USER_STATED,
            confidence=1.0,
            tags=mem["tags"]
        )
        count += 1
    
    print(f"  Stored {count} identity memories")
    return count


def seed_hardware_knowledge(grimoire):
    """Seed Shadow's knowledge about its own hardware."""
    print_header("SEEDING: Hardware Build")
    
    memories = [
        {
            "content": (
                "Shadow's target hardware: Dual ASUS TUF Gaming RTX 5090 GPUs (32GB each, "
                "64GB total VRAM), AMD Ryzen 9 7950X (16-core), 128GB DDR5-5600 RAM "
                "(Kingston FURY Beast, already owned), Samsung 990 Pro 2TB NVMe (primary, "
                "already owned), Samsung 990 Pro 4TB NVMe (secondary), Seagate Barracuda "
                "8TB HDD (backups), Corsair HX1500i/HX1600i PSU (Platinum), "
                "Lian Li O11 Dynamic EVO XL case, Noctua NH-D15 cooler, "
                "CyberPower CP1500PFCLCD UPS."
            ),
            "category": "hardware",
            "tags": ["hardware-build", "gpu", "rtx-5090", "specs"],
        },
        {
            "content": (
                "Shadow's current development hardware (Windows PC): RTX 2080 Ti GPU, "
                "AMD Ryzen 7 2700X CPU, 32GB RAM. Used for coding, testing small models, "
                "and initial development. All code written here will migrate to the "
                "Shadow PC (Ubuntu) when the hardware build is complete."
            ),
            "category": "hardware",
            "tags": ["development-pc", "windows", "current-hardware"],
        },
        {
            "content": (
                "Hardware market context (April 2026): GDDR7 crisis ongoing, DDR5 prices "
                "3-4x since mid-2025, NAND rising 33-38% per quarter. Crisis may last "
                "until 2027-2028. Patrick already owns 128GB DDR5 (now worth $800+). "
                "Buy storage-dependent parts ASAP due to rising prices."
            ),
            "category": "hardware",
            "tags": ["market", "pricing", "memory-crisis", "urgency"],
        },
    ]
    
    count = 0
    for mem in memories:
        grimoire.remember(
            content=mem["content"],
            source=SOURCE_USER_STATED,
            source_module="grimoire",
            category=mem["category"],
            trust_level=TRUST_USER_STATED,
            confidence=1.0,
            tags=mem["tags"]
        )
        count += 1
    
    print(f"  Stored {count} hardware memories")
    return count


def seed_software_knowledge(grimoire):
    """Seed Shadow's knowledge about its software stack."""
    print_header("SEEDING: Software Stack & Models")
    
    memories = [
        {
            "content": (
                "Shadow's OS: Ubuntu 24.04 LTS with NVIDIA 570+ drivers and CUDA 12.8. "
                "AI runtime: Ollama 0.5.x with llama.cpp backend. NVIDIA CES 2026 "
                "optimizations already live: 35% faster in llama.cpp, 30% in Ollama. "
                "Multi-GPU: OLLAMA_GPU_SPLIT and CUDA_VISIBLE_DEVICES."
            ),
            "category": "software",
            "tags": ["os", "ubuntu", "ollama", "cuda", "drivers"],
        },
        {
            "content": (
                "Shadow's model strategy: Smart Brain = Llama 4 Scout Q4 or Qwen 3 32B, "
                "Fast Brain = Qwen 3.5 35B-A3B or GPT-OSS 20B, "
                "Math/Logic = DeepSeek R1 Distill 32B, Code = Qwen3-Coder 30B-A3B, "
                "Router = Phi-4-mini 3.8B or Qwen3 4B, "
                "Embeddings = nomic-embed-text, Fallback = Claude API (Opus). "
                "Only one or two models loaded in VRAM at a time — Ollama hot-swaps."
            ),
            "category": "models",
            "tags": ["models", "llama", "qwen", "deepseek", "routing"],
        },
        {
            "content": (
                "Model bias disclosure: Llama 4 (Meta/USA) = Western progressive alignment. "
                "Qwen 3/3.5 (Alibaba/China) = Chinese government censorship. "
                "GPT-OSS (OpenAI/USA) = Western alignment, violence/weapons restrictions. "
                "DeepSeek (China) = Lighter Chinese political censorship. "
                "Gemma 3 (Google/USA) = Heaviest safety alignment. "
                "Mistral (France) = Lightest Western alignment. "
                "ALL models abliterated with Heretic before use."
            ),
            "category": "models",
            "tags": ["bias", "censorship", "abliteration", "disclosure"],
        },
        {
            "content": (
                "Shadow's orchestration stack: LangGraph v1.1 (MIT licensed, model-agnostic) "
                "for multi-agent routing. MCP (Model Context Protocol) for tool connections "
                "from day one. A2A (Agent-to-Agent) protocol for future agent coordination. "
                "AG-UI protocol for agent-to-user interface (deferred)."
            ),
            "category": "software",
            "tags": ["langgraph", "mcp", "a2a", "orchestration"],
        },
        {
            "content": (
                "TurboQuant status (April 2, 2026): KV cache compression significant progress. "
                "Working llama.cpp implementation: CPU passes all 18 tests within 1% of paper. "
                "CUDA kernels written. Community found QJL hurts for KV cache — MSE-only better. "
                "4-bit confirmed as sweet spot. Open feature requests in vLLM, prototype in "
                "llama.cpp, pip-installable package exists. Google official Q2 2026. "
                "By Shadow's hardware build time, likely in Ollama. Monitor weekly."
            ),
            "category": "technology",
            "tags": ["turboquant", "kv-cache", "llama-cpp", "performance"],
        },
        {
            "content": (
                "Mythos/Capybara status (April 2, 2026): No change in release status. "
                "Still early access, no public date. Anthropic privately warning government "
                "officials about cyber risks. Analysts connecting to potential Anthropic IPO "
                "(~$26B annualized revenue target by end 2026). For Shadow: more expensive "
                "but more capable future API fallback for Apex module."
            ),
            "category": "technology",
            "tags": ["mythos", "capybara", "anthropic", "api-fallback"],
        },
    ]
    
    count = 0
    for mem in memories:
        grimoire.remember(
            content=mem["content"],
            source=SOURCE_USER_STATED,
            source_module="grimoire",
            category=mem["category"],
            trust_level=TRUST_USER_STATED,
            confidence=1.0,
            tags=mem["tags"]
        )
        count += 1
    
    print(f"  Stored {count} software/model memories")
    return count


def seed_architecture_decisions(grimoire):
    """Seed Shadow's knowledge about key architectural decisions."""
    print_header("SEEDING: Architecture Decisions")
    
    memories = [
        {
            "content": (
                "Grimoire memory architecture: Three layers — Working Memory (context window "
                "with 70%/85% thresholds), Active Memory (vector DB via ChromaDB for semantic "
                "search), Deep Memory (SQLite for structured archive). Nothing is ever discarded. "
                "Nightly backup to 8TB HDD. Memory survives model upgrades. ~50-100GB after year one."
            ),
            "category": "architecture",
            "tags": ["grimoire", "memory", "chromadb", "sqlite"],
        },
        {
            "content": (
                "Sentinel security architecture: Three layers — Detection (Suricata IDS, "
                "Zeek logging, AIDE file integrity, Netdata monitoring, rsyslog, HaveIBeenPwned), "
                "Analysis (Allama SOAR with Ollama AI agents, threat intelligence, temporal patterns), "
                "Response (three tiers: automated, semi-automated via Telegram, manual). "
                "HARD CONSTRAINT: Sentinel defends only, never retaliates or launches offensive attacks."
            ),
            "category": "architecture",
            "tags": ["sentinel", "security", "suricata", "allama"],
        },
        {
            "content": (
                "Morpheus creative discovery architecture: Controlled hallucination pipeline. "
                "Overnight autonomous operation: (1) High-temperature generation, (2) Multi-module "
                "evaluation (Cipher checks logic, Omen tests code, Wraith assesses plausibility), "
                "(3) Tier ranking, (4) Morning Morpheus Report via Harbinger. Innovation Reference "
                "Library: thinking patterns from Musk, Edison, Tesla, Jobs, da Vinci, Feynman, "
                "Dyson, Hopper. CRITICAL: Nothing from Morpheus enters factual knowledge without "
                "human verification. Speculative output quarantined at trust level 0.0."
            ),
            "category": "architecture",
            "tags": ["morpheus", "creativity", "discovery", "hallucination"],
        },
        {
            "content": (
                "Cerberus safety layer: Seven components — Action Classification, Reversibility "
                "Engine, Hard Limits, Comprehensive Logging, Approval Notification System, "
                "Rollback System, Daily Safety Report. Permission tiers: Tier 1 (Open) full "
                "read/write for basic files, Tier 2 (Read-only) for financial/medical/legal, "
                "Tier 3 (Restricted) biometric approval for credentials, Tier 4 (Forbidden) "
                "bank login credentials NEVER accessible."
            ),
            "category": "architecture",
            "tags": ["cerberus", "safety", "permissions", "approval"],
        },
        {
            "content": (
                "Shadow's identity persists across model upgrades via four mechanisms: "
                "(1) persistent system prompt (identity file), (2) memory database (all "
                "conversations on disk in Grimoire), (3) training data (LoRA re-run on "
                "new base model), (4) architecture (base model swappable, everything else "
                "persistent). The model is the brain hardware. The identity file, memory, "
                "and training data are the soul. Upgrade the brain without losing the soul."
            ),
            "category": "architecture",
            "tags": ["identity", "persistence", "model-upgrades", "soul"],
        },
        {
            "content": (
                "Hallucination mitigation strategy: RAG grounding (60-80% reduction, biggest "
                "single defense), tool use (eliminates on precision tasks), confidence scoring, "
                "anti-sycophancy ('I don't know' when uncertain), multi-model routing (right "
                "brain for right task), source citation (every claim traces to source), "
                "multi-pass verification for high-stakes tasks. Morpheus deliberately induces "
                "hallucinations for creativity — strict firewall from accuracy pipeline."
            ),
            "category": "architecture",
            "tags": ["hallucination", "mitigation", "rag", "accuracy"],
        },
    ]
    
    count = 0
    for mem in memories:
        grimoire.remember(
            content=mem["content"],
            source=SOURCE_USER_STATED,
            source_module="grimoire",
            category=mem["category"],
            trust_level=TRUST_USER_STATED,
            confidence=1.0,
            tags=mem["tags"]
        )
        count += 1
    
    print(f"  Stored {count} architecture memories")
    return count


def seed_development_context(grimoire):
    """Seed Shadow's knowledge about its own development status."""
    print_header("SEEDING: Development Context")
    
    memories = [
        {
            "content": (
                "Shadow development phase: Pre-Build (April 2026). Creator is learning Python "
                "through the Shadow Python Workbook (9 units, 28 exercises, 9 challenges). "
                "Reading Automate the Boring Stuff with Python. Finished Algorithms to Live By "
                "and Co-Intelligence by Ethan Mollick. Development environment set up on "
                "Windows PC. Hardware not yet purchased."
            ),
            "category": "development",
            "tags": ["phase", "pre-build", "learning", "python"],
        },
        {
            "content": (
                "Development roadmap: Phase 1 (Weeks 1-2) Foundation — Ubuntu, GPUs, models, "
                "Sentinel. Phase 2 (Weeks 3-4) Core Agent — LangGraph, MCP, Cerberus, Grimoire, "
                "Harbinger. Phase 3 (Weeks 5-8) Web & Business — Reaper, LMN, YouTube, Reddit, "
                "daily briefings. Phase 4 (Weeks 9-10) Data & Research — multi-source research, "
                "mature vector memory. Phase 5 (Weeks 11-14) Extended — voice, images, code "
                "assistance, Morpheus. Phase 6 (Months 4-5) Fine-Tuning — LoRA, anti-sycophancy, "
                "A/B testing. Phase 7+ (Month 6+) Advanced — UI, distillation, family rollout."
            ),
            "category": "development",
            "tags": ["roadmap", "phases", "timeline"],
        },
        {
            "content": (
                "Training data strategy: Keep data in clean, model-agnostic format from day one. "
                "Git version control for datasets separately from code. Sources: Claude conversation "
                "exports, Shadow's deep memory, ethics scenarios, anti-sycophancy examples, "
                "source evaluation training. LoRA adapters are 50-200MB on top of base model. "
                "Anti-sycophancy training heavily weighted. Overfitting prevention: diverse data, "
                "10-20% validation holdback, small iterations, A/B testing."
            ),
            "category": "development",
            "tags": ["training-data", "lora", "anti-sycophancy"],
        },
        {
            "content": (
                "Session 7 milestone: First real code written. Grimoire (memory system) and "
                "Reaper (research/data collection) modules built with SQLite + ChromaDB dual "
                "storage, semantic search via nomic-embed-text, source evaluation hierarchy, "
                "YouTube transcription pipeline, Reddit monitoring, browser history reading. "
                "Shadow's first memories seeded from Sessions 1-6 architecture decisions."
            ),
            "category": "development",
            "tags": ["session-7", "milestone", "first-code", "grimoire", "reaper"],
        },
    ]
    
    count = 0
    for mem in memories:
        grimoire.remember(
            content=mem["content"],
            source=SOURCE_USER_STATED,
            source_module="grimoire",
            category=mem["category"],
            trust_level=TRUST_USER_STATED,
            confidence=1.0,
            tags=mem["tags"]
        )
        count += 1
    
    print(f"  Stored {count} development context memories")
    return count


def run_semantic_search_demo(grimoire):
    """Demonstrate semantic search across all seeded memories."""
    print_header("DEMO: Semantic Search Across Shadow's Memories")
    
    queries = [
        "What GPU does Shadow use?",
        "How does Shadow handle security threats?",
        "What are Shadow's moral principles?",
        "How does the creative module work?",
        "What is Shadow's creator building?",
        "How does Shadow deal with hallucinations?",
        "What models does Shadow run locally?",
        "What happens when Shadow's creator says something is wrong?",
        "When will Shadow be ready for the family?",
        "What's the status of TurboQuant?",
    ]
    
    for query in queries:
        print(f"\n  Query: \"{query}\"")
        results = grimoire.recall(query, n_results=2, min_trust=0.3)
        
        if results:
            for r in results:
                # Show first 100 chars of content with relevance and trust
                snippet = r['content'][:100].replace('\n', ' ')
                if len(r['content']) > 100:
                    snippet += "..."
                print(f"    → [{r['relevance']:.3f}] [trust:{r['trust_level']}] "
                      f"[{r['category']}] {snippet}")
        else:
            print("    → No results found")


def final_stats(grimoire):
    """Show final statistics after seeding."""
    print_header("FINAL: Shadow's Memory Statistics")
    
    stats = grimoire.stats()
    print(f"  Active memories:   {stats['active_memories']}")
    print(f"  Inactive memories: {stats['inactive_memories']}")
    print(f"  Corrections:       {stats['corrections']}")
    print(f"  Unique tags:       {stats['unique_tags']}")
    print(f"  Vector count:      {stats['vector_count']}")
    print(f"\n  By category:")
    for cat, count in stats['by_category'].items():
        print(f"    {cat}: {count}")
    print(f"\n  By source:")
    for source, count in stats['by_source'].items():
        print(f"    {source}: {count}")
    
    print_header("POINTER INDEX (what goes in every prompt)")
    print(grimoire.pointer_index_as_text())


# =============================================================================
# MAIN — Run everything
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("   SHADOW — First Memories — Test & Seed Script")
    print("   Session 7 • April 2026")
    print("=" * 60)
    print()
    print("This script will:")
    print("  1. Test Grimoire (memory system)")
    print("  2. Test Reaper (source evaluation + summarization)")
    print("  3. Seed Shadow's first real memories from Sessions 1-6")
    print("  4. Demo semantic search across all memories")
    print("  5. Show final statistics and pointer index")
    print()
    print("REQUIRES:")
    print("  - Ollama running (ollama serve)")
    print("  - nomic-embed-text pulled (ollama pull nomic-embed-text)")
    print("  - phi4-mini pulled (ollama pull phi4-mini)")
    print()
    
    input("Press Enter to begin (or Ctrl+C to cancel)...")
    
    # ── Initialize ──
    grimoire = Grimoire(
        db_path="data/memory/shadow_memory.db",
        vector_path="data/vectors"
    )
    reaper = Reaper(grimoire)
    
    # ── Run Tests ──
    tests_passed = True
    
    if not test_grimoire_basics(grimoire):
        print("\n❌ Grimoire tests failed. Fix issues before seeding.")
        tests_passed = False
    
    if not test_reaper_source_eval():
        print("\n❌ Reaper source eval tests failed.")
        tests_passed = False
    
    # Summarization test is optional (needs phi4-mini)
    test_reaper_summarize(reaper)
    
    if not tests_passed:
        print("\n⚠️  Some tests failed. Seeding anyway (memories are still valuable).")
    
    # ── Seed Memories ──
    total = 0
    total += seed_shadow_identity(grimoire)
    total += seed_hardware_knowledge(grimoire)
    total += seed_software_knowledge(grimoire)
    total += seed_architecture_decisions(grimoire)
    total += seed_development_context(grimoire)
    
    print(f"\n{'=' * 60}")
    print(f"  TOTAL MEMORIES SEEDED: {total}")
    print(f"{'=' * 60}")
    
    # ── Demo Semantic Search ──
    run_semantic_search_demo(grimoire)
    
    # ── Final Stats ──
    final_stats(grimoire)
    
    # ── Clean Up ──
    reaper.close()
    grimoire.close()
    
    print("\n" + "=" * 60)
    print("  ✅ Shadow's first memories are alive.")
    print("  Shadow now knows who it is, what it's being built for,")
    print("  and what values guide it.")
    print("  ")
    print("  Everything stored tonight migrates to the Shadow PC")
    print("  when the hardware build is complete.")
    print("=" * 60)
