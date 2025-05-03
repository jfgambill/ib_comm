import logging
import os
import configparser
import smtplib
import sys
import ssl
from typing import List

# Third‑party
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='send_email.log'
)
logger = logging.getLogger('protonmail_sender')


class EmailSender:
    """Utility class for sending e‑mails through ProtonMail Bridge.

    Configuration is read from an INI file with a ``[ProtonMail]`` section
    containing::

        smtp_server = 127.0.0.1
        smtp_port   = 1025
        smtp_use_tls = true
        email = you@example.com
        bridge_password = ********

    """

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def __init__(self, config_file: str = 'config.ini') -> None:
        self.config = self._load_config(config_file)

    # @staticmethod
    def _load_config(self, config_file: str) -> configparser.ConfigParser:
        if not os.path.exists(config_file):
            self._create_default_config(config_file)
            logger.info(f"Created default configuration file: {config_file}")
            #raise FileNotFoundError(f"Please edit {config_file} with your ProtonMail credentials")

        cfg = configparser.ConfigParser()
        cfg.read(config_file)
        return cfg
    
    def _create_default_config(self, config_file: str) -> None:
        """Create a default configuration file."""
        config = configparser.ConfigParser()
        config['ProtonMail'] = {
            'email': 'john.gambill@protonmail.com',
            'bridge_password': 'cN0mvXqWUhAbbQi7aBrRYw',
            'imap_server': '127.0.0.1',
            'imap_port': '1143',
            'smtp_server': '127.0.0.1',
            'smtp_port': '1025',
            'smtp_use_tls': 'False'
        }
        config['Notifications'] = {
            'phone_number': '4846801564',
            'carrier': 'tmomail.net',
            'from_email': 'john.gambill@protonmail.com'
        }
        
        with open(config_file, 'w') as f:
            config.write(f)

    # ------------------------------------------------------------------
    # Plain‑text sender (existing behaviour)
    # ------------------------------------------------------------------
    def send_email(self, subject: str, body: str) -> bool:
        """Send a plain‑text message. Returns *True* if sent successfully."""
        try:
            msg = MIMEText(body, "plain")
            msg['Subject'] = subject
            msg['From'], msg['To'] = self._creds().email, self._creds().email
            self._deliver(msg)
            return True
        except Exception as exc:
            logger.exception("Failed to send notification")
            return False

    # ------------------------------------------------------------------
    # New ✨ method
    # ------------------------------------------------------------------
    def send_email_with_inline_df(self, subject: str, df: pd.DataFrame) -> bool:
        """Send *df* rendered as an inline HTML table.

        A plain‑text fallback is included as the first MIME part so that
        minimal clients (or plaintext‑only previews) still show something
        meaningful.
        """
        try:
            # 1) Build multipart/alternative message --------------------
            msg = MIMEMultipart("alternative")
            msg['Subject'] = subject
            msg['From'], msg['To'] = self._creds().email, self._creds().email

            # Plain‑text part (fallback)
            plaintext = MIMEText(df.to_string(index=False), "plain")
            msg.attach(plaintext)

            # HTML part
            html_table = df.to_html(index=False, border=0, justify="center")
            html_body = f"""<html><head><style>
                    table {{ border‑collapse: collapse; font‑family: Arial, sans‑serif; }}
                    th, td {{ border:1px solid #ddd; padding:4px 8px; text‑align: right; }}
                    th {{ background:#f2f2f2; }}
                </style></head><body>
                {html_table}
            </body></html>"""
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)

            # 2) Deliver ----------------------------------------------
            self._deliver(msg)
            return True
        except Exception:
            logger.exception("Failed to send DataFrame e‑mail")
            return False

    # ------------------------------------------------------------------
    # Internal helpers (credentials + transport)
    # ------------------------------------------------------------------
    class _Creds:
        """Simple struct‑like object holding credential info."""
        def __init__(self, email: str, pw: str, server: str, port: int, use_tls: bool):
            self.email, self.password = email, pw
            self.server, self.port, self.use_tls = server, port, use_tls

    def _creds(self) -> "EmailSender._Creds":
        sec = self.config['ProtonMail']
        email = sec.get('email')
        pw = sec.get('bridge_password')
        if not (email and pw):
            raise RuntimeError("Email credentials missing in config file")
        server = sec.get('smtp_server', '127.0.0.1')
        port = int(sec.get('smtp_port', '1025'))
        use_tls = sec.get('smtp_use_tls', 'False').lower() == 'true'
        return self._Creds(email, pw, server, port, use_tls)

    def _deliver(self, msg) -> None:
        c = self._creds()
        context = ssl.create_default_context()
        with smtplib.SMTP(c.server, c.port, timeout=30) as s:
            if c.use_tls:
                s.starttls(context=context)
            s.login(c.email, c.password)
            s.send_message(msg)
            logger.info("Email sent to %s with subject '%s'", msg['To'], msg['Subject'])


# -----------------------------------------------------------------------------
# Optional CLI usage
# -----------------------------------------------------------------------------

def main() -> int:  # pragma: no cover (simple demo CLI)
    import argparse
    import pandas as pd

    parser = argparse.ArgumentParser(description='ProtonMail Email Sender')
    parser.add_argument('--config', default='config.ini', help='Path to configuration file')
    parser.add_argument('--subject', default='Test DataFrame', help='Email subject')
    args = parser.parse_args()

    sender = EmailSender(args.config)

    # Tiny sample DF
    sample_df = pd.DataFrame({
        'Ticker': ['AAPL', 'MSFT', 'NVDA'],
        'PnL ($)': [1234.56, -789.01, 4567.89],
        'Position': [100, -50, 25]
    })

    ok = sender.send_email_with_inline_df(args.subject, sample_df)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
