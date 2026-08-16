# Place this near your other prompt definitions (e.g., in ..groq or at the top of your file)
INTENT_ROUTER_PROMPT = """
You are an intent classifier. Analyze the user's input and classify it into one of two categories:
1. "DB_QUERY": If the user is asking for data, metrics, reports, filtering records, or anything requiring a database search.
2. "GENERAL": If the user is greeting you (e.g., "hello", "hi"), saying goodbye, thanking you, or asking general conversational questions unrelated to data.

Respond with ONLY the category name ("DB_QUERY" or "GENERAL"). Do not include any other text.

User Input: "{user_query}"
Category:"""

