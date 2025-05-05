import requests
from bs4 import BeautifulSoup
import hashlib
import time
import schedule
from datetime import datetime
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import email.utils
import os
import random
import difflib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("web_monitor.log"),
        logging.StreamHandler()
    ]
)

class WebMonitor:
    def __init__(self, url, check_interval=600):
        self.url = url
        self.check_interval = check_interval
        self.last_hash = None
        self.last_content = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        self.last_notification_time = None
        self.notification_cooldown = 3600
        
   
        self.use_gmail = True
        
        if self.use_gmail:
            self.smtp_server = "smtp.gmail.com"
            self.smtp_port = 587 
            self.sender_email = "beken.drive@gmail.com"
            self.email_password = "ylrbjxombnsvutpu"
            self.recipient_email = "Aa.Bougrine@aui.ma"
            logging.info("Using Gmail with app password for SMTP access")
        else:
            self.smtp_server = "smtp.yandex.com"
            self.smtp_port = 465
            self.sender_email = "govquery@yandex.com"
            self.email_password = "cyzqfzkelxmcimdr"
            self.recipient_email = "Aa.Bougrine@aui.ma"
            logging.info("Using Yandex Mail with app password for SMTP access")
        
        self.test_email_configuration()

        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.snapshot_dir = "snapshots"
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def get_page_content(self):
        try:
            response = self.session.get(
                self.url,
                headers=self.headers,
                timeout=10,
                allow_redirects=True
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logging.error(f"Error fetching the page: {e}")
            return None

    def get_content_hash(self, content):
        return hashlib.md5(content.encode('utf-8')).hexdigest() if content else None

    def test_email_configuration(self):
        try:
            if self.use_gmail:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    logging.info(f"Testing connection to {self.smtp_server}...")
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.sender_email, self.email_password)
                    logging.info("Email configuration test successful!")
            else:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    logging.info(f"Testing connection to {self.smtp_server}...")
                    server.login(self.sender_email, self.email_password)
                    logging.info("Email configuration test successful!")
        except Exception as e:
            logging.error(f"Email Configuration Error: {e}")
            logging.error("Check SMTP access, app password, or settings.")

    def save_content_snapshot(self, content, timestamp):
        """Save a snapshot of the content for debugging purposes"""
        try:
            filename = f"{self.snapshot_dir}/snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info(f"Saved content snapshot to {filename}")
        except Exception as e:
            logging.error(f"Failed to save content snapshot: {e}")

    def can_send_notification(self):
        """Check if we can send a notification based on rate limiting"""
        current_time = time.time()
        if self.last_notification_time is None:
            return True
        
        time_since_last = current_time - self.last_notification_time
        if time_since_last > self.notification_cooldown:
            return True
        
        logging.info(f"Notification cooldown active. Next notification allowed in {int(self.notification_cooldown - time_since_last)} seconds.")
        return False

    def generate_diff(self, old_content, new_content):
        """Generate a human-readable diff between old and new content"""
        if not old_content or not new_content:
            return "Cannot generate diff - missing content"
            
        diff = difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            lineterm='',
            n=1
        )
        
        diff_lines = list(diff)
        if len(diff_lines) > 12:
            diff_lines = diff_lines[:2] + diff_lines[2:12]
            diff_lines.append("... [additional changes truncated] ...")
            
        return "\n".join(diff_lines)

    def send_email_notification(self, current_hash, diff_text=None):
        if not self.can_send_notification():
            self._print_fallback_notification(rate_limited=True)
            return
        
        try:
            msg = MIMEMultipart('alternative')
            
            msg['Message-ID'] = email.utils.make_msgid(domain=self.sender_email.split('@')[1])
            msg['Date'] = email.utils.formatdate(localtime=True)
            
            subjects = [
                f"Website Update Alert: Changes on {self.url.split('//')[1]}",
                f"Web Monitor Notification: Updates Detected",
                f"Important: Website Changes Found - {datetime.now().strftime('%H:%M')}",
                f"Website Monitoring Alert - {random.randint(1000, 9999)}"
            ]
            
            msg['Subject'] = random.choice(subjects)
            msg['From'] = f"Web Monitor <{self.sender_email}>"
            msg['To'] = self.recipient_email
            msg['Reply-To'] = self.sender_email
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            text_content = f"""Hello,

Our web monitoring system has detected changes on the website you're tracking.

Website: {self.url}
Time detected: {now}

The changes were identified at {now}. You can check the website directly to see the updates.

If you'd like to pause these notifications, please reply to this email.

Best regards,
Web Monitoring System
"""
            
            if diff_text:
                text_content += f"\n\nDetected changes:\n{diff_text}\n"

            html_content = f"""
<p>Hello,</p>

<p>Our web monitoring system has detected changes on the website you're tracking.</p>

<p><strong>Website:</strong> <a href="{self.url}">{self.url}</a><br>
<strong>Time detected:</strong> {now}</p>

<p>You can visit the website directly to see the updates.</p>

<p>If you'd like to pause these notifications, please reply to this email.</p>

<p>Best regards,<br>
Web Monitoring System</p>
"""
            if diff_text:
                html_content += f"""
<p><strong>Detected changes:</strong></p>
<pre style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; font-family: monospace;">{diff_text}</pre>
"""

            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            if self.use_gmail:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    logging.info(f"Connecting to {self.smtp_server}...")
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.sender_email, self.email_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    logging.info(f"Connecting to {self.smtp_server}...")
                    server.login(self.sender_email, self.email_password)
                    server.send_message(msg)

            logging.info(f"Email sent successfully to {self.recipient_email}")
            self.last_notification_time = time.time()

        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            self._print_fallback_notification()

    def _print_fallback_notification(self, rate_limited=False):
        notification_type = "RATE LIMITED" if rate_limited else "EMAIL FAILED"
        
        logging.info("=" * 50)
        logging.info(f"FALLBACK NOTIFICATION: {notification_type}")
        logging.info("=" * 50)
        logging.info(f"Subject: Web Monitor: Change Detected")
        logging.info(f"Body: A change was detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} on {self.url}")
        logging.info("=" * 50)

    def extract_important_content(self, full_content):
        """
        Extract only the important parts of a page to reduce false positives
        For time.is, we'll try to extract just the main time display
        """
        try:
            soup = BeautifulSoup(full_content, 'html.parser')
            
       
            for script in soup.find_all('script'):
                script.extract()
                
            for style in soup.find_all('style'):
                style.extract()
                
            for meta in soup.find_all('meta'):
                meta.extract()
                
            for div in soup.find_all('div', id=['clock', 'date', 'twd']):
                div.extract()
                
            body = soup.find('body')
            if body:
                return str(body)
            
            return str(soup)
            
        except Exception as e:
            logging.error(f"Error extracting important content: {e}")
            return full_content

    def check_for_updates(self):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logging.info(f"Checking for updates at {current_time}")
        
        content = self.get_page_content()
        if not content:
            logging.warning("Failed to get page content")
            return

        important_content = self.extract_important_content(content)
        
        current_hash = self.get_content_hash(important_content)

        if self.last_hash is None:
            self.last_hash = current_hash
            self.last_content = important_content
            self.save_content_snapshot(content, datetime.now())
            logging.info("Initial content stored.")
            return

        if current_hash != self.last_hash:
            logging.info("Change detected!")
            self.save_content_snapshot(content, datetime.now())
            
            diff_text = self.generate_diff(self.last_content, important_content)
            
            self.send_email_notification(current_hash, diff_text)
            self.last_hash = current_hash
            self.last_content = important_content
        else:
            logging.info("No changes detected.")

    def start_monitoring(self):
        logging.info(f"Monitoring {self.url} every {self.check_interval} seconds.")
        try:
            self.check_for_updates()
            schedule.every(self.check_interval).seconds.do(self.check_for_updates)

            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("\nMonitoring stopped by user.")
        except Exception as e:
            logging.error(f"Unexpected error: {e}", exc_info=True)
            logging.info("Monitoring stopped due to error.")

if __name__ == "__main__":
    URL_TO_MONITOR = "https://time.is/" #i can put any website here
    
    CHECK_INTERVAL = 600
    
    try:
        monitor = WebMonitor(URL_TO_MONITOR, CHECK_INTERVAL)
        monitor.start_monitoring()
    except Exception as e:
        logging.critical(f"Failed to start monitoring: {e}", exc_info=True)