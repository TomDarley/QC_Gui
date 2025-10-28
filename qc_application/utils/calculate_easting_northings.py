import pandas as pd
from datetime import datetime


def calculate_missing_northing_easting(df, date, survey_unit):
    def where_points_added(df):

        # Check only the 'Easting' column in head and tail
        head_has_nan = df["easting"].head().isna().any()
        tail_has_nan = df["easting"].tail().isna().any()

        if head_has_nan and tail_has_nan:
            status = "Both"
            head_count = df["easting"].head().isna().sum()
            tail_count = df["easting"].tail().isna().sum()
            nan_count = [head_count, tail_count]

        elif head_has_nan:
            status = "Head"
            nan_count = df["easting"].head().isna().sum()

        elif tail_has_nan:
            status = "Tail"
            nan_count = df["easting"].tail().isna().sum()

        else:
            status = "No Added Points"
            nan_count = None

        return status, nan_count

    status, nan_count = where_points_added(df)

    if status != "No Added Points":
        # use and and tail to get points added beofore and after....
        df = df.reset_index(drop=True, inplace=False)
        date_str = date.strftime('%Y-%m-%d')
        df["date"]= date_str
        df["survey_unit"] = survey_unit

        # drop all na rows from df
        no_na_df = df.dropna(subset=["easting"])

        # get the current date and profile values we use them to fill in the missing cells
        no_na_df_profile = no_na_df["reg_id"].tolist()[0]
        no_na_df_date = no_na_df["date"].tolist()[0]
        no_na_survey_unit = no_na_df['survey_unit'].tolist()[0]
        no_na_df_month  = datetime.strptime(no_na_df_date, '%Y-%m-%d').month
        no_na_df_year  = datetime.strptime(no_na_df_date, '%Y-%m-%d').year

        # get a list of all exiting northings
        non_null_eastings = no_na_df['easting'].tolist()
        non_null_northings = no_na_df['northing'].tolist()
        non_null_chainage = no_na_df['chainage'].tolist()



        def process_head(non_null_northings, non_null_eastings, number_of_nans):

            if isinstance(number_of_nans, list):
                number_of_head_nulls = number_of_nans[0]
            else:
                number_of_head_nulls = number_of_nans

            generated_row_list = list(range(0, number_of_head_nulls))
            # get the first two values
            northing_1, northing_2 = float(non_null_northings[0]), float(non_null_northings[1])
            easting_1, easting_2 = float(non_null_eastings[0]), float(non_null_eastings[1])
            chainage_1, chainage_2 = float(non_null_chainage[0]), float(non_null_chainage[1])

            # Calculate deltas (change in northing and easting)
            delta_northing = northing_2 - northing_1
            delta_easting = easting_2 - easting_1
            delta_chainage = chainage_2 - chainage_1

            # Calculate slopes in terms of northing/chainage and easting/chainage
            slope_northing = delta_northing / delta_chainage
            slope_easting = delta_easting / delta_chainage

            # Calculate the missing northing and easting values using the slopes
            for i in generated_row_list:  # For the two missing rows
                chainage = df.loc[i, 'chainage']

                northing_cal = round(northing_1 + slope_northing * (chainage - chainage_1), 3)
                df.loc[i, 'northing'] = northing_cal

                easting_cal = round(easting_1 + slope_easting * (chainage - chainage_1), 3)
                df.loc[i, 'easting'] = easting_cal

                # Additionally fill in the other missing values
                df.loc[i, 'fc'] = "ZZ"
                df.loc[i, 'reg_id'] = no_na_df_profile
                df.loc[i, 'date'] = no_na_df_date
                df.loc[i, 'survey_unit'] = no_na_survey_unit
                df.loc[i, 'month'] = no_na_df_month
                df.loc[i, 'year'] = no_na_df_year
                df.loc[i, 'profile'] = "" # override nan value in profile

        def process_tail(non_null_northings, non_null_eastings, number_of_nans: list):

            if isinstance(number_of_nans, list):
                number_of_tail_nulls = number_of_nans[1]
            else:
                number_of_tail_nulls = number_of_nans

            total_number_of_rows = len(df) - 1
            generated_row_list = list(range(0, number_of_tail_nulls))
            reverse_index_list = []
            for i in generated_row_list:
                index_position = total_number_of_rows - i
                reverse_index_list.append(index_position)

            # get the first two values
            northing_1, northing_2 = float(non_null_northings[0]), float(non_null_northings[1])
            easting_1, easting_2 = float(non_null_eastings[0]), float(non_null_eastings[1])
            chainage_1, chainage_2 = float(non_null_chainage[0]), float(non_null_chainage[1])

            # Calculate deltas (change in northing and easting)
            delta_northing = northing_2 - northing_1
            delta_easting = easting_2 - easting_1
            delta_chainage = chainage_2 - chainage_1


            # Calculate slopes in terms of northing/chainage and easting/chainage
            slope_northing = delta_northing / delta_chainage
            slope_easting = delta_easting / delta_chainage

            print(df.dtypes)

            # Calculate the missing northing and easting values using the slopes
            for i in generated_row_list:  # For the two missing rows
                chainage = df.loc[i, 'chainage']

                northing_cal = round(northing_1 + slope_northing * (chainage - chainage_1), 3)
                df.loc[i, 'northing'] = northing_cal

                easting_cal = round(easting_1 + slope_easting * (chainage - chainage_1), 3)
                df.loc[i, 'easting'] = easting_cal

                # Additionally fill in the other missing values
                df.loc[i, 'fc'] = "ZZ"
                df.loc[i, 'reg_id'] = no_na_df_profile
                df.loc[i, 'date'] = no_na_df_date
                df.loc[i, 'survey_unit'] = no_na_survey_unit
                df.loc[i, 'month'] = no_na_df_month
                df.loc[i, 'year'] = no_na_df_year
                df.loc[i, 'profile'] = ""  # override nan value in profile

            # Calculate the missing northing and easting values using the slopes
            for i in reverse_index_list:  # For the two missing rows
                chainage = df.loc[i, 'chainage']

                northing_cal = round(northing_1 + slope_northing * (chainage - chainage_1), 3)
                df.loc[i, 'northing'] = northing_cal

                easting_cal = round(easting_1 + slope_easting * (chainage - chainage_1), 3)
                df.loc[i, 'easting'] = easting_cal

                # Additionally fill in the other missing values
                df.loc[i, 'fc'] = "ZZ"
                df.loc[i, 'reg_id'] = no_na_df_profile
                df.loc[i, 'date'] = no_na_df_date
                df.loc[i, 'survey_unit'] = no_na_survey_unit
                df.loc[i, 'month'] = no_na_df_month
                df.loc[i, 'year'] = no_na_df_year
                df.loc[i, 'profile'] = ""  # override nan value in profile

        if status == "Both":

            # process head:
            process_head(non_null_northings, non_null_eastings, nan_count)
            process_tail(non_null_northings, non_null_eastings, nan_count)
        elif status == 'Head':
            process_head(non_null_northings, non_null_eastings, nan_count)
        elif status == 'Tail':
            process_tail(non_null_northings, non_null_eastings, nan_count)
    print(df)

    df1 = df.copy()

    df1['elevation'] = df1['elevation'].round(3)

    return df1