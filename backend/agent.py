import os
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ollama import chat as ollama_chat

from gmail_client import GmailClient
from memory_store import MemoryStore, LabeledEmail


class AgentState(dict):
    pass


def build_prompt(subject: Optional[str], sender: Optional[str], snippet: Optional[str], labels: List[str], similar_examples: List[Dict]) -> str:
    examples_text = "\n".join(
        [
            f"- Subject: {ex.get('subject')} | Sender: {ex.get('sender')} | Snippet: {ex.get('snippet')}\n  Applied Label: {ex.get('applied_label')}"
            for ex in similar_examples
        ]
    )
    content = f"""
You are an intelligent email classification assistant. Your job is to deeply analyze each email and suggest the MOST APPROPRIATE label.

YOUR TASK:
1. **ANALYZE THOROUGHLY**: Read the subject, sender, and content snippet carefully
2. **UNDERSTAND THE CONTEXT**: What is this email about? What is its purpose?
3. **CHECK EXISTING LABELS**: Does any existing label truly fit this email's purpose?
4. **CREATE IF NEEDED**: If no existing label is a good match, create a NEW descriptive label

CRITICAL RULES:
- NEVER use generic labels like "Uncategorized", "Other", "Misc", or "General"
- ALWAYS create a specific, meaningful label that describes the email's actual purpose
- Think about future emails: "Will similar emails fit under this label?"
- Use the sender, subject, and content to inform your decision
- ALWAYS add an appropriate emoji to NEW labels for better visual identification

EXAMPLES OF GOOD LABELING WITH EMOJIS:
✓ Google security alert → "Security Alerts 🚨" or "Account Notifications 🔐"
✓ ICICI Bank credit card payment → "Credit Card Payments 💳" or "Banking Transactions 🏦"
✓ Flipkart order confirmation → "Shopping Orders 🛒" or "E-commerce 📦"
✓ CoinSwitch transaction → "Investments 📈" or "Crypto Transactions ₿"
✓ Netflix subscription renewal → "Subscriptions 📺" or "Entertainment 🎬"
✓ LinkedIn job alert → "Job Alerts 💼" or "Career Opportunities 🚀"
✓ Electricity bill → "Utility Bills ⚡"
✓ Travel booking → "Travel Plans ✈️"
✓ Insurance policy → "Insurance 📋"
✓ Tax documents → "Tax Documents 📊"
✓ Health appointments → "Health & Medical 🏥"
✓ Educational content → "Learning & Education 📚"

LABEL FORMATTING:
- Use title case (e.g., "Credit Card Payments 💳")
- Keep it concise but descriptive (2-4 words)
- ALWAYS include a relevant emoji at the end for new labels
- Choose emojis that clearly represent the category (🛒 for shopping, 💳 for payments, etc.)

EXISTING LABELS:
{labels if labels else "No existing custom labels"}

EMAIL TO CLASSIFY:
Subject: {subject}
From: {sender}
Snippet: {snippet}

SIMILAR EMAILS FROM MEMORY (for reference):
{examples_text if examples_text else "None"}

IMPORTANT: 
- Think about what category this email belongs to
- If it's a security alert, suggest "Security Alerts 🚨"
- If it's about payments, suggest "Credit Card Payments 💳" or "Banking Transactions 🏦"  
- If it's promotional, suggest "Shopping Promotions 🛒" or the specific store name
- NEVER default to "Uncategorized" - always create a meaningful category
- ALWAYS include an appropriate emoji for new labels

Return a JSON object with fields: "label" (string - a specific, meaningful label WITH emoji), "rationale" (string explaining why this label fits the email content).
""".strip()
    return content


# File logger (data/labeler.log)
logger = logging.getLogger("gmail_labeler")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    os.makedirs(os.path.join(os.getcwd(), "data"), exist_ok=True)
    fh = logging.FileHandler(os.path.join(os.getcwd(), "data", "labeler.log"))
    fh.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    
# Global variables to hold non-serializable clients
_gmail_client = None
_memory_store = None


def node_fetch_messages(state: AgentState) -> AgentState:
    global _gmail_client
    max_results: int = state.get("max_results", 5)
    messages = _gmail_client.get_unread_messages(max_results=max_results)
    logger.info("fetch_messages count=%d", len(messages))
    state["messages"] = messages
    return state


