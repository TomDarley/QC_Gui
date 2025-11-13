import shutil

from qc_application.utils.database_connection import establish_connection
from sqlalchemy import text
from pathlib import Path
import geopandas as gpd
from qc_application.config.app_settings import AppSettings


settings = AppSettings()
interim_shp_file = settings.get("interim_survey_path")




from pathlib import Path
import shutil
import geopandas as gpd
from sqlalchemy import text

def confirm_rejection(survey_id):
    """
    Confirm rejection for a survey:
    - Update qc_log (set Failed -> Rejected)
    - Clear staging tables
    - Rename parent of qc_folder to Rejected
    """

    conn = establish_connection()
    if not conn:
        print("Database connection could not be established.")
        return False

    try:
        # ✅ Run all DB operations inside a single transaction
        with conn.begin():  # atomic commit/rollback
            # 1️⃣ Fetch survey details from rejected_topo_surveys
            survey_query = text("""
                SELECT * 
                FROM topo_qc.rejected_topo_surveys 
                WHERE survey_id = :survey_id
            """)
            result = conn.execute(survey_query, {"survey_id": survey_id})
            survey = result.mappings().first()
            if not survey:
                print(f"No rejected survey found for survey_id {survey_id}")
                return False

            survey_unit = survey.get("survey_unit")
            date = survey.get("completion_date")
            qc_folder = survey.get("qc_folder")
            if not survey_unit or not date or not qc_folder:
                print("Missing survey_unit, completion_date, or qc_folder")
                return False

            # 2️⃣ Update qc_log folder path to new parent folder name
            qc_parent = Path(qc_folder).parent
            new_qc_parent_path = qc_parent.parent / f"Rejected_{qc_parent.name}"

            update_log_query = text("""
                UPDATE topo_qc.qc_log
                SET qc_folder = :new_qc_folder
                WHERE survey_id = :survey_id
            """)
            conn.execute(update_log_query, {"new_qc_folder": str(new_qc_parent_path), "survey_id": survey_id})

            # 3️⃣ Delete staging tables
            conn.execute(text("""
                DELETE FROM staging_data.topo_data
                WHERE survey_unit = :survey_unit AND date = :date
            """), {"survey_unit": survey_unit, "date": date})

            conn.execute(text("""
                            DELETE FROM staging_data.topo_data_history
                            WHERE survey_unit = :survey_unit AND date = :date
                        """), {"survey_unit": survey_unit, "date": date})


            conn.execute(text("""
                DELETE FROM staging_data.cpa_table
                WHERE survey_unit = :survey_unit AND date = :date
            """), {"survey_unit": survey_unit, "date": date})

            conn.execute(text("""
                            DELETE FROM staging_data.cpa_table_history
                            WHERE survey_unit = :survey_unit AND date = :date
                        """), {"survey_unit": survey_unit, "date": date})

            # 4️⃣ Delete master_profiles for profiles from shapefile
            gdf = gpd.read_file(interim_shp_file)
            gdf["FULL_SUR_UNT"] = gdf["CELL"].astype(str) + gdf["SURVEY_UNT"].astype(str)
            profile_ids = gdf.loc[gdf["FULL_SUR_UNT"] == survey_unit, "REGIONAL_N"].dropna().unique().tolist()
            if profile_ids:
                conn.execute(text("""
                    DELETE FROM staging_data.master_profiles
                    WHERE profile_id = ANY(:profile_ids)
                """), {"profile_ids": profile_ids})

                conn.execute(text("""
                                    DELETE FROM staging_data.master_profiles_history
                                    WHERE profile_id = ANY(:profile_ids)
                                """), {"profile_ids": profile_ids})

        # ✅ Rename the parent folder AFTER transaction commits successfully
        shutil.move(str(qc_parent), str(new_qc_parent_path))

        # Delete the orginal survey folder
        original_survey_folder = Path(survey.get("original_survey_folder"))
        if original_survey_folder.exists() and original_survey_folder.is_dir():
            shutil.rmtree(original_survey_folder)

        print(f"Rejection confirmed for survey {survey_id}")
        return True

    except Exception as e:
        print(f"Error confirming rejection: {e}")
        return False

    finally:
        conn.close()




def reject_failed_entries(survey_id, rejection_comment = "Escalated to Rejected by Admin"):
    """
    Updates all enum columns in topo_qc.qc_log for a given survey_id
    where the value is 'Failed', setting it to 'Rejected'.

    Args:
        conn: SQLAlchemy connection object
        survey_id: int or str, the survey_id to filter rows
        comment : str, optional comment to log the rejection reason

    Returns:
        total_updated: int, total number of rows updated across all enum columns
    """

    conn = establish_connection()
    if not conn:
        print("Database connection could not be established.")
        return None


    # Step 1: Fetch all enum columns
    cols_query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'topo_qc'
          AND table_name = 'qc_log'
          AND udt_name IN ('issue_status_enum', 'check_status_enum')
    """)
    cols_result = conn.execute(cols_query).fetchall()
    enum_columns = [r[0] for r in cols_result]

    if not enum_columns:
        print("No enum columns found in topo_qc.qc_log.")
        return 0

    total_updated = 0

    # Step 2: Update each column
    for col in enum_columns:
        enum_comment_col = f"{col}_cc"

        update_query = text(f"""
            UPDATE topo_qc.qc_log
            SET {col} = 'Rejected', {enum_comment_col} = :comment
            WHERE survey_id = :survey_id
              AND {col} = 'Failed'
        """)
        result = conn.execute(update_query, {"survey_id": survey_id, "comment": rejection_comment})
        total_updated += result.rowcount  # number of rows affected in this column

    conn.commit()
    print(f"Updated {total_updated} 'Failed' entries to 'Rejected'.")
    return total_updated





def descalate_failed_entries(survey_id):
    """
    Reverts all 'Failed' values in topo_qc.qc_log for a given survey_id back to 'Issue'.
    """
    conn = establish_connection()
    if not conn:
        print("Database connection could not be established.")
        return 0

    # Fetch enum columns
    cols_query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'topo_qc'
          AND table_name = 'qc_log'
          AND udt_name IN ('issue_status_enum', 'check_status_enum')
    """)
    cols_result = conn.execute(cols_query).fetchall()
    enum_columns = [r[0] for r in cols_result]

    total_updated = 0
    for col in enum_columns:
        update_query = text(f"""
            UPDATE topo_qc.qc_log
            SET {col} = 'Issue'
            WHERE survey_id = :survey_id
              AND {col} = 'Failed'
        """)
        result = conn.execute(update_query, {"survey_id": survey_id})
        total_updated += result.rowcount

    conn.commit()
    print(f"Descalated {total_updated} 'Failed' entries to 'Issue'.")
    return total_updated
