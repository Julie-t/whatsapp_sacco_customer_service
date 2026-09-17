"""Response constants and output formatting utilities.

All user-facing response strings and AI-output cleanup functions live here.
This module is a leaf dependency — it imports nothing from other app services.
"""

import re

# ---------------------------------------------------------------------------
# Greeting / Menu
# ---------------------------------------------------------------------------

GREETING_MESSAGE = (
    "👋 Karibu! I'm your SACCO financial companion. How can I help you today?"
)

CAPABILITY_MENU = (
    "I can help with:\n"
    "1. SACCO information\n"
    "2. Financial education\n"
    "3. Your financial goals\n"
    "4. Connecting you with SACCO staff\n\n"
    "You can ask your question directly in your own words, or type a number (1-4)."
)
WELCOME_MESSAGE = CAPABILITY_MENU

ASSISTANT_CAPABILITY_RESPONSE = (
    "Karibu! Yes, I am your SACCO financial companion and I can assist you right here on WhatsApp. "
    "You can ask me about:\n"
    "• SACCO membership, loan products, and interest rates\n"
    "• Checking your savings and loan balances\n"
    "• Setting and tracking your financial savings goals\n"
    "• Explanations of financial concepts like compound interest\n\n"
    "What would you like help with today?"
)

# ---------------------------------------------------------------------------
# Fallback / Placeholder messages
# ---------------------------------------------------------------------------

FALLBACK_MESSAGE = (
    "Thank you for your message. My AI assistant capabilities are being introduced soon. "
    "For now, you can type HELP to see what I can do."
)

MEDIA_NOT_SUPPORTED = (
    "I can't process media messages yet. Please type HELP to see how I can assist you."
)

HUMAN_SUPPORT_PLACEHOLDER = (
    "Your request may need staff assistance. Human support connection is coming later. "
    "Please type HELP to see what is available now."
)

MEMBER_DATA_PLACEHOLDER = (
    "This question requires your personal SACCO information, which I don't have access "
    "to yet. A future version will connect this assistant to authorized member data."
)

MEMBER_NOT_RECOGNIZED = (
    "I couldn't verify your member information. "
    "Please contact a SACCO representative for help with personal account queries."
)

MEMBER_NO_ACCOUNTS = (
    "Your member profile is on file but I don't have account information available "
    "right now. Please contact a SACCO representative."
)

GENERAL_ASSISTANCE_PLACEHOLDER = (
    "General assistance is temporarily unavailable. Please contact a SACCO representative."
)

# ---------------------------------------------------------------------------
# Keyword sets
# ---------------------------------------------------------------------------

GREETINGS = {
    "hello",
    "hi",
    "hey",
    "habari",
    "mambo",
    "jambo",
    "sasa",
    "good morning",
    "good afternoon",
    "good evening",
    "good day",
}

MENU_TRIGGERS = {"menu", "help"}

MENU_RESPONSES: dict[str, str] = {
    "1": (
        "🏦 *SACCO Information*\n\n"
        "I can help with:\n"
        "• Membership requirements\n"
        "• Loan types and eligibility\n"
        "• Savings accounts and interest rates\n"
        "• Deposits and withdrawals\n"
        "• Dividends and shares\n\n"
        "Just ask me a question! For example:\n"
        "_\"What are the requirements to become a member?\"_"
    ),
    "2": (
        "📚 *Financial Education*\n\n"
        "I can explain topics like:\n"
        "• Budgeting and the 50/30/20 rule\n"
        "• Compound interest\n"
        "• Good debt vs bad debt\n"
        "• Emergency funds\n"
        "• Saving and investing basics\n\n"
        "Just ask me a question! For example:\n"
        "_\"How can I create a budget?\"_"
    ),
    "3": (
        "🎯 *Your Financial Goals*\n\n"
        "I can help you think through your savings goals and what "
        "it would take to reach them.\n\n"
        "Try asking something like:\n"
        "_\"How can I save for an emergency fund?\"_\n"
        "_\"I want to save KSh 300,000 to expand my shop next year.\"_"
    ),
    "4": HUMAN_SUPPORT_PLACEHOLDER,
}

# ---------------------------------------------------------------------------
# AI output cleanup
# ---------------------------------------------------------------------------


def clean_ai_artifacts(text: str) -> str:
    """Strip common AI-writing artifacts that slip through despite prompt rules."""
    # Remove markdown bold/italic markers
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    # Replace em dashes and non-breaking hyphens with normal hyphens
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2011", "-")
    # Replace non-breaking spaces
    text = text.replace("\u202f", " ").replace("\u00a0", " ")
    # Remove sycophantic openers
    text = re.sub(
        r"^(Certainly!|Great question!|Absolutely!|Sure!|Of course!|I'd be happy to help[.!]?)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Remove "Here's/Here is" openers
    text = re.sub(r"^(Here'?s|Here is)[^:]*:\s*", "", text, flags=re.IGNORECASE)
    # Remove "Source:" blocks at the end
    text = re.sub(r"\n*Sources?:\s*\n.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove "Note:" disclaimer blocks at the end
    text = re.sub(
        r"\n*Note:\s*(?:The details|These|This|Please).*$",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text.strip()


def format_rag_response(response) -> str:
    """Format a RAG answer response, cleaning AI artifacts."""
    return clean_ai_artifacts(response.answer)
