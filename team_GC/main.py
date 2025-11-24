import os
import json
from typing import Any, Dict, List

import requests
from google import genai
from google.genai import types


def classify_user_input(raw_text):
    """
    This function is checking whether the input looks like a gene symbol or an rsID SNP.
    """
    text = raw_text.strip()

    if text.lower().startswith("rs") and text[2:].isdigit():
        return "snp"

    if " " not in text and text.replace("_", "").isalnum():
        return "gene"

    return "unknown"


def get_gene_data_from_mygene(gene_query):
    """
    This function is calling MyGene.info and is returning a normalized gene dict.
    """
    url = "https://mygene.info/v3/query"
    params = {
        "q": gene_query,
        "fields": "symbol,name,entrezgene,ensembl.gene,summary,genomic_pos,map_location,alias,taxid",
        "size": 5,
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    hits = data.get("hits", [])
    if not hits:
        raise ValueError(f"No gene hits found for query: {gene_query}")

    gene_hit = hits[0]

    genomic_pos = gene_hit.get("genomic_pos") or {}
    if isinstance(genomic_pos, list) and genomic_pos:
        genomic_pos = genomic_pos[0]

    if isinstance(genomic_pos, dict):
        chrom = genomic_pos.get("chr")
        start = genomic_pos.get("start")
        end = genomic_pos.get("end")
        strand = genomic_pos.get("strand")
    else:
        chrom = start = end = strand = None

    ensembl_block = gene_hit.get("ensembl") or {}
    if isinstance(ensembl_block, list) and ensembl_block:
        ensembl_block = ensembl_block[0]

    normalized_gene = {
        "input": gene_query,
        "entity_type": "gene",
        "species_detected": gene_hit.get("taxid"),
        "basic_info": {
            "symbol": gene_hit.get("symbol"),
            "name": gene_hit.get("name"),
            "entrez_id": gene_hit.get("entrezgene"),
            "ensembl_id": ensembl_block.get("gene") if isinstance(ensembl_block, dict) else None,
            "map_location": gene_hit.get("map_location"),
            "genomic_location": {
                "chromosome": chrom,
                "start": start,
                "end": end,
                "strand": strand,
            },
            "aliases": gene_hit.get("alias", []),
        },
        "functional_summary_raw": gene_hit.get("summary"),
        # keeping these keys so the schema is shared with SNPs
        "clinical_significance": [],
        "trait_associations": [],
        "source_metadata": {
            "primary_source": "MyGene.info",
            "mygene_query_url": response.url,
        },
    }

    return normalized_gene


def get_snp_data_from_myvariant(rs_id):
    """
    This function is calling MyVariant.info for an rsID and is returning a normalized SNP dict.
    """
    url = f"https://myvariant.info/v1/variant/{rs_id}"
    resp = requests.get(url, timeout=10)

    if resp.status_code == 404:
        raise ValueError(f"No SNP found for query: {rs_id}")

    resp.raise_for_status()
    raw_data = resp.json()

    # MyVariant may return:
    # - a dict (normal variant record)
    # - a list of records (ambiguous query)
    # - an empty list (no data)
    if isinstance(raw_data, list):
        if not raw_data:
            raise ValueError(f"No SNP found for query: {rs_id}")
        # picking the first variant in the list
        raw_data = raw_data[0]

    dbsnp_block = raw_data.get("dbsnp") or {}
    if not isinstance(dbsnp_block, dict):
        dbsnp_block = {}

    hg19_block = dbsnp_block.get("hg19") or {}
    if isinstance(hg19_block, list) and hg19_block:
        hg19_block = hg19_block[0]
    if not isinstance(hg19_block, dict):
        hg19_block = {}

    gene_block = dbsnp_block.get("gene") or {}
    gene_symbol = None
    if isinstance(gene_block, dict):
        gene_symbol = gene_block.get("symbol")
    elif isinstance(gene_block, list) and gene_block:
        first_gene = gene_block[0]
        if isinstance(first_gene, dict):
            gene_symbol = first_gene.get("symbol")

    clinvar_block = raw_data.get("clinvar") or {}
    if not isinstance(clinvar_block, dict):
        clinvar_block = {}

    clinical_significance_value = clinvar_block.get("clinical_significance")
    condition_names = []

    rcv_entries = clinvar_block.get("rcv") or []
    if isinstance(rcv_entries, dict):
        rcv_entries = [rcv_entries]
    elif not isinstance(rcv_entries, list):
        rcv_entries = []

    for rcv_item in rcv_entries:
        if not isinstance(rcv_item, dict):
            continue
        conditions = rcv_item.get("conditions") or []
        if isinstance(conditions, dict):
            conditions = [conditions]
        elif not isinstance(conditions, list):
            conditions = []
        for cond in conditions:
            if isinstance(cond, dict):
                name = cond.get("name")
                if name:
                    condition_names.append(name)

    clinical_significance_list = []
    if clinical_significance_value or condition_names:
        clinical_significance_list.append(
            {
                "source": "ClinVar",
                "value": clinical_significance_value,
                "conditions": sorted(set(condition_names)),
            }
        )

    normalized_snp = {
        "input": rs_id,
        "entity_type": "snp",
        "species_detected": "Homo sapiens",
        "basic_info": {
            "rsid": dbsnp_block.get("rsid"),
            "chromosome": dbsnp_block.get("chrom"),
            "position_hg19": hg19_block.get("start"),
            "ref_allele": dbsnp_block.get("ref"),
            "alt_allele": dbsnp_block.get("alt"),
            "gene_symbol": gene_symbol,
        },
        "clinical_significance": clinical_significance_list,
        "trait_associations": [],
        "functional_summary_raw": None,
        "source_metadata": {
            "primary_source": "MyVariant.info",
            "myvariant_url": resp.url,
        },
    }

    return normalized_snp


#Configuring LLM

SUMMARY_SYSTEM_PROMPT = """
You are a bioinformatics assistant that summarizes structured gene or variant information for researchers and clinicians.

You will receive a single JSON object describing either:
- a gene, or
- a single nucleotide polymorphism (SNP).

This JSON already contains the only facts you are allowed to use. You MUST NOT invent additional biology, diseases, pathways, or interpretations that are not explicitly present in the JSON input.

Your tasks:
1. Identify whether the entity is a gene or SNP from the "entity_type" field.
2. Produce a concise, clinically and biologically useful insight summary based ONLY on the input JSON.
3. If information is missing or unclear, say "unknown" rather than guessing.
4. Keep the output short, structured, and ready to be rendered in a UI.

You MUST respond with valid JSON only, following this exact schema:

{
  "input": "string (echo from input JSON 'input')",
  "entity_type": "gene or snp",
  "species": "string or 'unknown'" (if you see 9606 as taxid then it is homo sapiens),
  "headline": "1-2 sentences: high-level summary of what this gene or SNP is, using only provided data.",
  "functional_role": "For genes: short paragraph on function or processes, using only provided summary or fields. For SNPs: state whether any functional/clinical impact is reported, or 'unknown'.",
  "disease_associations": [
    {
      "name": "disease or trait name, or 'unknown'",
      "evidence_source": "e.g., ClinVar, GWAS Catalog, MyVariant.info, or 'unknown'",
      "evidence_note": "one short sentence summarizing the evidence from the input JSON"
    }
  ],
  "notable_details": [
    "Short bullet-style statement 1 based only on input JSON",
    "Short bullet-style statement 2 based only on input JSON"
  ],
  "source_list": [
    "Short list of database/source names you can see in the input JSON (e.g. MyGene.info, Ensembl, MyVariant.info, ClinVar, GWAS Catalog)."
  ]
}

Rules:
- Do NOT add external citations.
- Do NOT mention studies, diseases, or functions that are not clearly implied by the input JSON.
- If there are no disease or trait associations in the input, return an empty list for 'disease_associations'.
- If there are no notable details beyond basic ID and location, return an empty list for 'notable_details'.
"""


def build_gemini_client():
    """
    This function is creating a Gemini client using the google-genai SDK.
    """
    api_key = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))

    if not api_key:
        raise RuntimeError("Gemini API key is missing. Set GOOGLE_API_KEY or GEMINI_API_KEY in your environment.")

    client = genai.Client(api_key=api_key)
    return client


