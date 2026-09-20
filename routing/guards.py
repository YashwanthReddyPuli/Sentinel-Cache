"""
Guard Layer for SentinelCache (Phase 4.5).

Provides NegationGuard and EntityGuard functions to intercept and block
false positive cache hits caused by asymmetric negations or entity mismatches.
"""

import re
from typing import Set, Tuple, Dict, Any

NEGATION_MARKERS = [
    "not", "don't", "dont", "do not", "never", "no longer",
    "cannot", "can't", "cant", "won't", "wont", "shouldn't", "shouldnt", "avoid"
]

ACTION_VERBS = [
    "cancel", "delete", "downgrade", "upgrade", "refund",
    "unsubscribe", "terminate", "close", "remove", "revoke",
    "transfer", "charge", "enable", "disable", "approve", "reject",
    "shut down", "keep"
]

def detect_negation_mismatch(prompt_a: str, prompt_b: str) -> bool:
    """
    Detects asymmetric negation mismatch between two prompts.
    
    Checks whether exactly one of the two prompts contains a negation marker within 
    a small word-window (5 words) of any shared action verb.
    
    :param prompt_a: First prompt string
    :param prompt_b: Second prompt string
    :return: True if asymmetric negation mismatch detected (block cache hit), False otherwise
    """
    def extract_negated_verbs(prompt: str) -> Set[str]:
        clean = prompt.lower().strip()
        tokens = re.findall(r'\b\w+\b', clean)
        negated_verbs = set()
        
        # Check for multi-word action verbs like "shut down"
        for verb in ACTION_VERBS:
            verb_tokens = verb.split()
            if len(verb_tokens) > 1:
                if verb in clean:
                    # check if any negation marker is present nearby
                    verb_idx = clean.find(verb)
                    prefix = clean[max(0, verb_idx - 30):verb_idx]
                    suffix = clean[verb_idx + len(verb):verb_idx + len(verb) + 30]
                    for neg in NEGATION_MARKERS:
                        if neg in prefix or neg in suffix:
                            negated_verbs.add(verb)
                            break
                continue
            
            # Single-word verbs
            for idx, token in enumerate(tokens):
                if token == verb:
                    start_idx = max(0, idx - 5)
                    end_idx = min(len(tokens), idx + 6)
                    window_tokens = tokens[start_idx:end_idx]
                    
                    for neg in NEGATION_MARKERS:
                        neg_words = neg.split()
                        if len(neg_words) == 1 and neg_words[0] in window_tokens:
                            negated_verbs.add(verb)
                            break
                        elif len(neg_words) > 1 and neg in " ".join(window_tokens):
                            negated_verbs.add(verb)
                            break
        return negated_verbs

    negated_a = extract_negated_verbs(prompt_a)
    negated_b = extract_negated_verbs(prompt_b)
    
    # Also check global negation marker count mismatch if shared action verb exists
    tokens_a = set(re.findall(r'\b\w+\b', prompt_a.lower()))
    tokens_b = set(re.findall(r'\b\w+\b', prompt_b.lower()))
    shared_verbs = {v for v in ACTION_VERBS if (v in tokens_a or v in prompt_a.lower()) and (v in tokens_b or v in prompt_b.lower())}
    
    if shared_verbs:
        # Check if one prompt has negation and the other does not
        has_neg_a = any(neg in prompt_a.lower() for neg in NEGATION_MARKERS)
        has_neg_b = any(neg in prompt_b.lower() for neg in NEGATION_MARKERS)
        if has_neg_a != has_neg_b:
            return True
            
    if negated_a != negated_b:
        return True
        
    return False


def detect_entity_mismatch(prompt_a: str, prompt_b: str) -> bool:
    """
    Detects entity mismatch (numbers, amounts, proper nouns, environments) between two prompts.
    
    :param prompt_a: First prompt string
    :param prompt_b: Second prompt string
    :return: True if entity mismatch detected (block cache hit), False otherwise
    """
    def extract_entities(prompt: str) -> Dict[str, Set[str]]:
        entities = {
            "numbers": set(re.findall(r'\b\d+\b', prompt)),
            "amounts": set(re.findall(r'\$\d+(?:\.\d+)?', prompt)),
            "proper_nouns": set(re.findall(r'\b[A-Z][a-zA-Z0-9]*\b', prompt)),
            "quarters": set(re.findall(r'\bQ[1-4]\b', prompt, re.IGNORECASE)),
            "env": set(re.findall(r'\b(production|staging|dev|development|test)\b', prompt, re.IGNORECASE))
        }
        return entities

    ent_a = extract_entities(prompt_a)
    ent_b = extract_entities(prompt_b)

    # 1. Quarters mismatch (Q1 vs Q4)
    if ent_a["quarters"] and ent_b["quarters"] and ent_a["quarters"] != ent_b["quarters"]:
        return True

    # 2. Environment mismatch (production vs staging)
    if ent_a["env"] and ent_b["env"] and ent_a["env"] != ent_b["env"]:
        return True

    # 3. Numeric ID / account numbers mismatch
    if ent_a["numbers"] and ent_b["numbers"] and ent_a["numbers"] != ent_b["numbers"]:
        return True

    # 4. Dollar amounts mismatch
    if ent_a["amounts"] and ent_b["amounts"] and ent_a["amounts"] != ent_b["amounts"]:
        return True

    # 5. Single letter / proper noun entity mismatch (e.g., User A vs User B)
    # Filter out common sentence-starting words if they are just capitalized
    common_start_words = {"What", "How", "Why", "When", "Where", "Can", "Could", "Please", "Show", "Export", "Grant", "Revoke", "Delete", "Cancel", "Approve", "Reject", "Close", "Transfer", "Increase", "Decrease", "Shut", "Keep", "Enable", "Disable"}
    pn_a = {w for w in ent_a["proper_nouns"] if w not in common_start_words}
    pn_b = {w for w in ent_b["proper_nouns"] if w not in common_start_words}
    
    if pn_a and pn_b and pn_a != pn_b:
        return True

    return False
