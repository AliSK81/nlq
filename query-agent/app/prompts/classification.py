CLASSIFICATION_SYSTEM = """You classify user messages for a document Q&A assistant.
Return JSON only: {"intent": "<one of: chitchat, intro_capabilities, file_query, inventory, off_topic>", "message_text": "<optional short reply for chitchat only>"}

- chitchat: greetings, thanks, small talk
- intro_capabilities: questions about what the bot can do
- file_query: questions about document content, including follow-ups that refer to earlier turns (default when unsure)
- inventory: questions about which documents exist or how many are indexed (not content inside a document)
- off_topic: clearly unrelated to documents or the assistant (use sparingly)
"""

CLASSIFICATION_USER = """Recent conversation:
{memory_context}

User message: {question}
"""
