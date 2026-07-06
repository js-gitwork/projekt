_CONTEXTS = {}


def save_context(user_key="default", context=None):
    _CONTEXTS[user_key] = context or {}
    return _CONTEXTS[user_key]


def get_context(user_key="default"):
    return _CONTEXTS.get(user_key, {})


def clear_context(user_key="default"):
    _CONTEXTS.pop(user_key, None)