def node_classify(state: AgentState) -> AgentState:
    global _gmail_client, _memory_store
    gmail: GmailClient = _gmail_client
    memory: MemoryStore = _memory_store
    model: str = state.get("model", os.environ.get("OLLAMA_MODEL", "gemma3:4b"))
    # Ensure model name is valid - if user enters invalid model, skip
    if not model or model.strip() == "":
        model = "gemma3:4b"
    logger.info("classify node called with model=%s", model)

    messages: List[Dict] = state.get("messages", [])
    labels_api = gmail.list_labels()
    label_names = [lb["name"] for lb in labels_api]
    id_by_name = {lb["name"]: lb["id"] for lb in labels_api}

    # No more heuristics - we'll rely on embeddings for matching

    def majority_label_from_similar(similar_examples: List[Dict]) -> Optional[str]:
        counts: Dict[str, int] = {}
        for ex in similar_examples:
            lb = ex.get("applied_label")
            if not lb:
                continue
            counts[lb] = counts.get(lb, 0) + 1
        if not counts:
            return None
        # choose label with highest count
        best = max(counts.items(), key=lambda kv: kv[1])[0]
        return best

    def centroid_scoring(msg: Dict, labels: List[str], threshold: float = 0.35) -> Tuple[Optional[str], Dict[str, float]]:
        """Score message against per-label centroids using cosine similarity.
        
        Uses weighted centroids that prioritize user-approved labels.
        Excludes labels that were rejected for similar emails.
        Returns (best_label_above_threshold, score_by_label[0..1]).
        """
        # Get weighted centroids that prioritize accepted (user-approved) labels
        centroids = memory.get_label_centroids()
        if not centroids:
            return None, {}
        
        # Get rejected labels for similar emails to avoid suggesting them
        rejected_labels = memory.get_rejected_labels_for_similar_emails(
            msg.get("subject", ""),
            msg.get("from", ""),
            msg.get("snippet", "")
        )
        logger.info(f"Found {len(rejected_labels)} rejected labels to avoid: {rejected_labels}")
            
        # Create embedding for the current message
        joined = " \n ".join([x for x in [msg.get("subject"), msg.get("from"), msg.get("snippet")] if x])
        q = memory.embed_text(joined)
        
        # Calculate similarity scores with all label centroids (excluding rejected ones)
        score_map: Dict[str, float] = {}
        for label in labels:
            # Skip rejected labels
            if label in rejected_labels:
                logger.info(f"Skipping rejected label '{label}' for similar email")
                continue
                
            c = centroids.get(label)
            if c is None:
                continue
                
            # Cosine similarity (dot product for normalized vectors)
            score = float(np.dot(q, c))  # in [-1, 1]
            
            # Map to [0,1] range for easier interpretation
            score01 = (score + 1.0) / 2.0
            score_map[label] = score01
            
        if not score_map:
            return None, {}
            
        # Find the best matching label
        best_label, best_score = max(score_map.items(), key=lambda kv: kv[1])
        
        # Only return a label if it meets the threshold
        if best_score >= threshold:
            return best_label, score_map
            
        # Otherwise return no label but still include scores
        return None, score_map

    suggestions: List[Dict] = []
    for msg in messages:
        if not msg.get("id"):
            continue
        
        # Step 1: ALWAYS analyze email content against existing labels first
        # This ensures we properly classify emails even if they were previously mislabeled
        logger.info("Analyzing email: %s from %s", msg.get("subject"), msg.get("from"))
        
        # Use embedding-based similarity with existing labels (PRIMARY method)
        best_label, scores = centroid_scoring(msg, label_names, threshold=float(state.get("score_threshold", 0.40)))
        
        if best_label:
            # Found a good match with existing labels above threshold
            logger.info(
                "centroid_match msg_id=%s label=%s top_score=%.3f top3=%s",
                msg.get("id"),
                best_label,
                scores.get(best_label, 0.0),
                ", ".join([f"{k}:{scores[k]:.2f}" for k in sorted(scores, key=scores.get, reverse=True)[:3]]),
            )
            suggestions.append({
                "message": msg,
                "suggested_label": best_label,
                "label_id": id_by_name.get(best_label),
                "source": "centroid",
                "rationale": f"Best match among existing labels; score={(scores.get(best_label,0.0)*100):.1f}%",
                "scores": {k: round(v*100, 1) for k, v in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:10]},
            })
            continue
        
        # Step 2: No good match above threshold - check if we've seen similar emails before
        # Find similar emails from memory to use as examples
        logger.info("No strong match found (threshold=%.2f), checking memory for similar emails", float(state.get("score_threshold", 0.40)))
        similar_ids = [mid for mid, _ in memory.similar(msg.get("subject"), msg.get("from"), msg.get("snippet"), k=5)]
        similar_examples = memory.get_messages_by_ids(similar_ids)
        
        # Try to get a majority label from similar examples
        majority_lbl = majority_label_from_similar(similar_examples)
        if majority_lbl and majority_lbl in label_names:
            logger.info("memory_similar_majority msg_id=%s label=%s", msg.get("id"), majority_lbl)
            suggestions.append({
                "message": msg,
                "suggested_label": majority_lbl,
                "label_id": id_by_name.get(majority_lbl),
                "source": "memory_similar",
                "rationale": f"Based on {len(similar_examples)} similar emails in memory",
                "scores": {k: round(v*100, 1) for k, v in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:10]} if scores else {},
            })
            continue

        prompt = build_prompt(
            subject=msg.get("subject"),
            sender=msg.get("from"),
            snippet=msg.get("snippet"),
            labels=label_names,
            similar_examples=similar_examples,
        )
        try:
            response = ollama_chat(model=model, messages=[{"role": "user", "content": prompt}])
            content = response.get("message", {}).get("content", "").strip()
            logger.info(f"LLM raw response for msg_id={msg.get('id')}: {content[:200]}...")  # Log first 200 chars
        except Exception as e:
            logger.error(f"LLM call failed for msg_id={msg.get('id')}: {e}")
            # Skip this message if LLM fails - don't suggest any label
            continue

        # Check if content is empty
        if not content:
            logger.error(f"LLM returned empty response for msg_id={msg.get('id')}")
            continue

        # Parse the LLM response
        import json as _json
        label_name = None
        rationale = ""
        try:
            # Try to extract JSON from markdown code blocks if present
            if "```json" in content:
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
            elif "```" in content:
                # Remove any code block markers
                content = content.replace("```", "").strip()
            
            parsed = _json.loads(content)
            if isinstance(parsed, dict) and parsed.get("label"):
                label_name = str(parsed.get("label")).strip()
                rationale = str(parsed.get("rationale", "")).strip()
        except Exception as parse_error:
            # Try to heuristically extract a label from the content
            logger.warning(f"Failed to parse LLM JSON response for msg_id={msg.get('id')}: {parse_error}")
            logger.debug(f"Raw content was: {content}")
            for line in content.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    if key.lower().strip() in ["label", "\"label\""]:
                        label_name = val.strip().strip('"').strip(',')
                        break
        
        # If we couldn't extract a label at all, skip this message
        if not label_name:
            logger.error(f"Could not extract label from LLM response for msg_id={msg.get('id')}")
            logger.error(f"Full LLM response was: {content}")
            continue

        logger.info("llm_suggestion msg_id=%s label=%s rationale=%s", msg.get("id"), label_name, rationale)
        label_id = id_by_name.get(label_name)
        suggestions.append({
            "message": msg,
            "suggested_label": label_name,
            "label_id": label_id,
            "source": "llm",
            "rationale": rationale,
            "similar_examples": similar_examples,
            "scores": {},
        })

    state["suggestions"] = suggestions
    return state


