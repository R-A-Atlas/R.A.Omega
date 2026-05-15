# Skill: research_queue

## name
research_queue

## description
Manage a queue of research tasks. Add tickers or topics, prioritize them, execute them
in batch during off-peak hours, and surface completed research when the user is ready.

## when_to_use
- User says "add [ticker] to my research queue"
- User says "research these when you have time: [list]"
- During batch research runs (off-peak, low API cost periods)
- When the user has > 3 tickers queued for deep research

## inputs_required
- Ticker or topic to queue (required)
- Optional: priority level (urgent / normal / low)
- Optional: research type (deep / company_report / quick)

## steps
1. Accept ticker/topic and add to research_queue.json in atlas_vault/04-Projects/
2. Assign priority (urgent / normal / low) based on user input or default to normal
3. Log queue status: pending | in_progress | complete | failed
4. When executing queue:
   a. Sort by priority (urgent first)
   b. For each item: route to appropriate path (deep → POST /query, company → OmegaAgent)
   c. Save result to atlas_vault/03-Outputs/research_<ticker>_<date>.json
   d. Update queue item status to complete or failed
   e. Log to atlas_memory.db (learn from research)
5. Surface completed research when user opens /app or asks for results
6. Archive completed queue items after 7 days

## outputs
- research_queue.json updated with new item
- Research results saved to atlas_vault/03-Outputs/
- Queue status dashboard (pending / in_progress / complete / failed counts)
- Completed research summary when surfaced

## safety_rules
- Never auto-execute research for tickers that would generate trade plans without user opt-in
- Maximum queue depth: 50 items (reject if full)
- Do not run deep research (POST /query) in parallel for more than 3 tickers simultaneously (API cost)
- Failed items must be logged with reason and not silently dropped

## related_files
- atlas_vault/03-Outputs/ — research output directory
- atlas_vault/04-Projects/ — queue file location
- deep_research.py — deep research pipeline
- atlas_omega.py — OmegaAgent for company/quick research
- atlas_memory/memory_injector.py — learn from research

## quality_checks
- [ ] Queue item added with correct status (pending)
- [ ] Priority assigned (urgent / normal / low)
- [ ] Research result saved to atlas_vault/03-Outputs/
- [ ] Queue item marked complete or failed (not left as in_progress)
- [ ] Failed items logged with reason
- [ ] No more than 3 deep research calls in parallel
