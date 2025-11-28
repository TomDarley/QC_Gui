
import sys
import logging

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
        logging.info(f"{result}")

        if result:
            logging.info("QC script completed successfully.")
            return True
        else:
            logging.error("QC script encountered errors.")
            return False

    except Exception as e:
        logging.error(f"Error running QC script: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        input_text_files = sys.argv[1]
        interim_survey_lines = sys.argv[2]

        success = run_qc(input_text_files, interim_survey_lines)
        sys.exit(0 if success else 1)

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        sys.exit(1)