def node_wait_for_approval(state: AgentState) -> AgentState:
    # UI should read suggestions and set approvals: Dict[msg_id, {approved: bool, final_label: str}]
    approvals: Dict[str, Dict[str, Any]] = state.get("approvals", {})
    state["approvals"] = approvals
    return state


def node_apply_and_update(state: AgentState) -> AgentState:
    """Apply approved labels to messages and update the memory store."""
    global _gmail_client, _memory_store
    gmail: GmailClient = _gmail_client
    memory: MemoryStore = _memory_store

    suggestions: List[Dict] = state.get("suggestions", [])
    approvals: Dict[str, Dict[str, Any]] = state.get("approvals", {})
    
    logger.info(f"node_apply_and_update: Processing {len(suggestions)} suggestions with {len(approvals)} approvals")
    
    try:
        # Get all labels from Gmail
        labels_api = gmail.list_labels()
        id_by_name = {lb["name"]: lb["id"] for lb in labels_api}
        logger.info(f"Retrieved {len(labels_api)} labels from Gmail")
        
        # Track what we've processed
        applied_count = 0
        memory_updated_count = 0
        
        for s in suggestions:
            try:
                msg = s["message"]
                msg_id = msg["id"]
                
                # Get the approval decision for this message
                decision = approvals.get(msg_id, {})
                approved: bool = bool(decision.get("approved", False))
                final_label: Optional[str] = decision.get("final_label") or s.get("suggested_label")
                
                logger.info(f"Processing msg_id={msg_id}, approved={approved}, label={final_label}")
                
                # Only apply labels if approved
                if approved and final_label:
                    try:
                        # Ensure label exists (create if needed)
                        label_id = id_by_name.get(final_label)
                        if not label_id:
                            logger.info(f"Creating new label: {final_label}")
                            label_id, _ = gmail.ensure_label(final_label)
                            id_by_name[final_label] = label_id
                            
                        # Apply the label
                        gmail.apply_label(msg_id, label_id)
                        logger.info(f"Successfully applied label_id={label_id} ('{final_label}') to msg_id={msg_id}")
                        applied_count += 1
                    except Exception as e:
                        logger.error(f"Error applying label to msg_id={msg_id}: {e}")
                
                # Get full message details if we only have ID
                if len(msg.keys()) <= 1:
                    try:
                        full_msg = gmail.get_message_by_id(msg_id)
                        msg = full_msg  # Use the full message details
                    except Exception as e:
                        logger.warning(f"Could not get full message details for {msg_id}: {e}")
                
                # Store in memory based on approval status
                if approved and final_label:
                    try:
                        # Store approved suggestions as good examples for future learning
                        memory.upsert_labeled_email(
                            LabeledEmail(
                                message_id=msg_id,
                                subject=msg.get("subject"),
                                sender=msg.get("from"),
                                snippet=msg.get("snippet"),
                                applied_label=final_label,
                                accepted=True,  # Only store approved examples
                            )
                        )
                        
                        logger.info(f"Stored approved example in memory: msg_id={msg_id}, label={final_label}")
                        memory_updated_count += 1
                    except Exception as e:
                        logger.error(f"Error storing approved example in memory for {msg_id}: {e}")
                
                elif not approved and final_label:
                    try:
                        # Store rejected suggestions as negative examples to avoid in future
                        memory.store_rejected_label(
                            message_id=msg_id,
                            subject=msg.get("subject", ""),
                            sender=msg.get("from", ""),
                            snippet=msg.get("snippet", ""),
                            rejected_label=final_label
                        )
                        
                        logger.info(f"Stored rejected label '{final_label}' to avoid for similar emails: msg_id={msg_id}")
                    except Exception as e:
                        logger.error(f"Error storing rejected label in memory for {msg_id}: {e}")
                
                # Mark email as processed (regardless of approval status)
                memory.mark_email_processed(msg_id, final_label or "Uncategorized", approved)
                
            except Exception as e:
                logger.error(f"Error processing suggestion: {e}")
                
        # Add summary to state
        state["apply_summary"] = {
            "suggestions_processed": len(suggestions),
            "labels_applied": applied_count,
            "memory_updates": memory_updated_count
        }
        logger.info(f"node_apply_and_update complete: {applied_count} labels applied, {memory_updated_count} memory entries updated")
        
    except Exception as e:
        logger.error(f"Error in node_apply_and_update: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    return state


def build_graph() -> Tuple[StateGraph, Any]:
    graph = StateGraph(AgentState)
    graph.add_node("fetch", node_fetch_messages)
    graph.add_node("classify", node_classify)
    graph.add_node("approve", node_wait_for_approval)
    graph.add_node("apply", node_apply_and_update)

    graph.set_entry_point("fetch")
    graph.add_edge("fetch", "classify")
    graph.add_edge("classify", "approve")
    graph.add_edge("approve", "apply")
    graph.add_edge("apply", END)

    # Compile without a checkpointer to avoid serializing non-JSON-safe objects in state
    app = graph.compile()
    return graph, app


def classify_emails_streaming(
    gmail: GmailClient,
    memory_store: MemoryStore,
    max_results: int = 5,
    model: Optional[str] = None,
    score_threshold: Optional[float] = None,
):
    """Stream email classification results one by one as they're processed.
    
    Yields: Dict with suggestion for each email as it's processed
    """
    global _gmail_client, _memory_store
    _gmail_client = gmail
    _memory_store = memory_store
    
    # Fetch unread emails (no filtering)
    messages = gmail.get_unread_messages(max_results=max_results)
    logger.info(f"Fetched {len(messages)} unread emails for streaming classification")
    
    if not messages:
        return
    
    # Get labels
    labels_api = gmail.list_labels()
    label_names = [lb["name"] for lb in labels_api]
    id_by_name = {lb["name"]: lb["id"] for lb in labels_api}
    
    model_name = model or os.environ.get("OLLAMA_MODEL", "gemma3:4b")
    threshold = score_threshold or 0.40
    
    # Process each email and yield immediately
    for msg in messages:
        if not msg.get("id"):
            continue
        
        try:
            # Use the same logic as node_classify but yield each result
            from agent import node_classify
            
            # Create a mini-state for this one message
            mini_state = {
                "messages": [msg],
                "model": model_name,
                "score_threshold": threshold,
            }
            
            # Call the classify logic (but we need to extract the code)
            # For now, let's inline the classification logic
            suggestion = _classify_single_email(msg, label_names, id_by_name, memory_store, model_name, threshold)
            
            if suggestion:
                yield suggestion
                
        except Exception as e:
            logger.error(f"Error processing email {msg.get('id')}: {e}")
            continue


def _classify_single_email(msg: Dict, label_names: List[str], id_by_name: Dict[str, str], 
                           memory: MemoryStore, model: str, threshold: float) -> Optional[Dict]:
    """Classify a single email and return the suggestion."""
    import numpy as np
    from ollama import chat as ollama_chat
    
    logger.info("Analyzing email: %s from %s", msg.get("subject"), msg.get("from"))
    
    # Use embedding-based similarity (same logic as node_classify)
    def centroid_scoring(msg: Dict, labels: List[str], threshold: float = 0.35):
        centroids = memory.get_label_centroids()
        if not centroids:
            return None, {}
            
        joined = " \n ".join([x for x in [msg.get("subject"), msg.get("from"), msg.get("snippet")] if x])
        q = memory.embed_text(joined)
        
        score_map: Dict[str, float] = {}
        for label in labels:
            c = centroids.get(label)
            if c is None:
                continue
            score = float(np.dot(q, c))
            score01 = (score + 1.0) / 2.0
            score_map[label] = score01
            
        if not score_map:
            return None, {}
            
        best_label, best_score = max(score_map.items(), key=lambda kv: kv[1])
        
        if best_score >= threshold:
            return best_label, score_map
            
        return None, score_map
    
    best_label, scores = centroid_scoring(msg, label_names, threshold=threshold)
    
    if best_label:
        logger.info("Found strong match: %s (%.1f%%)", best_label, scores[best_label] * 100)
        return {
            "message": msg,
            "suggested_label": best_label,
            "label_id": id_by_name.get(best_label),
            "source": "embedding",
            "rationale": f"Similarity score: {scores[best_label]:.1%}",
            "scores": {k: round(v*100, 1) for k, v in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:10]},
        }
    
    # Check memory for similar emails
    logger.info("No strong match found (threshold=%.2f), checking memory for similar emails", threshold)
    similar_ids = [mid for mid, _ in memory.similar(msg.get("subject"), msg.get("from"), msg.get("snippet"), k=5)]
    similar_examples = memory.get_messages_by_ids(similar_ids)
    
    def majority_label_from_similar(similar_examples: List[Dict]) -> Optional[str]:
        if not similar_examples:
            return None
        counts: Dict[str, int] = {}
        for ex in similar_examples:
            lbl = ex.get("applied_label")
            if lbl:
                counts[lbl] = counts.get(lbl, 0) + 1
        if not counts:
            return None
        best = max(counts.items(), key=lambda kv: kv[1])[0]
        return best
    
    majority_lbl = majority_label_from_similar(similar_examples)
    if majority_lbl and majority_lbl in label_names:
        logger.info("memory_similar_majority label=%s", majority_lbl)
        return {
            "message": msg,
            "suggested_label": majority_lbl,
            "label_id": id_by_name.get(majority_lbl),
            "source": "memory_similar",
            "rationale": f"Based on {len(similar_examples)} similar emails in memory",
            "scores": {k: round(v*100, 1) for k, v in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:10]} if scores else {},
        }
    
    # Ask LLM for suggestion
    prompt = build_prompt(
        subject=msg.get("subject"),
        sender=msg.get("from"),
        snippet=msg.get("snippet"),
        labels=label_names,
        similar_examples=similar_examples,
    )
    
    try:
        response = ollama_chat(model=model, messages=[{"role": "user", "content": prompt}])
        content = response.get("message", {}).get("content", "").strip()
        logger.info(f"LLM raw response for msg_id={msg.get('id')}: {content[:200]}...")
    except Exception as e:
        logger.error(f"LLM call failed for msg_id={msg.get('id')}: {e}")
        return None
    
    if not content:
        logger.error(f"LLM returned empty response for msg_id={msg.get('id')}")
        return None
    
    # Parse response
    import json as _json
    label_name = None
    rationale = ""
    
    try:
        if "```json" in content:
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
        elif "```" in content:
            content = content.replace("```", "").strip()
        
        parsed = _json.loads(content)
        if isinstance(parsed, dict) and parsed.get("label"):
            label_name = str(parsed.get("label")).strip()
            rationale = str(parsed.get("rationale", "")).strip()
    except Exception as parse_error:
        logger.warning(f"Failed to parse LLM JSON response: {parse_error}")
        for line in content.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                if key.lower().strip() in ["label", "\"label\""]:
                    label_name = val.strip().strip('"').strip(',')
                    break
    
    if not label_name:
        logger.error(f"Could not extract label from LLM response for msg_id={msg.get('id')}")
        return None
    
    logger.info("llm_suggestion label=%s rationale=%s", label_name, rationale)
    label_id = id_by_name.get(label_name)
    
    return {
        "message": msg,
        "suggested_label": label_name,
        "label_id": label_id,
        "source": "llm",
        "rationale": rationale,
        "similar_examples": similar_examples,
        "scores": {},
    }


