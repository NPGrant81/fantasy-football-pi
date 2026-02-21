# backend/utils/email_sender.py
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_invite_email(to_email, username, temp_password, league_id=None):
    """
    Sends an invitation email with temporary credentials.
    """
    # 1. Load Credentials (you can add these to your .env file later)
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = os.getenv("MAIL_USERNAME")
    sender_password = os.getenv("MAIL_PASSWORD")

    # 2. Construct the Email
    subject = "You've been drafted! 🏈"
    body = f"""
    <div style="font-family: Arial, sans-serif; color: #333;">
        <h1 style="color: #d35400;">Welcome to the League, {username}!</h1>
        <p>The Commissioner has created your owner profile.</p>
        
        <div style="background: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p><strong>Your Temporary Credentials:</strong></p>
            <ul>
                <li>Username: <b>{username}</b></li>
                <li>Password: <b>{temp_password}</b></li>
                <li>League ID: <b>{league_id if league_id is not None else 'Ask commissioner'}</b></li>
            </ul>
        </div>
        
        <p>Please log in and change your password immediately.</p>
        <p><a href="http://localhost:5173/login" style="background: #27ae60; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Login Now</a></p>
    </div>
    """

    # 3. Development Mode Catch (If no email is configured in .env)
    if not sender_email or not sender_password:
        print("\n" + "="*50)
        print(f"📧 [SIMULATION] Sending Email to: {to_email}")
        print(f"👤 User: {username}")
        print(f"🔑 Password: {temp_password}")
        print(f"🏟️ League ID: {league_id if league_id is not None else 'Ask commissioner'}")
        print("="*50 + "\n")
        return True

    # 4. Actual Sending Logic (for when you add credentials)
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def send_bug_report_email(report, support_email=None):
    """
    Sends a bug report email to the support inbox.
    """
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = os.getenv("MAIL_USERNAME")
    sender_password = os.getenv("MAIL_PASSWORD")
    support_email = support_email or os.getenv("SUPPORT_EMAIL", "nicholaspgrant@gmail.com")

    subject = f"Bug Report: {report['title']}"
    body = f"""
    <div style="font-family: Arial, sans-serif; color: #333;">
        <h2>New Bug Report</h2>
        <p><strong>Title:</strong> {report['title']}</p>
        <p><strong>Description:</strong><br/>{report['description']}</p>
        <p><strong>Issue Type:</strong> {report.get('issue_type') or 'Not specified'}</p>
        <p><strong>Page Name:</strong> {report.get('page_name') or 'Not provided'}</p>
        <p><strong>Page URL:</strong> {report.get('page_url') or 'Not provided'}</p>
        <p><strong>Reporter Email:</strong> {report.get('email') or 'Not provided'}</p>
        <p><strong>Reported At:</strong> {report.get('created_at') or 'Just now'}</p>
    </div>
    """

    if not sender_email or not sender_password:
        print("\n" + "=" * 50)
        print(f"📧 [SIMULATION] Bug Report Email to: {support_email}")
        print(f"🪲 Title: {report['title']}")
        print(f"📝 Description: {report['description']}")
        print(f"🏷️ Issue Type: {report.get('issue_type') or 'Not specified'}")
        print(f"📄 Page Name: {report.get('page_name') or 'Not provided'}")
        print(f"🔗 Page URL: {report.get('page_url') or 'Not provided'}")
        print(f"📨 Reporter Email: {report.get('email') or 'Not provided'}")
        print("=" * 50 + "\n")
        return True

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = support_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Failed to send bug report email: {e}")
        return False