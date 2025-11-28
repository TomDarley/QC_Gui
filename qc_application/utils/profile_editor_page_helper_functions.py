
from qc_application.utils.database_connection import establish_connection
from sqlalchemy import text
import pandas as pd
def get_available_survey_units_and_profiles():
    conn = establish_connection()

    query = text("""
        SELECT DISTINCT survey_unit, reg_id, date 
        FROM topo_qc.topo_data
        ORDER BY survey_unit, reg_id, date
    """)

    result = conn.execute(query)

    # Build DataFrame
    df = pd.DataFrame(result.fetchall(), columns=result.keys())

    conn.close()
    print(df)
    return df

#get_available_survey_units_and_profiles()



def get_existing_topo_data(survey_unit, date):
    conn = establish_connection()

    query = text("""
        SELECT * 
        FROM topo_qc.topo_data
        WHERE survey_unit = :survey_unit AND date = :date
        ORDER BY chainage ASC
        
    """)
    query = query.bindparams(survey_unit=survey_unit, date=date)

    result = conn.execute(query)

    # Build DataFrame
    df = pd.DataFrame(result.fetchall(), columns=result.keys())

    conn.close()
    print(df)
    return df

#get_existing_topo_data(survey_unit="6aSU10", date="2020-06-25")