#import logging
#import os
#import shutil
#import traceback
#from datetime import datetime
#from qc_application.utils.database_connection import establish_connection
#from sqlalchemy import text
#from qc_application.config.app_settings import AppSettings
#settings = AppSettings()
#USER = settings.get("user")

# --------  Now Redundant - Using FTP Instead --------


#class SendBatchDataLocal:
#    def __init__(self, batch_folders, remote_base_path):
#        self.batch_folders = batch_folders
#        self.remote_base_path = remote_base_path
#
#    def send_folders(self):
#        for survey_id, folder in self.batch_folders:
#            try:
#                folder_name = os.path.basename(folder)
#                dest_folder_path = os.path.join(self.remote_base_path, folder_name)
#                os.makedirs(dest_folder_path, exist_ok=True)
#
#                for root, dirs, files in os.walk(folder):
#                    rel_path = os.path.relpath(root, folder)
#                    target_root = os.path.join(dest_folder_path, rel_path)
#                    os.makedirs(target_root, exist_ok=True)
#                    for file in files:
#                        shutil.copy2(os.path.join(root, file), os.path.join(target_root, file))
#
#                print(f"✅ Uploaded {folder_name}")
#
#                self.update_qc_log(survey_id)
#
#            except Exception as e:
#                print(f"❌ Failed to send folder {folder}: {e}")
#
#    def update_qc_log(self, survey_id):
#        conn = None
#        try:
#            logging.debug(f"🔌 Connecting to DB for survey_id {survey_id}")
#            conn = establish_connection()
#            if conn is None:
#                print(f"❌ Could not connect to database for survey_id {survey_id}")
#                return
#
#            logging.debug("🧾 Starting transaction...")
#            trans = conn.begin()  # manually handle the transaction
#
#            try:
#                conn.execute(
#                    text("""
#                        UPDATE topo_qc.qc_log
#                        SET batch_sent = TRUE,
#                            batch_sender = :sender,
#                            batch_sent_date = :sent_date
#                        WHERE survey_id = :survey_id
#                    """),
#                    {
#                        "sender": f'{USER}', # from settings
#                        "sent_date": datetime.now(),
#                        "survey_id": survey_id
#                    }
#                )
#                logging.debug("✅ Executed update, committing transaction...")
#                trans.commit()
#                logging.info(f"✅ Updated qc_log for survey_id {survey_id}")
#
#            except Exception as inner_e:
#                logging.error(f"❌ Rolling back transaction for survey_id {survey_id}: {inner_e}")
#                trans.rollback()
#                traceback.print_exc()
#
#        except Exception as e:
#            logging.error(f"❌ Failed to update qc_log for survey_id {survey_id}: {type(e).__name__} - {e}")
#            traceback.print_exc()
#
#        finally:
#            if conn:
#                logging.debug("🔒 Closing connection.")
#                conn.close()