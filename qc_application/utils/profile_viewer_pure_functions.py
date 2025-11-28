import pandas as pd

def qc_profile(master_df, survey_df):
    """
    master_df, survey_df: pandas DataFrames with columns ['chainage', 'elevation']
    chainage increases seaward.
    Returns dict with flags and diagnostics.
    """
    master = master_df.sort_values('chainage').reset_index(drop=True)
    survey = survey_df.sort_values('chainage').reset_index(drop=True)

    flags = []

    # --- Check 1: Profile reaches MLW ---
    mlsw = master['elevation'].min()
    if survey['elevation'].min() > mlsw:
        flags.append("Profile does not reach MLW elevation")

    # --- Check 2: Survey extent ---
    cutoff_chainage = master['chainage'].quantile(0.9)
    min_cutoff_chainage = master['chainage'].quantile(0.3)

    max_master_chainage = master['chainage'].max()
    max_survey_chainage = survey['chainage'].max()

    # FIX: Simplified landward check
    landward_section = survey[survey['chainage'] <= min_cutoff_chainage]
    if landward_section.empty:
        flags.append("Survey does not reach master profile landward limit")

    # Check chainage order increases for each point
    survey_raw_chainage = survey_df['chainage']
    sorted_survey_chainage = survey_df['chainage'].sort_values().reset_index(drop=True)
    survey_raw_chainage_reset = survey_raw_chainage.reset_index(drop=True)
    if not survey_raw_chainage_reset.equals(sorted_survey_chainage):
        flags.append("Survey chainage values are not strictly increasing")

    # --- Check 4: Seaward section stays above MLSW ---
    seaward_section = survey[survey['chainage'] >= cutoff_chainage]
    if not seaward_section.empty:
        if seaward_section['elevation'].min() > mlsw and "Profile does not reach MLW elevation" not in flags:
            flags.append("Survey elevation does not meet depth at seaward end")

    # --- Check 3: Count crossings between master and survey ---
    def orientation(p, q, r):
        val = (q[1]-p[1]) * (r[0]-q[0]) - (q[0]-p[0]) * (r[1]-q[1])
        if val == 0: return 0  # collinear
        return 1 if val > 0 else 2  # clockwise / counterclockwise

    def on_segment(p, q, r):
        return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and
                min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))

    def segments_intersect(p1, q1, p2, q2):
        o1 = orientation(p1, q1, p2)
        o2 = orientation(p1, q1, q2)
        o3 = orientation(p2, q2, p1)
        o4 = orientation(p2, q2, q1)

        if o1 != o2 and o3 != o4:
            return True
        if o1 == 0 and on_segment(p1, p2, q1): return True
        if o2 == 0 and on_segment(p1, q2, q1): return True
        if o3 == 0 and on_segment(p2, p1, q2): return True
        if o4 == 0 and on_segment(p2, q1, q2): return True
        return False

    crossings = 0
    for i in range(len(master) - 1):
        m1 = (master.loc[i, 'chainage'], master.loc[i, 'elevation'])
        m2 = (master.loc[i + 1, 'chainage'], master.loc[i + 1, 'elevation'])
        for j in range(len(survey) - 1):
            s1 = (survey.loc[j, 'chainage'], survey.loc[j, 'elevation'])
            s2 = (survey.loc[j + 1, 'chainage'], survey.loc[j + 1, 'elevation'])
            if segments_intersect(m1, m2, s1, s2):
                crossings += 1

    if crossings == 0:
        flags.clear()
        flags.append(f"Survey does not cross master profile anywhere!")
    elif crossings > 2 and "Survey chainage values are not strictly increasing" not in flags:
        flags.append(f"Survey crosses master profile {crossings} times (expected ≤2)")
    # REMOVED: The flawed "elif crossings == 1" check

    diagnostics = {
        "mlsw": mlsw,
        "cutoff_chainage": cutoff_chainage,
        "max_master_chainage": max_master_chainage,
        "max_survey_chainage": max_survey_chainage,
        "crossings": crossings
    }

    flags_set = set(flags)
    flags = list(flags_set)

    return {"flags": flags, "diagnostics": diagnostics}


def find_over_spacing(df, max_spacing=5.0):
    """
    Identify segments in the profile where the spacing between consecutive chainage points exceeds max_spacing.
    Returns a list of tuples indicating the start and end chainage of each over-spaced segment.
    """

    over_spaced_segments = []

    for i in range(len(df) - 1):

        chainage_current = df.iloc[i]['chainage']
        chainage_next = df.iloc[i + 1]['chainage']
        spacing = chainage_next - chainage_current

        if spacing > max_spacing:
            over_spaced_segments.append(df.index[i+1])

    return over_spaced_segments



##MP_PATH = r"C:\Users\darle\AppData\Local\Temp\New_MP_Data\MASTER_6d6D2-13_6d01221_20230222.pkl"
#PROFILE_PATH = r"C:\Users\darle\AppData\Local\Temp\New_Profile_Data\6d6D2-13_6d0122120230222.pkl"
##
##mp_df = pd.read_pickle(MP_PATH)
#profile_df = pd.read_pickle(PROFILE_PATH)
#
#result = find_over_spacing(profile_df, max_spacing=5.0)
#print(result)
