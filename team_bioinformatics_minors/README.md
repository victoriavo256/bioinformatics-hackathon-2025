## OVERVIEW
This project uses Google Gemini with data from MyGene.info, MyVariant.info, Ensembl, ClinicalTable, NCBI, and Uniprot to generate concise insight summaries on any given gene ID or SNP. This tool was designed for researchers who want fast insight into a gene or variant’s functional role, disease association, and known variants.

## GETTING STARTED
Follow the steps below to run the app locally.

1. Clone the github repository
git clone https://github.com/victoriavo256/bioinformatics-hackathon-2025.git
cd bioinformatics-hackathon-2025

2. (Optional) Create a virtual environment and activate it
python -m venv venv

TO ACTIVATE ON WINDOWS: venv\Scripts\activate
TO ACTIVATE ON MACOS/ LINUX: source venv/bin/activate

3. Install dependencies in requirements.txt
pip install -r requirements.txt

4. Create a Google Gemini API key and store it in a .env file as the following:
GEMINI_API_KEY = <YOUR_API_KEY>

4. Run the streamlit frontend (this will open the app on a localhost)
streamlit run main.py

5. Enter your valid gene ID or SNP string into the input box and click Summarize. Wait a few moments while data is fetched and the AI summary is generated.

6. If you'd like to save a copy of the summary for future reference, click on the Download AI Summary button at the bottom of the page! This will save a .txt file to your device.