def _classify_single_email_with_rejected(
    msg: Dict, 
    label_names: List[str], 
    id_by_name: Dict[str, str], 
    memory: MemoryStore, 
    rejected_suggestions: List[str],
    model: str = "gemma3:4b", 
    threshold: float = 0.35
) -> Optional[Dict]:
    """Classify a single email with context of previously rejected suggestions.
    
    This function is similar to _classify_single_email but takes into account
    previously rejected suggestions to avoid suggesting them again.
    """
    import logging
    import numpy as np
    logger = logging.getLogger("gmail_labeler")
    
    logger.info(f"Classifying email {msg.get('id')} with rejected suggestions: {rejected_suggestions}")
    
    # Define centroid_scoring function locally
    def centroid_scoring(msg: Dict, labels: List[str], threshold: float = 0.35):
        centroids = memory.get_label_centroids()
        if not centroids:
            return None, {}
            
        joined = " \n ".join([x for x in [msg.get("subject"), msg.get("from"), msg.get("snippet")] if x])
        q = memory.embed_text(joined)
        
        score_map: Dict[str, float] = {}
        for label in labels:
            c = centroids.get(label)
            if c is None:
                continue
            score = float(np.dot(q, c))
            score01 = (score + 1.0) / 2.0
            score_map[label] = score01
            
        best_label = None
        best_score = 0.0
        for label, score in score_map.items():
            if score > best_score and score >= threshold:
                best_label = label
                best_score = score
                
        return best_label, score_map
    
    # First try centroid scoring (excluding rejected suggestions)
    best_label, score_map = centroid_scoring(msg, label_names, threshold)
    
    if best_label and best_label not in rejected_suggestions:
        logger.info(f"Found good centroid match: {best_label}")
        return {
            "message": msg,
            "suggested_label": best_label,
            "label_id": id_by_name.get(best_label),
            "source": "centroid",
            "rationale": f"Strong match with existing label '{best_label}' based on similar emails",
            "scores": score_map
        }
    
    # If centroid didn't work or suggested a rejected label, try memory
    memory_label = memory.get_label_for_message(msg.get("id"))
    if memory_label and memory_label not in rejected_suggestions:
        logger.info(f"Found memory match: {memory_label}")
        return {
            "message": msg,
            "suggested_label": memory_label,
            "label_id": id_by_name.get(memory_label),
            "source": "memory",
            "rationale": f"Previously labeled as '{memory_label}' in local memory",
            "scores": {}
        }
    
    # Finally, use LLM but with context about rejected suggestions
    logger.info("No good matches found, using LLM with rejected suggestions context")
    
    # Build prompt with rejected suggestions context
    prompt = build_prompt_with_rejected_context(msg, label_names, rejected_suggestions)
    
    try:
        from ollama import chat as ollama_chat
        response = ollama_chat(model=model, messages=[{"role": "user", "content": prompt}])
        content = response.get("message", {}).get("content", "").strip()
        logger.info(f"LLM response with rejected context: {content[:200]}...")
        
        # Parse JSON response
        import json
        import re
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        
        result = json.loads(content)
        
        suggested_label = result.get("suggested_label", "").strip()
        
        # Make sure the suggested label is not in rejected suggestions
        if suggested_label in rejected_suggestions:
            logger.warning(f"LLM suggested rejected label '{suggested_label}', trying alternative approach")
            # Try to get a different suggestion by modifying the prompt
            alternative_prompt = build_prompt_with_rejected_context(msg, label_names, rejected_suggestions, force_different=True)
            response = ollama_chat(model=model, messages=[{"role": "user", "content": alternative_prompt}])
            content = response.get("message", {}).get("content", "").strip()
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            result = json.loads(content)
            suggested_label = result.get("suggested_label", "").strip()
        
        if suggested_label:
            logger.info(f"LLM suggested: {suggested_label}")
            return {
                "message": msg,
                "suggested_label": suggested_label,
                "label_id": id_by_name.get(suggested_label),
                "source": "llm",
                "rationale": result.get("rationale", "AI-generated suggestion based on email content"),
                "scores": {}
            }
        
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
    
    return None


