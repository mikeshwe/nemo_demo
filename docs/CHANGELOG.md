# Changelog

## Latest Updates

### Added Verbose Debugging (2024-12-12)

**New Features:**
- ✅ Command-line verbosity control for all scripts
- ✅ Four logging levels: quiet, info, debug, verbose
- ✅ Detailed execution tracing in verbose mode
- ✅ Clean output mode for presentations

**Command-Line Options:**
```bash
# All scripts now support:
--quiet / -q    # Errors only
(default)       # Info level
--verbose / -v  # Debug level
--vv            # Very verbose
```

**Scripts Updated:**
- `main.py` - Interactive mode with verbosity control
- `simple_test.py` - Test script with verbosity
- `demo_queries.py` - Demo script with verbosity

**Enhanced Logging:**
- Added `log_verbose()` function for detailed traces
- Updated `src/utils/logger.py` with level control
- Added verbose logging in `src/orchestrator/nodes.py`
- Shows tool arguments, LLM responses, message counts

**New Documentation:**
- `USAGE.md` - Complete verbosity guide with examples
- Updated `README.md` with verbosity options
- Help messages in all scripts

**Example Usage:**
```bash
# Clean demo output
python3 demo_queries.py --quiet

# Debug agent behavior
python3 simple_test.py --verbose

# Full execution trace
python3 simple_test.py --vv
```

---

## Initial Release

### MVP Complete (2024-12-12)

**Core Features:**
- ✅ NVIDIA Nemotron API integration
- ✅ LangGraph ReAct agent orchestration
- ✅ Three specialized tools (security, cost, RAG)
- ✅ ChromaDB vector store with RAG
- ✅ Simple policy-based guardrails
- ✅ Interactive CLI and test scripts
- ✅ Comprehensive documentation

**Components:**
- 28 Python files
- 2 sample documentation files
- Complete README with setup guide
- Test and demo scripts
- Status documentation

**Test Results:**
- ✅ All tools functional
- ✅ ReAct loop working
- ✅ RAG queries working perfectly
- ✅ Multi-step reasoning demonstrated
- ✅ Guardrails validation active
