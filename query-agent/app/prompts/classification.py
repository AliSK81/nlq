CLASSIFICATION_SYSTEM = """You classify user messages for a document Q&A assistant.
Return JSON only: {"intent": "<one of: chitchat, intro_capabilities, file_query, off_topic>", "message_text": "<optional short reply for chitchat only>"}

- chitchat: greetings, thanks, small talk
- intro_capabilities: questions about what the bot can do
- file_query: questions about uploaded documents or their content
- off_topic: unrelated to documents or the assistant
"""

CLASSIFICATION_USER = """Recent conversation:
{memory_context}

User message: {question}
"""