def build_prompt_with_rejected_context(msg: Dict, labels: List[str], rejected_suggestions: List[str], force_different: bool = False) -> str:
    """Build prompt for LLM with context about rejected suggestions."""
    
    subject = msg.get("subject", "No Subject")
    sender = msg.get("from", "Unknown Sender")
    snippet = msg.get("snippet", "")
    
    rejected_context = ""
    if rejected_suggestions:
        rejected_context = f"\n\nIMPORTANT: The user has already rejected these suggestions for this email: {', '.join(rejected_suggestions)}. Do NOT suggest any of these labels again."
    
    force_different_context = ""
    if force_different:
        force_different_context = "\n\nCRITICAL: The user specifically wants a DIFFERENT suggestion. Be creative and suggest something completely different from the rejected labels."
    
    prompt = f"""You are an AI email labeling assistant. Analyze this email and suggest an appropriate label.

Email Details:
- Subject: {subject}
- From: {sender}
- Preview: {snippet}

Available Labels: {', '.join(labels) if labels else 'None (create new label)'}
{rejected_context}{force_different_context}

Instructions:
1. If the email matches an existing label well, suggest that label
2. If no existing label fits well, create a NEW meaningful label name
3. ALWAYS add an appropriate emoji to NEW labels for better visual identification
4. NEVER suggest labels that were already rejected for this email
5. Be specific and descriptive with new label names

Examples of good new labels:
- "Security Alerts 🚨"
- "Credit Card Payments 💳" 
- "Travel Bookings ✈️"
- "Work Projects 💼"

Respond with JSON format:
{{
    "suggested_label": "Label Name 🎯",
    "rationale": "Brief explanation of why this label fits"
}}"""

    return prompt


