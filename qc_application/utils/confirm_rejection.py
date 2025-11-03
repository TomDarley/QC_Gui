import shutil

from qc_application.utils.database_connection import establish_connection
from sqlalchemy import text
from pathlib import Path

def confirm_rejection(survey_id):
    """
    Confirm rejection for a survey:
    1) Fetch survey details
    2) Move the survey to a rejected folder
    3) Update the qc_folder path in the database
    """

    def get_survey_folder_path(survey_id):
        conn = establish_connection()
        if not conn:
            print("Database connection could not be established.")
            return None

        try:
            query = text(
                "SELECT * FROM topo_qc.rejected_topo_surveys WHERE survey_id = :survey_id"
            )
            result = conn.execute(query, {"survey_id": survey_id})
            survey_details = result.mappings().first()  # returns dict-like object

            qc_folder = survey_details['qc_folder'] if survey_details else None
            if not qc_folder:
                return None

            qc_folder_path = Path(qc_folder)
            parent_dir = qc_folder_path.parent  # <-- only one level up

            return parent_dir
        except Exception as e:
            print(f"Error fetching survey details: {e}")
            return None

    def rename_survey_folder(survey_folder_dir):
        try:
            survey_folder_dir = Path(survey_folder_dir)
            parent_dir = survey_folder_dir.parent
            new_folder_name = f"Rejected_{survey_folder_dir.name}"
            new_folder_path = parent_dir / new_folder_name

            # Rename the folder
            shutil.move(str(survey_folder_dir), str(new_folder_path))
            return Path(new_folder_path)
        except Exception as e:
            print(f"Error renaming survey folder: {e}")
            return None



    def set_new_qc_folder_path_in_db(survey_id, new_folder_path):

        conn = establish_connection()
        if not conn:
            print("Database connection could not be established.")
            return False

        try:
            query = text(
                "UPDATE topo_qc.rejected_topo_surveys "
                "SET qc_folder = :new_qc_folder "
                "WHERE survey_id = :survey_id"
            )
            conn.execute(query, {
                "new_qc_folder": str(new_folder_path),
                "survey_id": survey_id
            })
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating qc_folder path in database: {e}")
            return False


    # Fetch survey details
    survey_folder_dir  = get_survey_folder_path(survey_id)
    if not survey_folder_dir:
        print(f"No survey found with survey_id {survey_id}")
        return False

    new_qc_folder_path = rename_survey_folder(survey_folder_dir)

    set_new_qc_folder_path_in_db(survey_id, new_qc_folder_path)











    # Example: simulate moving the survey to a rejected folder
    # You can replace this with your actual file operations
    print(f"Moving survey {survey_id} to rejected folder...")

    # Example: simulate updating qc_folder path in database
    # conn.execute(text("UPDATE ..."), {...})
    print(f"Updating qc_folder path for survey {survey_id} in database...")

    print(f"Rejection confirmed for survey {survey_id}")


