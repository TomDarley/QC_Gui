import glob
import logging
import os
import re
import shutil
import tempfile
from qc_application.utils.database_connection import establish_connection
from sqlalchemy import text


class Auto_Batcher:
    DEFAULT_DRIVE = r"X:\Data\Survey_Topo\Phase4"

    def __init__(self, df):
        self.df = df
        self.conn = None

    @staticmethod
    def get_file_paths(dir_path):

        """Function used to convert all file paths in a dir to a list of string paths"""
        file_paths = []
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                file_paths.append(file_path)
        return file_paths



    def get_qc_folder_from_db(self, survey_unit, received_date):
        """
        Retrieves the qc_folder path from the qc_log table for a given survey_unit and survey_received date.
        Returns None if no record is found.
        """

        if not self.conn:
            self.conn = establish_connection()
        if not self.conn:
            print("❌ Could not connect to database.")
            return None

        try:
            query = text("""
                SELECT qc_folder
                FROM topo_qc.qc_log
                WHERE survey_unit = :survey_unit AND survey_received = :received_date
                LIMIT 1
            """)
            result = self.conn.execute(query, {"survey_unit": survey_unit, "received_date": received_date}).fetchone()

            if result:
                return result[0]
            else:
                print(f"No qc_folder found for {survey_unit} on {received_date}")
                return None

        except Exception as e:
            print(f"Query error: {e}")
            return None

    def get_batch_number_from_db(self, survey_id):
        """
        Retrieves the batch_number for a given survey_id from topo_qc.qc_log.
        Returns None if no record is found.
        """
        if not self.conn:
            self.conn = establish_connection()
        if not self.conn:
            print("❌ Could not connect to database.")
            return None

        try:
            query = text("""
                SELECT batch_number
                FROM topo_qc.qc_log
                WHERE survey_id = :survey_id
                LIMIT 1
            """)
            result = self.conn.execute(query, {"survey_id": survey_id}).fetchone()

            if result:
                return result[0]
            else:
                print(f"No batch number found for {survey_id}")
                return None

        except Exception as e:
            print(f"Query error: {e}")
            return None



    def is_baseline(self, survey_type: str):
        if "interim" in survey_type.lower():
            return False
        elif "baseline" in survey_type.lower():
            return True
        else:
            print("Warning: The survey type could not be determined, defaulting to Not Baseline.")
            return False

    def is_pco_survey(self, batch_folder_path):
        if "PCO" in batch_folder_path:
            return True
        elif "PCO" not in batch_folder_path:
            return False
        else:
            print("Warning: The survey type could not be determined, defaulting to Not PCO.")
            return False

    def generate_re_patterns(self, is_pco: bool, is_baseline: bool):
        """Function generates re search patterns which change based on the survey type"""

        if is_pco and is_baseline:
            re_patterns = {"tri_zip_check": ".*tri.zip$", "tp.txt_check": ".*tp.txt$",
                           "tb_txt_check": ".*tb.txt$", "pdf_check": ".*.pdf$",
                           "xls_xlsx_check": r".*(\.xlsx|\.xls)$"}
        elif is_pco and not is_baseline:
            re_patterns =  {"tri_zip_check": ".*tri.zip$", "tp.txt_check": ".*tp.txt$",
                                       "tb_txt_check": ".*tb.txt$", "pdf_check": ".*.pdf$",
                                       "xls_xlsx_check": r".*(\.xlsx|\.xls)$"}

        elif not is_pco and is_baseline:
            re_patterns = {"lei_zip_check:": "*lei.zip$", "tp.txt_check": ".*tp.txt$",
                           "pdf_check": ".*.pdf$", "xls_xlsx_check": r".*(\.xlsx|\.xls)$"}

        elif not is_pco and not is_baseline:
            re_patterns =  {"lei_zip_check": ".*lei.zip$", "tip.txt_check": ".*tip.txt$",
             "pdf_check": ".*.pdf$", "xls_xlsx_check": r".*(\.xlsx|\.xls)$"}


        else:
            print("The re_search_patterns could not be set, exiting...")
            re_patterns = {}

        return re_patterns

    def run_batch_files_checks(self, batch_folder_path, found_batch_files: list, found_other_files: list,
                               survey_type: str):

        """Function checks, if current batch not a baseline, for all files to be present. It returns a
           dictionary of the check name(key) and found status(value). Checks run:

           1) Lei.zip is present or tri.zip if pco batch
           2) tip.txt is present
           4) pdf is present
           5) xls/xlsx is present

           """

        # holds a dict of k(check), v(check_result -> bool)
        batch_file_check_results = {}

        # PCO surveys have tri.zip not lei.zip folders, we determine this here
        is_pco_survey = self.is_pco_survey(batch_folder_path)

        # baseline surveys have additional files to batch, we determine this here
        is_baseline = self.is_baseline(survey_type)

        # check if pco baseline, if we are look for a tri.zip, else a lei.zip
        re_patterns = self.generate_re_patterns(is_pco_survey, is_baseline)

        # loop over each regex pattern and search for files, if found we update the check results
        # with the re_patterns key and bool True
        for re_patterns_key in re_patterns.keys():
            for file_path in found_batch_files:
                if re.match(re_patterns.get(re_patterns_key), file_path):
                    found = True
                    batch_file_check_results.update({re_patterns_key: found})
                    break

        # If file not found the re_patterns key will not have been updated to the check results, check
        # if any keys in the re patterns are not in the check results
        diff = [x for x in re_patterns.keys() if x not in batch_file_check_results.keys()]

        # Update the check results with the missing keys, if found, with the key name and bool False
        if diff:
            for k_name in diff:
                batch_file_check_results.update({k_name: False})

        # if the survey is a baseline we also need to check for a tb.txt file in the other folder which needs to be
        # included in the batch
        if is_baseline:
            pattern = ".*tb.txt$"
            batch_file_check_results["tb_txt_other_check"] = any(
                re.match(pattern, file_path) for file_path in found_other_files
            )

        return batch_file_check_results

    def evaluate_batch_results(self, batch_file_check_results):
        """
            Checks each batch to see if all file checks passed.

            Args:
                batch_file_check_results (dict): A dictionary with batch IDs as keys and dictionaries of check results as values.

            Returns:
                tuple:
                    - List of batch IDs that passed all checks.
                    - List of dicts for batches that failed at least one check.
            """
        failed_batches = []
        passed_batch_files = []

        for batch_id, checks in batch_file_check_results.items():
            if all(checks.values()):
                passed_batch_files.append(batch_id)
            else:
                failed_batches.append({batch_id: checks})

        return passed_batch_files, failed_batches

    def run_auto_batch(self):
        print(self.df)

        batch_file_check_results = {}

        for _, row in self.df.iterrows():
            survey_id = row["survey_id"]
            survey_unit = row["survey_unit"]
            received_date = row["survey_received"]
            survey_type = row["survey_type"]

            qc_folder = self.get_qc_folder_from_db(survey_unit, received_date)
            if not qc_folder:
                print(f"QC folder not found for {survey_unit} - {received_date}")
                batch_file_check_results.update({survey_id: {}})
                continue  # Skip to next survey

            # Replace both 'QC_files' and 'QC_Files' with 'Batch'
            batch_folder = re.sub(r"QC[_]?files", "Batch", qc_folder,flags=re.IGNORECASE)

            if not os.path.exists(batch_folder):
                print(f"Batch folder not found for {batch_folder}")
                batch_file_check_results.update({survey_id: {}})
                continue

                # Construct the other folder path by replacing QC files
            other_folder = re.sub(r"QC[_]?files", "Other", qc_folder,flags=re.IGNORECASE)
            if not os.path.exists(other_folder):
                print(f"Other folder not found for {survey_unit} - {received_date}")
                batch_file_check_results.update({survey_id: {}})
                continue

            try:
                batch_files = self.get_file_paths(batch_folder)
                other_files = self.get_file_paths(other_folder)
            except Exception as e:
                print(f"Failed to extract files: {e}")
                batch_file_check_results.update({survey_id: {}})
                continue

            try:
                batch_file_checks = self.run_batch_files_checks(batch_folder, batch_files, other_files, survey_type)
                print(f"Batch checks: {batch_file_checks}")
                batch_file_check_results.update({survey_id: batch_file_checks})
            except Exception as e:
                print(f"Failed to run batch file checks: {e}")
                batch_file_check_results.update({survey_id: {}})
                continue

        print(batch_file_check_results)
        passed_ids, failed_ids = self.evaluate_batch_results(batch_file_check_results)

        return passed_ids, failed_ids

    def make_batch_folders(self, passed_ids):

        created_batch_folders ={}

        for _, row in self.df.iterrows():
            survey_id = row["survey_id"]

            print(self.df.columns)
            if survey_id in passed_ids:
                survey_unit = row["survey_unit"]
                received_date = row["survey_received"]
                survey_type = row["survey_type"]


                baseline_tb_txt_path= None

                batch_number  = self.get_batch_number_from_db(survey_id)

                # extract the qc folder path for the survey
                qc_folder = self.get_qc_folder_from_db(survey_unit, received_date)
                if qc_folder:
                    print(f"Found QC folder: {qc_folder}")
                else:
                    print(f"QC folder not found for {survey_unit} - {received_date}")

                    break
                # construct batch folder from qc folder path
                batch_folder = re.sub(r"QC[_]?files", "Batch", qc_folder, flags=re.IGNORECASE)
                if os.path.exists(batch_folder):
                    print(batch_folder)
                else:
                    print(f"Batch folder not found for {batch_folder}")
                    break

                # construct the other folder path from the qc folder path
                other_folder = re.sub(r"QC[_]?files", "Other", qc_folder,flags=re.IGNORECASE)
                if os.path.exists(other_folder):
                    print(other_folder)
                else:
                    print(f"Other folder not found for {survey_unit} - {received_date}")
                    break

                if "baseline" in survey_type.lower():
                    try:
                        other_files = self.get_file_paths(other_folder)
                        print(other_files)
                    except Exception as e:
                        print(f"Failed to extract other files {e}")
                        break

                    pattern = ".*tb.txt$"
                    match = next((f for f in other_files if re.match(pattern, f)), None)
                    if match:
                        print("Found:", match)
                        baseline_tb_txt_path = match
                    else:
                        print("No match found.")
                        break


                temp_dir = r"C:\Users\darle\Desktop\Batch_Folder"
                destination_folder = os.path.join(temp_dir, os.path.basename(batch_folder))
                final_destination = f"{destination_folder}_{batch_number}"

                if os.path.exists(final_destination):
                    print(f"Already Batched {final_destination}")
                    created_batch_folders.update({survey_id: final_destination})
                else:
                    shutil.copytree(batch_folder, final_destination)
                    if baseline_tb_txt_path:
                        shutil.copy(baseline_tb_txt_path,final_destination)
                    created_batch_folders.update({survey_id: final_destination})


        return created_batch_folders













