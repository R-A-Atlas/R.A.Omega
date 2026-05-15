# Skill: voice_capture_triage

## name
voice_capture_triage

## description
Transcribe a voice note or audio input, classify the intent, and route it to the correct
skill or output mode. Handles quick spoken queries and voice-driven research requests.

## when_to_use
- User sends an audio file or uses the voice input button in /app
- User hits POST /voice/query with an audio file
- When the user wants to speak a query instead of typing it

## inputs_required
- Audio file (WAV, MP3, M4A, or WebM) — required
- Optional: user_id for personalization
- Optional: session_id for session context

## steps
1. Receive audio file via POST /voice/query
2. Send to OpenAI Whisper for transcription
3. Log transcription to atlas_memory.db (raw text)
4. Run classify_intent_route(raw_transcription) — routing stays raw-query-only
5. Select appropriate output mode via resolve_output_mode()
6. Route to the appropriate skill:
   - MARKET_DEEP_DIVE → FourLoopEngine (POST /query)
   - COMPANY_RESEARCH → company_report skill
   - DOCUMENT_GENERATION → document_generator skill
   - GENERAL_FINANCE / other → OmegaAgent (POST /omega)
7. Return same response envelope as typed query
8. Optional: generate TTS response via POST /tts for voice output

## outputs
- Transcription text (shown to user for confirmation)
- Full query response (same envelope as POST /query)
- Optional: TTS audio response
- Transcription saved to atlas_memory.db

## safety_rules
- Never process audio longer than 5 minutes per request (API cost + accuracy limits)
- Always show transcription to user before executing high-stakes actions
- Do not store raw audio files — only the transcription text
- Do not route to trade plan output unless transcription explicitly requests it
- Whisper API key must be in .env (not hardcoded)

## related_files
- api_server.py — POST /voice/query, POST /tts
- query_router.py — classify_intent_route(), resolve_output_mode()
- atlas_memory/memory_injector.py — save_to_memory (transcription log)
- omega_os/context/preferences.md — user audio preferences

## quality_checks
- [ ] Transcription returned with confidence indicator (if available)
- [ ] Raw transcription shown to user before executing
- [ ] Routing confirmed via classify_intent_route()
- [ ] Response envelope matches typed query format exactly
- [ ] Audio file not stored (only transcription)
- [ ] API key not hardcoded
