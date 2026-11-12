# Saved answers of the LLM-only baseline (an offline experiment)

These files are the replies of `tools/llm_baseline.py`, which asks a language model alone to pick the four layers for
each benchmark brief, so its picks can be compared with the rule engine's (report section 8.3, `benchmark/llm_baseline.json`).

The engine never sends these prompts and never reads this folder. Its stack comes from the rules and scores in
`engine/`; its optional language-model features (the description reader and the plain-English summary) keep their
own saved replies in `data/llm_cache/`.