def run_labeling_flow(
    gmail: GmailClient,
    memory_store: MemoryStore,
    approvals: Optional[Dict[str, Dict[str, Any]]] = None,
    max_results: int = 5,
    model: Optional[str] = None,
    score_threshold: Optional[float] = None,
) -> Dict:
    """Run the labeling workflow with the given parameters.
    
    This function sets up global variables to avoid serialization issues with LangGraph.
    """
    # Log the function call for debugging
    logger.info(f"run_labeling_flow called with approvals={approvals}, max_results={max_results}")
    
    # Build the graph
    _, app = build_graph()
    
    # Store clients in global variables to avoid serialization issues
    global _gmail_client, _memory_store
    _gmail_client = gmail
    _memory_store = memory_store
    
    # Create a clean state with only serializable objects
    # We'll add the non-serializable objects directly in the nodes
    state: AgentState = AgentState(
        approvals=approvals or {},
        max_results=max_results,
    )
    
    # Add optional parameters if provided
    if model:
        state["model"] = model
    if score_threshold is not None:
        state["score_threshold"] = score_threshold
    
    # Add required config for checkpointer
    config = {"configurable": {"thread_id": "gmail_labeling_session"}}
    
    # If we have approvals but no suggestions, we're in apply-only mode
    if approvals and not state.get("suggestions"):
        # Create a minimal set of suggestions from the approvals
        suggestions = []
        for msg_id, decision in approvals.items():
            # Log each approval decision for debugging
            logger.info(f"Processing approval for msg_id={msg_id}, approved={decision.get('approved')}, label={decision.get('final_label')}")
            
            # Only include approved messages in suggestions
            if decision.get("approved"):
                logger.info(f"Creating suggestion from approval for msg_id={msg_id}")
                suggestions.append({
                    "message": {"id": msg_id},
                    "suggested_label": decision.get("final_label", "Uncategorized")
                })
        
        # Set suggestions in state
        state["suggestions"] = suggestions
        logger.info(f"Created {len(suggestions)} suggestions from {len(approvals)} total approvals")
        
        # If no approved messages, log a warning
        if not suggestions:
            logger.warning("No approved messages found in approvals. Nothing will be applied.")
    
    # Run the graph
    try:
        # Skip to apply_and_update node directly if we're just applying labels
        if approvals and len(state.get("suggestions", [])) > 0:
            logger.info("Skipping to apply_and_update node directly")
            # Apply labels directly
            node_apply_and_update(state)
            result = state
        else:
            # Run the full graph
            result = app.invoke(state, config=config)
            
        logger.info(f"Graph execution completed with result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in graph execution: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


def _classify_single_email_with_context(
    msg: Dict, 
    user_message: str,
    gmail_client,
    memory_store,
    rejected_suggestions: List[str] = [],
    model: str = "gemma3:4b",
    threshold: float = 0.3
) -> Optional[Dict]:
    """Classify a single email with user context message."""
    import numpy as np
    from ollama import chat as ollama_chat
    
    logger.info(f"Classifying email {msg.get('id')} with user context: {user_message}")
    
    # Get labels and memory
    labels_api = gmail_client.list_labels()
    label_names = [lb["name"] for lb in labels_api]
    id_by_name = {lb["name"]: lb["id"] for lb in labels_api}
    memory = memory_store
    
    # Filter out system labels
    system_labels = {'INBOX', 'SENT', 'DRAFT', 'SPAM', 'TRASH', 'UNREAD', 
                     'CATEGORY_PERSONAL', 'CATEGORY_SOCIAL', 'CATEGORY_PROMOTIONS', 
                     'CATEGORY_UPDATES', 'CATEGORY_FORUMS', 'STARRED', 'IMPORTANT'}
    label_names = [label for label in label_names if label not in system_labels]
    
    if not label_names:
        logger.warning("No custom labels found")
        return None
    
    # Build prompt with user context
    prompt = build_prompt_with_user_context(msg, label_names, user_message, rejected_suggestions)
    
    try:
        # Call LLM with user context
        logger.info(f"Calling LLM with user context for email {msg.get('id')}")
        response = ollama_chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1}
        )
        
        llm_response = response.get('message', {}).get('content', '').strip()
        logger.info(f"LLM response with context: {llm_response}")
        
        # Parse LLM response
        suggestion = parse_llm_response(llm_response, label_names, id_by_name)
        
        if suggestion:
            suggestion["source"] = "llm_with_context"
            suggestion["rationale"] = f"LLM suggestion with user context: {user_message}"
            logger.info(f"Context-based suggestion for {msg.get('id')}: {suggestion.get('suggested_label')}")
            return suggestion
        
        logger.warning(f"Failed to parse LLM response with context for {msg.get('id')}")
        return None
        
    except Exception as e:
        logger.error(f"Error calling LLM with context for {msg.get('id')}: {e}")
        return None


