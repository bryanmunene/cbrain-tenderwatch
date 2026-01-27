# Autonomous Scanning & Notifications Guide

## Overview

TenderWatch now supports **autonomous operation** with automatic scanning and real-time notifications! The system can run in the background, continuously monitoring tender sources and alerting you to new opportunities.

## Features

### 🤖 Autonomous Scanning
- **Background Scheduler**: Automatically scans tender sources at configurable intervals
- **Persistent Operation**: Runs continuously while the app is running
- **Flexible Scheduling**: Set scan intervals from 5 minutes to 24 hours
- **Smart Detection**: Only notifies about new tenders (not duplicates)

### 🔔 Notifications
- **Desktop Notifications**: Instant popup alerts on Windows, macOS, and Linux
- **Email Alerts**: Detailed HTML emails with tender information
- **Score-Based Filtering**: Only get notified about high-quality matches
- **Configurable Thresholds**: Control notification frequency

## Quick Start

### 1. Enable Autonomous Scanning

1. Navigate to **Settings** in the top menu
2. Enable **"Automatic Scanning"**
3. Set your desired **Scan Interval** (e.g., 60 minutes)
4. Click **Save Settings**

The scheduler will now automatically scan all active sources at the configured interval!

### 2. Configure Notifications

#### Desktop Notifications (Easiest)
1. In Settings, enable **"Desktop Notifications"**
2. Set your **Minimum Score to Notify** (recommended: 50-70)
3. Click **"Test Desktop Notification"** to verify it works
4. Save settings

