import ftplib
import os
import logging
import traceback
from ftplib import FTP_TLS

from qc_application.utils.database_connection import establish_connection
from sqlalchemy import text
from qc_application.config.app_settings import AppSettings
from datetime import datetime

settings = AppSettings()
USER = settings.get("user")


# Secure the data channel
def update_qc_log(survey_id):
    conn = None
    try:
        logging.debug(f"🔌 Connecting to DB for survey_id {survey_id}")
        conn = establish_connection()
        if conn is None:
            print(f"❌ Could not connect to database for survey_id {survey_id}")
            return

        logging.debug("🧾 Starting transaction...")
        trans = conn.begin()  # manually handle the transaction

        try:
            conn.execute(
                text("""
                    UPDATE topo_qc.qc_log
                    SET batch_sent = TRUE,
                        batch_sender = :sender,
                        batch_sent_date = :sent_date
                    WHERE survey_id = :survey_id
                """),
                {
                    "sender": f'{USER}', # from settings
                    "sent_date": datetime.now(),
                    "survey_id": survey_id
                }
            )
            logging.debug("✅ Executed update, committing transaction...")
            trans.commit()
            logging.info(f"✅ Updated qc_log for survey_id {survey_id}")

        except Exception as inner_e:
            logging.error(f"❌ Rolling back transaction for survey_id {survey_id}: {inner_e}")
            trans.rollback()
            traceback.print_exc()

    except Exception as e:
        logging.error(f"❌ Failed to update qc_log for survey_id {survey_id}: {type(e).__name__} - {e}")
        traceback.print_exc()

    finally:
        if conn:
            logging.debug("🔒 Closing connection.")
            conn.close()


class FTPSender:
    def __init__(self, host, username, password, port, use_tls):
        """
        Initialize the FTPSender.

        :param host: FTP server hostname
        :param username: FTP username
        :param password: FTP password
        :param port: FTP port (default 21)
        :param use_tls: Use FTP over TLS/SSL if True
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_tls = use_tls
        self.ftp = None

    def connect(self):
        logging.info(f"Connecting to FTP server {self.host}:{self.port} (TLS={self.use_tls})")
        if self.use_tls:
            self.ftp = ftplib.FTP_TLS()
        else:
            self.ftp = ftplib.FTP()

        self.ftp.connect(self.host, self.port, timeout=30)
        self.ftp.login(self.username, self.password)
        if self.use_tls:
            self.ftp.prot_p()  # Switch to secure data connection
        logging.info("Connected successfully.")

    def disconnect(self):
        if self.ftp:
            self.ftp.quit()
            logging.info("Disconnected from FTP server.")

    def upload_file(self, local_path, remote_path):
        with open(local_path, 'rb') as f:
            logging.info(f"Uploading file {local_path} to {remote_path}")
            self.ftp.storbinary(f'STOR {remote_path}', f)

    def upload_folder(self, local_folder, remote_folder):
        # Ensure remote folder exists
        try:
            self.ftp.mkd(remote_folder)
        except ftplib.error_perm:
            pass  # Folder may already exist

        for root, _, files in os.walk(local_folder):
            rel_path = os.path.relpath(root, local_folder)
            ftp_path = os.path.join(remote_folder, rel_path).replace("\\", "/")

            try:
                self.ftp.mkd(ftp_path)
            except ftplib.error_perm:
                pass  # Folder may already exist

            for file in files:
                local_file = os.path.join(root, file)
                remote_file = f"{ftp_path}/{file}"
                self.upload_file(local_file, remote_file)

    def send_folders(self, folders):
        self.connect()
        try:
            for local_folder, remote_folder in folders:
                folder_name = os.path.basename(local_folder)
                self.upload_folder(local_folder, f"{remote_folder}/{folder_name}")
        finally:
            self.disconnect()

#ftp_sender = (FTPSender(
#    host="127.0.0.1",
#    username="TD",
#    password="Plymouth_C0",
#    use_tls=False
#))
#ftp_sender.connect()
#
#ftp_sender.send_folders([
#    (r"C:\Users\darle\Desktop\Blank.gdb", "/remote_folder")
#])