def build_prompt_with_user_context(msg: Dict, label_names: List[str], user_message: str, rejected_suggestions: List[str]) -> str:
    """Build prompt for LLM with user context message."""
    
    # Get email content
    subject = msg.get('subject', 'No subject')
    sender = msg.get('from', 'Unknown sender')
    snippet = msg.get('snippet', 'No preview available')
    
    # Log user context for debugging
    logger.info(f"🔍 Building prompt with user context for email {msg.get('id')}")
    logger.info(f"   📝 User message: '{user_message}'")
    logger.info(f"   🚫 Rejected suggestions: {rejected_suggestions}")
    
    # Build rejected context
    rejected_context = ""
    if rejected_suggestions:
        rejected_context = f"\n\nIMPORTANT: The user has previously rejected these label suggestions for this email: {', '.join(rejected_suggestions)}. Do NOT suggest any of these labels again."
    
    prompt = f"""You are an AI assistant that helps categorize emails by suggesting appropriate labels.

EMAIL TO CATEGORIZE:
Subject: {subject}
From: {sender}
Preview: {snippet}

USER CONTEXT: {user_message}

AVAILABLE LABELS: {', '.join(label_names)}

TASK: Based on the email content AND the user's context message, suggest the most appropriate label.

RULES:
1. Consider the user's context message carefully - it provides important information about how this email should be categorized
2. If the email fits an existing label well, suggest that label
3. If no existing label fits well, create a new meaningful label name (not "Uncategorized")
4. New labels should be descriptive and include an appropriate emoji
5. Respond with ONLY a JSON object in this format: {{"suggested_label": "Label Name 🎯", "reasoning": "Brief explanation"}}
{rejected_context}

RESPOND WITH JSON ONLY:"""

    # Log the complete prompt for debugging
    logger.info(f"📋 Complete prompt sent to LLM:")
    logger.info(f"   {prompt[:200]}...")  # Log first 200 chars
    
    return prompt


def parse_llm_response(content: str, label_names: List[str], id_by_name: Dict[str, str]) -> Optional[Dict]:
    """Parse LLM response and extract suggestion."""
    import json
    import re
    
    try:
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        elif "```" in content:
            content = content.replace("```", "").strip()
        
        result = json.loads(content)
        
        suggested_label = result.get("suggested_label", "").strip()
        
        if suggested_label:
            logger.info(f"LLM suggested: {suggested_label}")
            return {
                "suggested_label": suggested_label,
                "label_id": id_by_name.get(suggested_label),
                "source": "llm",
                "rationale": result.get("reasoning", "AI-generated suggestion based on email content"),
            }
        
        return None
        
    except Exception as e:
        logger.warning(f"Failed to parse LLM response: {e}")
        logger.debug(f"Raw content was: {content}")
        return None


