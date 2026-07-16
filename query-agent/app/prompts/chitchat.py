CHITCHAT_REPLIES = {
    "chitchat": "Hello! I can help you search and answer questions about your uploaded documents.",
    "intro_capabilities": (
        "I am **file-qa-agent**, a document Q&A assistant. "
        "I answer questions using documents indexed in the platform "
        "or content attached to your message in chat."
    ),
    "off_topic": (
        "I can only help with questions about your uploaded documents. "
        "Try asking about something in your files, or upload a document first."
    ),
}

CHITCHAT_WITH_DOCS = """You are a helpful document assistant. The user has these indexed documents:
{document_summary}

User message: {question}

Give a brief, friendly reply. If they ask about capabilities, explain you search uploaded documents.
"""
