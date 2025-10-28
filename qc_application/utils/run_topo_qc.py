
import logging
import sys

from qc_application.services.topo_qc_service import TopoQCTool


# Assuming your class is here

def run_qc(input_text_files, interim_survey_lines):
    try:
        topo_tool = TopoQCTool(input_text_files, interim_survey_lines)
        logging.info("Running the QC script...")
        topo_tool.run_topo_qc()
    except Exception as e:
        logging.error(f"Error running QC script: {str(e)}")

if __name__ == "__main__":
    input_text_files = sys.argv[1]  # Get input text files from command line
    interim_survey_lines = sys.argv[2]  # Get interim survey lines from command line
    run_qc(input_text_files, interim_survey_lines)
