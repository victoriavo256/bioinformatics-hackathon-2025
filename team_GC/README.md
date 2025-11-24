# Team GC

The backend takes a **gene symbol** or an **rsID** and uses public bioinformatics APIs to pull real data.  
The output is cleaned into a predictable JSON structure and summarized using a Gemini model.  
No alignment tools or heavy workflows - just fast lookups and a controlled LLM that summarizes without guessing.

The frontend provides a simple interfaces for users who would like to access information on their gene of
interest quickly. Individuals of all technological skill levels would be able to navigate this application.

---
## Requirements

- Python 3.10+  
- `requests`  
- `google-genai`
- `flask`

Create a Virtual Environment and Install dependencies:

```bash
pip install requests google-genai

pip install Flask

## Running the backend

You’ll need a Gemini API key.

### Option — Environment variable

```bash
export GOOGLE_API_KEY="your_key"

Use setx on windows.

Run the program with this command:
flask --app frontend run
---

## Overview

The backend follows a simple flow:

1. **Classify input**  
   Determine whether the user typed a gene symbol or an rsID.  
   (rsIDs are strictly detected using the `rs` + digits rule.)

2. **Fetch data**  
   - Genes → `MyGene.info`  
   - SNPs → `MyVariant.info`  
   These APIs return inconsistent structures, so the parser handles lists, nested blocks, missing fields, and odd cases.

3. **Normalize data**  
   Raw API results are converted into a consistent JSON object with:
   - `input`  
   - `entity_type`  
   - `species_detected`  
   - `basic_info`  
   - `clinical_significance` (SNPs)  
   - `functional_summary_raw` (genes)  
   - `source_metadata`

4. **Summarize using Gemini**  
   The cleaned JSON is sent to the Gemini model (`models/gemini-2.5-flash`).  
   The model uses a strict system prompt that prevents hallucination and only summarizes data from the JSON we provide.

5. **Return final structured JSON**  
   The final summary includes:
   - a high-level headline  
   - functional role  
   - any disease/trait associations mentioned in the API data  
   - notable details  
   - a list of sources  

---

## Why this backend exists

The goal was not to build a large agent system but a **small, predictable pipeline**:

- APIs are the only source of biological truth  
- The LLM stays in a summarizer role only  
- No fabricated biological claims  
- Easy to debug and extend  
- Lightweight enough for a hackathon project

---


