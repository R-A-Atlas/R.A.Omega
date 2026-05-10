The test shows Status 200 but TLDR, trader_memo, and final_report are all N/A. 
The /omega endpoint calls OmegaAgent from atlas_omega.py which does NOT have 
the 10 loops. The 10 loops are in QueryRouter from query_router.py which is 
called by the /query endpoint.

Please do two things:

1. Read test_result_soun.json completely and show me the top-level keys so 
we can see what the /omega endpoint actually returned.

2. Update test_omega.py to test the /query endpoint instead of /omega for 
the SOUN analysis, since /query uses QueryRouter which has all 10 loops.
The payload format for /query is:
{"query": "Analyze my SOUN $14 Call (Exp 06/18) given today's earnings beat, 
the Walmart ONN TV integration, the 11% AH drop. My avg cost was $0.52. 
Should I hold, roll, or exit?"}

Then run the updated test and show me the output.