def summarize_bio_entity(normalized_entity, client):
    """
    This function is sending the normalized entity to Gemini and is returning the parsed JSON summary.
    """
    entity_text = json.dumps(normalized_entity)

    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=[entity_text],
        config=types.GenerateContentConfig(
            system_instruction=SUMMARY_SYSTEM_PROMPT.strip(),
            response_mime_type="application/json",
        ),
    )

    summary_text = response.text.strip()
    return json.loads(summary_text)



def test_in_terminal(user_query):
    '''
    user_query = input("Enter a gene symbol or SNP rsID (e.g., TP53 or rs7412): ").strip()
    if not user_query:
        print("Empty input, exiting.")
        return
    '''
    kind = classify_user_input(user_query)
    if kind == "unknown":
        print("Could not classify input as gene or SNP.")
        return 'error'

    try:
        if kind == "gene":
            normalized_entity = get_gene_data_from_mygene(user_query)
        else:
            normalized_entity = get_snp_data_from_myvariant(user_query)
    except Exception as fetch_error:
        print(f"Error while fetching data: {fetch_error}")
        return 'error'

    try:
        client = build_gemini_client()
        summary = summarize_bio_entity(normalized_entity, client)
    except Exception as llm_error:
        print(f"Error during LLM summarization: {llm_error}")
        print("Here is the normalized JSON for debugging:")
        print(json.dumps(normalized_entity, indent=2))
        return 'error'


    print("\n------------- LLM summary ---------------")
    print(json.dumps(summary, indent=2))
    print("\n------------- Normalized JSON ---------------")
    print(json.dumps(normalized_entity, indent=2))

    return summary
    


if __name__ == "__main__":
    test_in_terminal()
