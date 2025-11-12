import os
import re
import logging
from datetime import datetime
from typing import Optional, Dict, List
import psycopg2
from sqlalchemy import text

from qc_application.utils.database_connection import establish_connection

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

survey_naming_check_results: Dict[str, List[bool]] = {
    "Survey_Unit_Valid": [],
    "Survey_Date_Valid": [],
    "Survey_Folder_Naming": [],
    "Batch_lei_tri_Naming": [],
    "Batch_tip_tp_tb_Naming": [],
    "Survey_Report_Naming": [],
    "Survey_Meta_Naming": [],
}


def extract_survey_unit(filename: str) -> Optional[str]:
    match = re.match(r'^([^-_]+(?:-[^-_]+)?)_', filename)
    return match.group(1) if match else None


def extract_date(filename: str) -> Optional[str]:
    match = re.search(r'_(\d{8})', filename)
    return match.group(1) if match else None


def check_valid_survey_unit(survey_unit: str) -> bool:
    logger.info(f"Checking Survey Unit {survey_unit}")

    try:
        conn = establish_connection()  # SQLAlchemy-style engine connection

        query = text("""
            SELECT survey_unit 
            FROM topo_qc.survey_units 
            WHERE survey_unit = :survey_unit
        """)

        result = conn.execute(query, {"survey_unit": survey_unit}).mappings().fetchone()

        valid = result is not None
        survey_naming_check_results["Survey_Unit_Valid"] = [valid]

        if valid:
            logger.info(f"Survey unit exists: {result['survey_unit']}")
        else:
            logger.info("Survey unit does not exist.")

        return valid

    except Exception as e:
        logger.error(f"Database query failed: {e}")
        survey_naming_check_results["Survey_Unit_Valid"] = [False]
        return False

    finally:
        conn.close


def check_valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y%m%d")
        survey_naming_check_results["Survey_Date_Valid"] = [True]
        logger.info("✅ Date is valid.")
        return True
    except ValueError:
        survey_naming_check_results["Survey_Date_Valid"] = [False]
        logger.error("❌ Invalid date format or non-existent date.")
        return False


def check_parent_path_name(input_path: str, extracted_name: str) -> None:
    grandparent_dir = os.path.dirname(os.path.dirname(input_path))
    grandparent_name = os.path.basename(grandparent_dir)
    valid = extracted_name in grandparent_name
    survey_naming_check_results["Survey_Folder_Naming"] = [valid]
    if valid:
        logger.info("✅ Survey Directory Name Matches Input File Naming.")
    else:
        logger.warning("❌ Survey Directory Name Does Not Match Input File.")


def match_report_filename(filename: str, survey_unit: str) -> bool:
    pattern = fr"^Report_Topo_{re.escape(survey_unit)}_(\d{{8}})(\.\w+)?$"
    valid = bool(re.match(pattern, filename))
    survey_naming_check_results["Survey_Report_Naming"] = [valid]
    return valid


def match_meta_topo_filename(filename: str) -> bool:
    pattern = r"^Meta_Topo_([A-Za-z]+)_(\d{8})(\.\w+)?$"
    valid = bool(re.match(pattern, filename))
    survey_naming_check_results["Survey_Meta_Naming"] = [valid]
    return valid


def check_batch_file_names(input_path: str, extracted_name: str, is_baseline: bool, is_pco: bool) -> None:
    batch_folder = os.path.dirname(os.path.abspath(input_path))
    files = os.listdir(batch_folder)
    survey_unit = extracted_name.split("_")[0]

    # Determine expected batch filenames
    lei_tri, tip_tp_tb = {
        (False, False): (f"{extracted_name}lei.zip", f"{extracted_name}tip.txt"),
        (True, False): (f"{extracted_name}lei.zip", f"{extracted_name}tp.txt"),
        (False, True): (f"{extracted_name}tri.zip", f"{extracted_name}tip.txt"),
        (True, True): (f"{extracted_name}tri.zip", f"{extracted_name}tp.txt"),
    }[(is_baseline, is_pco)]

    survey_naming_check_results["Batch_lei_tri_Naming"] = [lei_tri in files]
    survey_naming_check_results["Batch_tip_tp_tb_Naming"] = [tip_tp_tb in files]

    # Check reports and metadata
    for file in files:
        if file.endswith(".pdf"):
            logger.info(f"Survey Report Name: {match_report_filename(file, survey_unit)}")
        elif file.endswith((".xlsx", ".xls")):
            logger.info(f"Meta Name: {match_meta_topo_filename(file)}")


def extract_and_validate_name(input_path: str) -> Optional[str]:
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    survey_unit = extract_survey_unit(base_name)
    date_str = extract_date(base_name)

    valid_unit = check_valid_survey_unit(survey_unit) if survey_unit else False
    valid_date = check_valid_date(date_str) if date_str else False

    if valid_unit and valid_date:
        valid_name = f"{survey_unit}_{date_str}"
        logger.info(f"✅ Valid name: {valid_name}")
        return valid_name
    logger.warning("❌ Invalid filename format or data.")
    return None


def check_data_labeling(input_path: str, is_baseline: bool, is_pco: bool) -> Dict[str, str]:
    extracted_name = extract_and_validate_name(input_path)
    check_parent_path_name(input_path, extracted_name if extracted_name else "")

    if extracted_name:
        check_batch_file_names(input_path, extracted_name, is_baseline, is_pco)

    failed_checks = [key for key, value in survey_naming_check_results.items() if not value[0]]
    if failed_checks:
        return {"Result": "Issue", "Comment": "Incorrect Naming: " + ", ".join(failed_checks)}
    return {"Result": "Pass", "Comment": "Auto Checked."}
