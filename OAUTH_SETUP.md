# 🔐 Google OAuth Setup Guide

## Step-by-Step Guide to Get Your OAuth Credentials

### 📋 Overview

This app needs permission to read and label your Gmail. Google provides this through OAuth credentials. Don't worry - **it's free and takes just 5 minutes!**

---

## 🎯 Step 1: Go to Google Cloud Console

**Open this link**: [Google Cloud Console](https://console.cloud.google.com/)

- Sign in with your Google account
- You'll see the main dashboard

---

## 🎯 Step 2: Create a New Project

1. Click **"Select a project"** at the top
2. Click **"New Project"** in the dialog
3. **Project name**: `Gmail Labeler` (or any name you like)
4. Click **"Create"**
5. Wait a few seconds for the project to be created
6. Select your new project from the dropdown

---

## 🎯 Step 3: Enable Gmail API

1. In the left sidebar, go to **"APIs & Services"** → **"Library"**
2. Search for **"Gmail API"**
3. Click on **"Gmail API"**
4. Click the **"Enable"** button
5. Wait for it to enable (should be quick)

---

## 🎯 Step 4: Configure OAuth Consent Screen

Before creating credentials, you need to configure the consent screen:

1. Go to **"APIs & Services"** → **"OAuth consent screen"**

2. **User Type**: Select **"External"** → Click **"Create"**

3. **Fill in required fields**:
   - **App name**: `Gmail Labeler`
   - **User support email**: Your email address
   - **Developer contact information**: Your email address

4. Click **"Save and Continue"**

5. **Scopes page**: Click **"Save and Continue"** (no changes needed)

6. **Test users page**: Click **"Save and Continue"** (no changes needed)

7. **Summary page**: Click **"Back to Dashboard"**

---

## 🎯 Step 5: Create OAuth Credentials

Now let's create the actual credentials:

1. Go to **"APIs & Services"** → **"Credentials"**

2. Click **"Create Credentials"** → **"OAuth client ID"**

3. **Application type**: Select **"Desktop app"**
   - ⚠️ **IMPORTANT**: Must be "Desktop app", not "Web application"!

4. **Name**: `Gmail Labeler Desktop` (or any name)

5. Click **"Create"**

6. A popup will show your credentials:
   - **Client ID**: (long string)
   - **Client secret**: (another string)

7. Click the **"Download JSON"** button (⬇️ icon)

---

## 🎯 Step 6: Save the Credentials File

1. The downloaded file will be named something like:
   ```
   client_secret_123456789.apps.googleusercontent.com.json
   ```

2. **Rename it to**: `client_secret.json`

3. **Move it to**: `backend/credentials/` folder in your project:
   ```
   llm-gmail-labeler/
   └── backend/
       └── credentials/
           └── client_secret.json  ← Put it here!
   ```

---

## ✅ Verification

Your `client_secret.json` should look like this:

```json
{
  "installed": {
    "client_id": "123456789-abcdefg.apps.googleusercontent.com",
    "project_id": "gmail-labeler-123456",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "GOCSPX-xxxxxxxxxxxxxxxxxxxxx",
    "redirect_uris": ["http://localhost"]
  }
}
```

**Key things to check**:
- ✅ File is named `client_secret.json`
- ✅ It has an `"installed"` key (NOT `"web"`)
- ✅ It's in `backend/credentials/` folder

---

## 🎉 You're Done!

Now you can run the app:

```bash
npm run start:dev
```

When you first access the app, it will:
1. Open a browser window automatically
2. Ask you to select your Google account
3. Show permissions it needs (read/modify Gmail)
4. Save the authorization for future use

**That's it!** You only need to do this once.

---

## 🐛 Troubleshooting

### "redirect_uri_mismatch" Error

**Problem**: You selected "Web application" instead of "Desktop app"

**Solution**:
1. Go back to Google Cloud Console
2. Delete the old OAuth client
3. Create a new one
4. Select **"Desktop app"** this time
5. Download and save the new JSON

### "Client secret not found"

**Problem**: File is in the wrong location

**Solution**:
```bash
# Check if file exists
ls -la backend/credentials/client_secret.json

# If not, make sure:
# 1. File is named exactly "client_secret.json" (not "client_secret (1).json")
# 2. It's in the "backend/credentials/" folder
# 3. You're running commands from the project root
```

### "Access blocked: This app hasn't been verified"

**Problem**: Google wants to review the app (only happens if you try to publish)

**Solution**: Since you're using it personally:
1. Click "Advanced"
2. Click "Go to Gmail Labeler (unsafe)"
3. Continue with authorization

This is normal for personal projects that haven't gone through Google's review process.

---

## 🔒 Security Notes

- **Your credentials are private**: Never share `client_secret.json` publicly
- **Local only**: All authentication happens on your machine
- **Revoke anytime**: You can revoke access in Google Account settings
- **Safe to delete**: You can delete the OAuth client anytime from Google Cloud Console

---

## 📱 Alternative: Using Existing Project

If you already have a Google Cloud project:

1. Select your existing project
2. Enable Gmail API
3. Create OAuth client ID (Desktop app)
4. Download and save credentials
5. Done!

---

## 🎓 Understanding OAuth

**What is OAuth?**
- A secure way to give apps limited access to your Google account
- You control what permissions to grant
- You can revoke access anytime
- No need to share your password

**What permissions does this app need?**
- Read your email messages
- Add/modify labels
- **Does NOT:**
  - Delete emails
  - Send emails
  - Access other Google services
  - Share data with anyone

---

## 📚 Additional Resources

- [Google Cloud Console](https://console.cloud.google.com/)
- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [OAuth 2.0 Overview](https://developers.google.com/identity/protocols/oauth2)

---

**Questions?** Check the troubleshooting section in the main README.md!

