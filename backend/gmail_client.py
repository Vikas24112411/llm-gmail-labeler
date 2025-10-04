import os
import json
import base64
from typing import List, Dict, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


# Gmail scopes needed: read metadata, modify labels, and basic read
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
]


class GmailClient:
    """Thin wrapper around Gmail API for auth, labels, and reading/applying labels."""

    def __init__(
        self,
        credentials_dir: str,
        token_filename: str = "token.json",
        client_secret_filename: str = "client_secret.json",
        user_id: str = "me",
    ) -> None:
        self.credentials_dir = credentials_dir
        self.token_path = os.path.join(credentials_dir, token_filename)
        self.client_secret_path = os.path.join(credentials_dir, client_secret_filename)
        self.user_id = user_id
        self.service = None

    def authenticate(self) -> None:
        """Authenticate with Gmail API, handling token refresh and expiration."""
        import logging
        logger = logging.getLogger("gmail_labeler")
        
        os.makedirs(self.credentials_dir, exist_ok=True)
        creds: Optional[Credentials] = None
        
        # Check for existing token and try to use it
        if os.path.exists(self.token_path):
            try:
                logger.info("Found existing token, attempting to load")
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                logger.error(f"Error loading credentials from token file: {e}")
                creds = None
                # Token might be corrupted, remove it
                os.remove(self.token_path)
        
        # If credentials need refresh or don't exist
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired token")
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Token refresh failed: {e}")
                    creds = None
                    # If refresh fails, remove the token and start fresh
                    if os.path.exists(self.token_path):
                        os.remove(self.token_path)
            
            # If we still don't have valid credentials, start the OAuth flow
            if not creds or not creds.valid:
                logger.info("Starting new OAuth flow")
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_path, SCOPES)
                
                # Check if this is a Web client with specific redirect URI
                with open(self.client_secret_path, 'r') as f:
                    client_config = json.load(f)
                
                if 'web' in client_config and 'redirect_uris' in client_config['web']:
                    # Web client with specific redirect path - must use manual flow
                    redirect_uri = client_config['web']['redirect_uris'][0]
                    
                    # Get authorization URL
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    
                    print(f"\nPlease visit this URL to authorize: {auth_url}")
                    print(f"After authorization, you'll be redirected to: {redirect_uri}")
                    print("Copy the 'code' parameter from the redirect URL and paste it below:")
                    
                    # Get authorization code from user
                    import sys
                    if hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
                        code = input("Enter authorization code: ").strip()
                    else:
                        raise RuntimeError("Manual OAuth flow requires interactive terminal. Use Desktop OAuth client instead.")
                    
                    # Exchange code for credentials
                    creds = flow.fetch_token(code=code)
                else:
                    # Desktop client - use preferred port with fallback
                    preferred_port = int(os.environ.get("OAUTH_REDIRECT_PORT", "8765"))
                    try:
                        creds = flow.run_local_server(port=preferred_port)
                    except OSError as e:
                        if "Address already in use" in str(e) or getattr(e, "errno", None) == 48:
                            creds = flow.run_local_server(port=0)
                        else:
                            raise
                
                # Save the credentials
                with open(self.token_path, "w") as token:
                    token.write(creds.to_json())
                logger.info("New OAuth credentials saved")

        # Build the service with the credentials
        try:
            # Simply build the service with credentials
            # Google's libraries will handle the http client internally
            self.service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail API service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to build Gmail service: {e}")
            raise

    def list_labels(self, only_custom: bool = True) -> List[Dict]:
        """Get labels from Gmail account with error handling.
        
        Args:
            only_custom: If True, only return user-created custom labels (not system labels).
                        If False, return all labels including INBOX, CATEGORY_*, etc.
        """
        if self.service is None:
            raise RuntimeError("Gmail not authenticated. Call authenticate() first.")
        
        # System labels to exclude when only_custom=True
        SYSTEM_LABELS = {
            'INBOX', 'UNREAD', 'STARRED', 'SENT', 'DRAFT', 'SPAM', 'TRASH',
            'IMPORTANT', 'CHAT', 'CATEGORY_PERSONAL', 'CATEGORY_SOCIAL',
            'CATEGORY_PROMOTIONS', 'CATEGORY_UPDATES', 'CATEGORY_FORUMS'
        }
        
        try:
            results = self.service.users().labels().list(userId=self.user_id).execute()
            all_labels = results.get("labels", [])
            
            if only_custom:
                # Filter to only user-created labels (exclude system labels)
                custom_labels = [
                    lb for lb in all_labels 
                    if lb.get("type") == "user" and lb.get("name") not in SYSTEM_LABELS
                ]
                import logging
                logger = logging.getLogger("gmail_labeler")
                logger.info(f"Found {len(custom_labels)} custom labels out of {len(all_labels)} total labels")
                return custom_labels
            
            return all_labels
            
        except Exception as e:
            import logging
            logger = logging.getLogger("gmail_labeler")
            logger.error(f"Error listing labels: {e}")
            
            # If we get a 400 error, token might be invalid - try to force reauthentication
            if "HttpError 400" in str(e) or "failedPrecondition" in str(e):
                logger.warning("Token may be invalid, removing and forcing reauthentication")
                if os.path.exists(self.token_path):
                    os.remove(self.token_path)
                    self.service = None
                    # Re-authenticate and try again
                    self.authenticate()
                    results = self.service.users().labels().list(userId=self.user_id).execute()
                    all_labels = results.get("labels", [])
                    
                    if only_custom:
                        return [
                            lb for lb in all_labels 
                            if lb.get("type") == "user" and lb.get("name") not in SYSTEM_LABELS
                        ]
                    return all_labels
            
            # Return empty list as fallback
            return []

    def get_unread_messages(self, max_results: int = 10, exclude_processed: set = None) -> List[Dict]:
        """Get unread messages with improved error handling, retry logic, and comprehensive logging.
        
        Args:
            max_results: Maximum number of messages to fetch
            exclude_processed: Set of email IDs to exclude (ignored - feature removed)
        """
        if self.service is None:
            raise RuntimeError("Gmail not authenticated. Call authenticate() first.")
        
        import logging
        import time
        logger = logging.getLogger("gmail_labeler")
        
        # Start timing
        start_time = time.time()
        
        # Make sure max_results is at least 1 (Gmail API requires positive value)
        max_results = max(1, max_results)
        
        logger.info("=" * 60)
        logger.info("📧 GMAIL API EMAIL FETCH STARTED")
        logger.info(f"📊 Request Parameters:")
        logger.info(f"   - Max Results: {max_results}")
        logger.info(f"   - User ID: {self.user_id}")
        logger.info(f"   - Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        try:
            # Step 1: Get message IDs
            step_start = time.time()
            query = "is:unread"
            logger.info(f"🔍 Step 1: Fetching message IDs with query: '{query}'")
            
            response = self.service.users().messages().list(
                userId=self.user_id, q=query, maxResults=max_results
            ).execute()
            
            step_time = time.time() - step_start
            messages = response.get("messages", [])
            
            logger.info(f"✅ Step 1 Complete: Found {len(messages)} message IDs in {step_time:.3f}s")
            
            if not messages:
                total_time = time.time() - start_time
                logger.info(f"📭 No unread messages found. Total time: {total_time:.3f}s")
                logger.info("=" * 60)
                return []
            
            # Step 2: Fetch detailed message data
            logger.info(f"📥 Step 2: Fetching detailed data for {len(messages)} messages")
            step_start = time.time()
            
            detailed: List[Dict] = []
            successful_fetches = 0
            failed_fetches = 0
            
            for i, m in enumerate(messages, 1):
                try:
                    msg_start = time.time()
                    msg = self.service.users().messages().get(
                        userId=self.user_id, id=m["id"], format="metadata", metadataHeaders=[
                            "From",
                            "To",
                            "Subject",
                            "Date",
                        ]
                    ).execute()
                    msg_time = time.time() - msg_start
                    
                    detailed.append(self._to_slim_message(msg))
                    successful_fetches += 1
                    
                    # Log every 5th message or if it takes longer than 0.5s
                    if i % 5 == 0 or msg_time > 0.5:
                        logger.info(f"   📨 Message {i}/{len(messages)}: {m['id']} ({msg_time:.3f}s)")
                        
                except Exception as e:
                    failed_fetches += 1
                    logger.error(f"❌ Error fetching message {m['id']}: {e}")
                    # Add minimal message info so we don't lose track of it
                    detailed.append({"id": m["id"], "threadId": m.get("threadId")})
            
            step_time = time.time() - step_start
            total_time = time.time() - start_time
            
            # Final summary
            logger.info("=" * 60)
            logger.info("📊 GMAIL API FETCH SUMMARY")
            logger.info(f"   ✅ Successful fetches: {successful_fetches}")
            logger.info(f"   ❌ Failed fetches: {failed_fetches}")
            logger.info(f"   📧 Total messages returned: {len(detailed)}")
            logger.info(f"   ⏱️  Step 1 (List): {step_time:.3f}s")
            logger.info(f"   ⏱️  Step 2 (Details): {step_time:.3f}s")
            logger.info(f"   ⏱️  Total time: {total_time:.3f}s")
            logger.info(f"   📈 Avg time per message: {total_time/len(messages):.3f}s")
            logger.info(f"   🚀 Messages per second: {len(messages)/total_time:.2f}")
            logger.info("=" * 60)
            
            return detailed
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"❌ GMAIL API FETCH FAILED after {total_time:.3f}s")
            logger.error(f"   Error: {e}")
            
            # Only retry on actual auth errors (401, 403), not validation errors (400)
            error_str = str(e)
            if ("HttpError 401" in error_str or "HttpError 403" in error_str or 
                "failedPrecondition" in error_str or "SSL" in error_str):
                logger.warning("🔄 Authentication issue detected, removing token and forcing reauthentication")
                if os.path.exists(self.token_path):
                    os.remove(self.token_path)
                    self.service = None
                    # Re-authenticate and try again
                    logger.info("🔄 Re-authenticating and retrying...")
                    self.authenticate()
                    return self.get_unread_messages(max_results, exclude_processed)
            
            # Return empty list as fallback
            logger.info("📭 Returning empty list due to error")
            logger.info("=" * 60)
            return []

    def get_message_by_id(self, msg_id: str) -> Dict:
        """Get a specific message by ID with error handling."""
        if self.service is None:
            raise RuntimeError("Gmail not authenticated. Call authenticate() first.")
            
        import logging
        logger = logging.getLogger("gmail_labeler")
        
        try:
            logger.info(f"🔍 Fetching message details for ID: {msg_id}")
            import time
            start_time = time.time()
            
            msg = self.service.users().messages().get(
                userId=self.user_id, id=msg_id, format="full"
            ).execute()
            
            fetch_time = time.time() - start_time
            logger.info(f"✅ Message {msg_id} fetched successfully in {fetch_time:.3f}s")
            
            return self._to_slim_message(msg)
        except Exception as e:
            fetch_time = time.time() - start_time if 'start_time' in locals() else 0
            logger.error(f"❌ Failed to fetch message {msg_id} after {fetch_time:.3f}s: {e}")
            
            # Only retry on actual auth errors (401, 403), not validation errors (400)
            error_str = str(e)
            if ("HttpError 401" in error_str or "HttpError 403" in error_str or 
                "failedPrecondition" in error_str or "SSL" in error_str):
                logger.warning("🔄 Authentication issue detected, removing token and forcing reauthentication")
                if os.path.exists(self.token_path):
                    os.remove(self.token_path)
                    self.service = None
                    # Re-authenticate and try again
                    logger.info("🔄 Re-authenticating and retrying...")
                    self.authenticate()
                    return self.get_message_by_id(msg_id)
                    
            # Return minimal info as fallback
            return {"id": msg_id}

    def apply_label(self, msg_id: str, label_id: str) -> bool:
        """Apply a label to a message with error handling. Returns True if successful."""
        if self.service is None:
            raise RuntimeError("Gmail not authenticated. Call authenticate() first.")
            
        import logging
        logger = logging.getLogger("gmail_labeler")
        
        try:
            logger.info(f"Applying label {label_id} to message {msg_id}")
            body = {"addLabelIds": [label_id], "removeLabelIds": []}
            self.service.users().messages().modify(userId=self.user_id, id=msg_id, body=body).execute()
            logger.info(f"Successfully applied label {label_id} to message {msg_id}")
            return True
        except Exception as e:
            logger.error(f"Error applying label {label_id} to message {msg_id}: {e}")
            
            # Only retry on actual auth errors (401, 403), not validation errors (400)
            error_str = str(e)
            if ("HttpError 401" in error_str or "HttpError 403" in error_str or 
                "failedPrecondition" in error_str or "SSL" in error_str):
                logger.warning("Authentication issue detected, removing token and forcing reauthentication")
                if os.path.exists(self.token_path):
                    os.remove(self.token_path)
                    self.service = None
                    # Re-authenticate and try again
                    self.authenticate()
                    return self.apply_label(msg_id, label_id)
            
            # For validation errors (400), don't retry - just fail
            return False

    def ensure_label(self, label_name: str) -> Tuple[str, Dict]:
        """Return (label_id, label_obj). Create label if it doesn't exist. With error handling."""
        if self.service is None:
            raise RuntimeError("Gmail not authenticated. Call authenticate() first.")
            
        import logging
        logger = logging.getLogger("gmail_labeler")
        
        try:
            # First check if label already exists
            existing = self.list_labels()
            for lb in existing:
                if lb.get("name") == label_name:
                    logger.info(f"Label '{label_name}' already exists with ID {lb['id']}")
                    return lb["id"], lb
                    
            # Create new label if it doesn't exist
            logger.info(f"Creating new label: '{label_name}'")
            label_body = {
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            }
            created = self.service.users().labels().create(userId=self.user_id, body=label_body).execute()
            logger.info(f"Successfully created label '{label_name}' with ID {created['id']}")
            return created["id"], created
            
        except Exception as e:
            logger.error(f"Error ensuring label '{label_name}': {e}")
            
            # If we get a 400 error, token might be invalid - try to force reauthentication
            if "HttpError 400" in str(e) or "failedPrecondition" in str(e) or "SSL" in str(e):
                logger.warning("Connection issue or token may be invalid, removing and forcing reauthentication")
                if os.path.exists(self.token_path):
                    os.remove(self.token_path)
                    self.service = None
                    # Re-authenticate and try again
                    self.authenticate()
                    return self.ensure_label(label_name)
            
            # Return a fallback label ID and empty dict
            # This is not ideal but prevents crashes
            fallback_id = "FALLBACK_" + label_name.replace(" ", "_")
            logger.warning(f"Using fallback label ID: {fallback_id}")
            return fallback_id, {"id": fallback_id, "name": label_name}

    @staticmethod
    def _to_slim_message(msg: Dict) -> Dict:
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        snippet = msg.get("snippet", "")
        label_ids = msg.get("labelIds", [])
        return {
            "id": msg.get("id"),
            "threadId": msg.get("threadId"),
            "from": headers.get("From"),
            "to": headers.get("To"),
            "subject": headers.get("Subject"),
            "date": headers.get("Date"),
            "snippet": snippet,
            "labelIds": label_ids,
        }


