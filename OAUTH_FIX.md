# Fix: OAuth Access Denied Error

## Problem
You're seeing: "Access blocked: Private has not completed the Google verification process"

This happens because your OAuth app is in "Testing" mode and you haven't added yourself as a test user.

## Quick Fix (5 minutes)

### Step 1: Add Yourself as a Test User

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Navigate to **APIs & Services** > **OAuth consent screen**
4. Scroll down to the **Test users** section
5. Click **+ ADD USERS**
6. Enter your Google account email address (the one you use for YouTube)
7. Click **ADD**
8. The page should refresh and show your email in the test users list

### Step 2: Try Again

Run the script again:
```bash
source venv/bin/activate
python3 run.py
```

The OAuth flow should now work!

## Alternative: Publish Your App (Not Recommended for Personal Use)

If you want to avoid the test user limitation, you can publish your app, but this requires:
- App verification by Google (can take days/weeks)
- Privacy policy URL
- Terms of service URL
- More complex setup

**For personal use, just add yourself as a test user - it's much simpler!**

## Still Having Issues?

- Make sure you're using the **exact same email** that you use for YouTube
- Check that you're logged into the correct Google account in your browser
- Try clearing your browser cache and cookies for Google
- Make sure the OAuth consent screen is set to "Testing" mode (not "In production")

