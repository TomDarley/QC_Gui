import json
import logging
import sys

try:
    from qc_application.services.topo_qc_service import TopoQCTool
except ImportError as e:
    logging.error(f"Failed to import TopoQCTool: {str(e)}")
    raise


def run_qc(input_text_files, interim_survey_lines):
    try:
        topo_tool = TopoQCTool(input_text_files, interim_survey_lines)
        logging.info("Running the QC script...")
        result = topo_tool.run_topo_qc()

        # Convert SurveyResult objects to dicts
        result_dict = {
            "success_count": result["success_count"],
            "failed_count": result["failed_count"],
            "total": result["total"],
            "results": [
                {
                    "file_path": r.file_path,
                    "survey_unit": r.survey_unit,
                    "success": r.success,
                    "error_message": r.error_message,
                    "stage": r.stage,
                }
                for r in result["results"]
            ]
        }

        # Print JSON for GUI to parse
        print(json.dumps(result_dict))
        return True

    except Exception as e:
        logging.error(f"Error running QC script: {str(e)}")
        # Emit a JSON indicating failure so GUI can handle it
        print(json.dumps({
            "success_count": 0,
            "failed_count": 1,
            "total": 0,
            "results": [{"file_path": "", "survey_unit": "", "success": False, "error_message": str(e), "stage": "run_qc"}]
        }))
        return False


if __name__ == "__main__":
    try:
        input_text_files = sys.argv[1]
        interim_survey_lines = sys.argv[2]

        success = run_qc(input_text_files, interim_survey_lines)
        sys.exit(0 if success else 1)

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        # Print JSON error for GUI
        print(json.dumps({
            "success_count": 0,
            "failed_count": 1,
            "total": 0,
            "results": [{"file_path": "", "survey_unit": "", "success": False, "error_message": str(e), "stage": "main"}]
        }))
        sys.exit(1)
