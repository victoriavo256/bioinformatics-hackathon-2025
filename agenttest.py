import requests
from google import genai
import os
from dotenv import load_dotenv
from typing import Dict, List, Optional

load_dotenv()
GOOGLE_API = os.getenv("GEMINI_API_KEY")


class BioinfoAgent:
    def __init__(self):
        self.query_type = None
        self.query = None
        self.collected_data = {}

    def classify_input(self, query: str) -> str:
        query = query.strip().upper()
        if query.startswith("RS"):
            return "snp"
        else:
            return "gene"

    def collect_myvariant(self, query: str, query_type: str) -> Optional[Dict]:
        try:
            type_param = "variant" if query_type == "snp" else "gene"
            fields = "clinvar,dbnsfp,cadd,cosmic,gnomad,dbsnp,hgvs,gene,refseq,ensembl"
            url = f"https://myvariant.info/v1/{type_param}/{query}?fields={fields}&dotfield=true&size=5"
            response = requests.get(url)
            data = response.json()
            return data
        except Exception as e:
            print(f"MyVariant.info error: {e}")
            return None

    def collect_ensembl_gene(self, gene: str) -> Optional[Dict]:

        try:
            url = f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{gene}"
            headers = {"Content-Type": "application/json"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Ensembl gene lookup error: {e}")
            return None

    def collect_ensembl_variants(self, gene_data: Dict) -> Optional[List[Dict]]:
        if not gene_data:
            return None
        try:
            start = gene_data.get("start")
            end = gene_data.get("end")
            seq = gene_data.get("seq_region_name")

            region = f"{seq}:{start}-{end}"
            url = f"https://rest.ensembl.org/overlap/region/homo_sapiens/{region}"
            params = {"feature": "variation"}
            headers = {"Content-Type": "application/json"}

            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            # dont wanna overwhelm - changeable limit
            return response.json()[:10]
        except Exception as e:
            print(f"Ensembl variants error: {e}")
            return None

    def collect_ensembl_vep(self, snp_id: str) -> Optional[List[Dict]]:
        try:
            url = f"https://rest.ensembl.org/vep/homo_sapiens/id/{snp_id}"
            headers = {"Content-Type": "application/json"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Ensembl VEP error: {e}")
            return None
