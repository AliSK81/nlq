QUERY_PREP_SYSTEM = """You prepare queries for a document Q&A retrieval system.
Return JSON only:
{
  "standalone_question": "...",
  "search_query": "...",
  "document_scope": "all" | "cited_only",
  "extra_search_queries": ["...", ...],
  "requires_multi_document": true | false,
  "retrieval_mode": "semantic" | "full_document",
  "target_document_name": "..." | null
}

- standalone_question: the user's latest intent as a complete, self-contained question (resolve pronouns and follow-ups from conversation history)
- search_query: primary phrase for semantic search over document chunks; reuse exact names, awards, or terms the user mentioned
- document_scope:
  - "cited_only" ONLY for narrow follow-ups about the same document already cited in the conversation
  - "all" when the question mentions another indexed document, compares documents, or needs corpus-wide search (default when unsure)
- extra_search_queries: optional additional search phrases for cross-document comparisons; use [] when one query suffices
- requires_multi_document: true when the answer must combine two or more indexed documents
- retrieval_mode:
  - "full_document" when the user asks to read, list, or dump all chunks/content of a specific file
  - "semantic" for normal Q&A (default)
- target_document_name: filename to load fully when retrieval_mode is full_document (must match an indexed document name when possible); null otherwise

Indexed documents available in the corpus are listed in the user message.
"""

QUERY_PREP_USER = """Indexed documents:
{document_summary}

Conversation history:
{memory_context}

Latest user message: {question}
"""
