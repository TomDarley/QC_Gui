import os
from qc_application.utils.check_photo_helper_functions  import *

def check_photos(
    survey_profiles: Set[str],
    survey_completion_date: str,
    input_text_path: str
) -> Dict[str, object]:
    """
    High-level function to check photos for a survey.

    Args:
        survey_profiles: Set of valid survey profile names
        survey_completion_date: Expected completion date as string (YYYYMMDD)
        input_text_path: Path to the survey input text file

    Returns:
        Dictionary of photo check results with any issues found
    """
    photo_check_results: Dict[str, object] = {}

    # Find photos
    found_photos = find_photos(input_text_path)
    if not found_photos:
        logger.warning("No photos found in the directory.")
        return photo_check_results

    logger.info(f"Found photos: {list(found_photos.values())}")

    # Check photo dates
    no_date, incorrect_dates = check_photo_dates(
        photo_dict=found_photos, survey_completion_date=survey_completion_date
    )

    if no_date:
        photo_check_results["Photos_Missing_Date"] = "Photos missing date in filename"
    if incorrect_dates:
        photo_check_results["Photos_Incorrect_Date"] = "Photos incorrect date in filename"

    # If there are issues with dates, skip profile checks
    if photo_check_results:
        logger.info("Photo date issues found, skipping profile checks.")
        return photo_check_results

    # Check photo profiles
    photo_profile_check = check_photo_profiles(found_photos, survey_profiles)
    if photo_profile_check:
        photo_check_results["Photo_Profile_Check"] = photo_profile_check

    return photo_check_results



#d =check_photos({'6d00952','6d00956','6d00960','6d00965'}, survey_completion_date='20211007',
#            input_text_path=r"X:\Data\Survey_Topo\Phase4\TSW02\6d\6d6D2-4_ParSands\6d6D2-4_20211007tip\Batch\6d6D2-4_20211007tip.txt"
#            )
#print(d)