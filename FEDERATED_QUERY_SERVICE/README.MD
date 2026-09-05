# FEDERATED_QUERY_SERVICE

The single query layer above both arms -- decides whether a query needs
document search (RAG_SERVICE, hybrid vector+BM25 over Chroma/Postgres),
structured/institutional search (AICTE_PIPELINE/11_RETRIEVAL, hybrid
Postgres+pgvector), or both -- and merges the results.

Not yet implemented -- this is the one genuinely new piece of code needed.
Everything it calls into already exists and works on its own:
- RAG_SERVICE's hybrid retrieval (document side)
- AICTE_PIPELINE/11_RETRIEVAL/HYBRID_RETRIEVER.py (structured side --
  already does its own structured/vector/hybrid routing internally)

## The real complication this service has to handle

The two sides live in **separate Postgres databases** (this warehouse on
port 5432, AICTE's canonical DB on port 55432 -- see
STRUCTURED_INTEGRATION/README.MD). This service can't do a SQL join across
them. It has to:
1. Query RAG_SERVICE and AICTE_PIPELINE's retriever independently
2. Merge/rank the two result sets in application code
3. Use `document_mart.aicte_institution_id` to associate a document with
   an institution record when both are relevant to the same query

Example: "show me everything related to XYZ College" -- pulls matching
institution/course/faculty rows from the AICTE side, AND documents whose
`aicte_institution_id` matches, from the document side, in one response.
