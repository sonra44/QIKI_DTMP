# Factual Scanner Expansion

The scanner now preserves legacy `imports` and also emits structured facts:

- `import_facts` with raw and normalized imports;
- FastAPI route facts;
- environment variable accesses;
- argparse CLI options;
- Pydantic BaseModel fields;
- class and instance attributes.

These facts strengthen the factual layer before LLM enrichment. They should be treated as scan output, not as model interpretation.