#### Email Notifications
1. In Settings, enable **"Email Notifications"**
2. Enter recipient email addresses (comma-separated)
3. Configure SMTP settings:
   - **For Gmail**:
     - SMTP Server: `smtp.gmail.com`
     - Port: `587`
     - Username: Your Gmail address
     - Password: Use an [App Password](https://support.google.com/accounts/answer/185833)
   - **For Outlook**:
     - SMTP Server: `smtp-mail.outlook.com`
     - Port: `587`
     - Username: Your Outlook email
     - Password: Your email password
4. Save settings

## Configuration Details

### Scan Interval
- **Minimum**: 5 minutes
- **Maximum**: 1440 minutes (24 hours)
- **Recommended**: 30-60 minutes for most use cases
- **Note**: Too frequent scanning may trigger rate limiting on some tender platforms

### Notification Threshold
- **Range**: 0-100
- **Recommended Settings**:
  - `30-40`: Get all potential matches (high volume)
  - `50-60`: Balanced approach (medium volume)
  - `70+`: Only high-quality matches (low volume)

### Email Configuration

#### Gmail Setup
1. Enable 2-factor authentication on your Google account
2. Generate an App Password:
   - Go to Google Account → Security
   - Select "2-Step Verification"
   - At the bottom, select "App passwords"
   - Generate a password for "Mail"
3. Use this app password in TenderWatch settings

#### Other Email Providers
Most SMTP providers work similarly. Common settings:
- **Yahoo**: smtp.mail.yahoo.com:587
- **Office 365**: smtp.office365.com:587
- **Custom SMTP**: Check your provider's documentation

## How It Works

### Automatic Scanning Process
1. **Scheduler starts** when app launches (if enabled)
2. **Every X minutes**, the system:
   - Scans all active tender sources
   - Scores and categorizes new tenders
   - Identifies tenders above notification threshold
3. **Notifications sent** for qualifying tenders
4. **Tenders marked** as notified to prevent duplicates

### Notification Logic
```
New Tender Found
    ↓
Score >= Threshold?
    ↓
Not Previously Notified?
    ↓
Send Notifications:
  - Desktop (if enabled)
  - Email (if enabled)
    ↓
Mark as Notified
```

## Usage Examples

### Example 1: Daily Morning Digest
- **Scan Interval**: 1440 minutes (24 hours)
- **Schedule**: Run app at startup each morning
- **Notifications**: Email only
- **Threshold**: 60
- **Result**: One comprehensive email each morning with yesterday's top tenders

### Example 2: Real-Time Monitoring
- **Scan Interval**: 15 minutes
- **Notifications**: Desktop + Email
- **Threshold**: 70
- **Result**: Instant alerts for high-priority tenders throughout the day

### Example 3: Passive Monitoring
- **Scan Interval**: 120 minutes (2 hours)
- **Notifications**: Desktop only
- **Threshold**: 50
- **Result**: Periodic desktop notifications without email clutter

## Troubleshooting

### Desktop Notifications Not Appearing
- **Windows**: Check Windows notification settings (Settings → System → Notifications)
- **macOS**: Grant notification permissions in System Preferences
- **Linux**: Ensure `notify-send` is installed

### Email Notifications Failing
- ✓ Check SMTP credentials are correct
- ✓ Verify app password (not regular password for Gmail)
- ✓ Test with "Test Email" button
- ✓ Check spam folder for initial emails
- ✓ Ensure firewall allows SMTP port (587)

### Scheduler Not Running
- ✓ Verify "Automatic Scanning" is enabled in Settings
- ✓ Check app logs for error messages
- ✓ Restart the application
- ✓ Ensure at least one source is active

### Too Many/Few Notifications
- **Too Many**: Increase the minimum score threshold
- **Too Few**: Decrease the threshold or check if sources are active
- **Wrong Times**: Adjust scan interval

## Best Practices

### 1. Start Conservative
- Begin with a 60-minute interval
- Set threshold to 60
- Enable desktop notifications only
- Adjust based on results

### 2. Monitor Performance
- Check the Settings page for "Next scan" time
- Review notification frequency after 24 hours
- Adjust threshold if needed

### 3. Source Management
- Keep only relevant sources active
- Use source favorites to prioritize certain platforms
- Disable low-quality sources

### 4. Email Management
- Use a dedicated email for TenderWatch alerts
- Set up email filters/folders
- Consider digest mode (longer intervals) to reduce email volume

## Security Notes

### Password Storage
- SMTP passwords are stored in the database
- Consider using environment variables for production
- Use app-specific passwords when possible

### Rate Limiting
- Respect tender platform terms of service
- Don't set intervals too low (< 15 minutes)
- Monitor for access restrictions

## Advanced Configuration

### Running as a Service (Windows)
To run TenderWatch as a background Windows service:

```powershell
# Using NSSM (Non-Sucking Service Manager)
nssm install TenderWatch "C:\path\to\venv\Scripts\python.exe" "C:\path\to\run.py"
nssm start TenderWatch
```

### Environment Variables
For enhanced security, use environment variables:

```python
# In __init__.py
import os
app.config["SMTP_PASSWORD"] = os.getenv("TENDERWATCH_SMTP_PASSWORD")
```

### Multiple Recipients
Separate email addresses with commas:
```
user1@company.com, user2@company.com, team@company.com
```

## API Integration

### Check Scheduler Status
```python
GET /settings
# Returns scheduler status in page
```

### Manual Trigger
```python
POST /scan
# Manually trigger a scan and notification check
```

## Future Enhancements

Potential features for future development:
- Slack/Teams webhook integration
- SMS notifications via Twilio
- Mobile app push notifications
- Advanced filtering rules
- Machine learning for better scoring
- Tender deadline reminders

## Support

For issues or questions:
1. Check this guide first
2. Review app logs for error messages
3. Test with "Test Notification" button
4. Verify all settings are saved correctly

## Summary

TenderWatch's autonomous features transform it from a manual scanning tool into a comprehensive tender monitoring system. With proper configuration, you'll never miss an important opportunity!

**Key Takeaways:**
- ✅ Enable automatic scanning for hands-free operation
- ✅ Configure notifications to stay informed
- ✅ Adjust thresholds to control notification volume
- ✅ Monitor and tune settings based on results

Happy tendering! 🎯
