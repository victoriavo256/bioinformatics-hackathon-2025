import requests
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from typing import Dict, List, Optional, Any
import json
from helpers import filter_high_impact_variants, source_mapper

load_dotenv()
GOOGLE_API = os.getenv("GEMINI_API_KEY")

class BioinfoAgent:
    def __init__(self):
        self.query_type = None
        self.query = None
        self.collected_data = {}
        if not GOOGLE_API:
             print("Error: GEMINI_API_KEY not found. Please check your .env file.")
             self.client = None
        else:
             self.client = genai.Client(api_key=GOOGLE_API)

    def classify_input(self, query: str) -> str:
        query = query.strip().upper()
        if query.startswith("RS"):
            return "snp"
        else:
            return "gene"
        
    def collect_mygene(self, gene: str):

        try:
            # get gene id
            url = "https://mygene.info/v3/query"
            params = {
                "q": gene,
                "species": "human",
                "size": 1,
                "fields": "entrezgene,ensembl.gene,symbol,name"
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "hits" not in data or len(data["hits"]) == 0:
                print("No gene found.")
                return None

            gene_id = data["hits"][0]["_id"]

            # use gene id to get full gene info
            gene_url = f"https://mygene.info/v3/gene/{gene_id}"
            fetch_params = {
                "fields": "symbol,name,summary,genomic_pos_hg38,pathway,clinvar"
            }

            response2 = requests.get(gene_url, params=fetch_params)
            response2.raise_for_status()
            data2 = response2.json()
            return data2
        except requests.exceptions.JSONDecodeError as e:
            print(f"MyGene.info JSON error: {e} - Response: {response.text[:200]}")
            return None
        except Exception as e:
            print(f"MyGene.info error: {e}")
            return None
    
    def collect_myvariant(self, query: str) -> Optional[Dict]:
        try:

            fields = "clinvar,dbnsfp,cadd,cosmic,gnomad,dbsnp,hgvs,gene,refseq,ensembl,exac"
            url = f"https://myvariant.info/v1/variant/{query}?fields={fields}&dotfield=true&size=5"
            response = requests.get(url, timeout=10)
            response.raise_for_status() 

            if response.text.strip():
                data = response.json()
                return data
            else:
                print(f"MyVariant.info: Empty response for {query}")
                return None
        except requests.exceptions.JSONDecodeError as e:
            print(f"MyVariant.info JSON error: {e} - Response: {response.text[:200]}")
            return None
        except Exception as e:
            print(f"MyVariant.info error: {e}")
            return None
        
    def collect_ensembl_gene(self, gene: str) -> Optional[Dict]:
        try:
            url = f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{gene}"
            headers = {"Content-Type": "application/json"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()["id"]
        except Exception as e:
            print(f"Ensembl gene lookup error: {e}")
            return None

    def collect_ensembl_variants(self, gene_data: Dict) -> Optional[List[Dict]]:
        if not gene_data:
            return None
        try:

            url = f"https://rest.ensembl.org/overlap/id/{gene_data}?feature=variation"
            params = {"feature": "variation"}
            headers = {"Content-Type": "application/json"}

            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            # dont wanna overwhelm - changeable limit
            return response.json()
        except Exception as e:
            print(f"Ensembl variants error: {e}")
            return None
        
    def collect_ensembl_gene_and_variants(self, gene: str):
        ensembl_gene = self.collect_ensembl_gene(gene)
        if not ensembl_gene:
            return {"ensembl_gene": None, "ensembl_variants": None}
        variants = self.collect_ensembl_variants(ensembl_gene) or []
        filter = filter_high_impact_variants(variants)
        return filter
    
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
    
    def collect_clinicaltables(self, snp_id: str) -> Optional[Dict]:
        try:
            url = "https://clinicaltables.nlm.nih.gov/api/snps/v3/search"
            params = {"terms": snp_id}

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if len(data) >= 4 and data[3]:
                table = data[3]
                for row in table:
                    if row[0] == snp_id:
                        return {
                            "rsid": row[0],
                            "chromosome": row[1],
                            "position": row[2],
                            "alleles": row[3],
                            "gene": row[4] if len(row) > 4 and row[4] else None
                        }
            return None
        except Exception as e:
            print(f"ClinicalTables error: {e}")
            return None

    #https://www.ncbi.nlm.nih.gov/books/NBK25500/
    def collect_ncbi_gene(self, gene_symbol: str) -> Optional[Dict]:
        try:
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            #AND Homo sapiens[Organism]
            search_params = {
                "db": "gene",
                "term": f"{gene_symbol}[Gene Name] AND Homo sapiens[Organism]",
                "retmode": "json",
                "retmax": "1"
            }

            search_response = requests.get(search_url, params=search_params, timeout=10)
            search_response.raise_for_status()
            search_data = search_response.json()

            if "esearchresult" not in search_data or not search_data["esearchresult"].get("idlist"):
                return None

            gene_id = search_data["esearchresult"]["idlist"][0]

            summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            summary_params = {
                "db": "gene",
                "id": gene_id,
                "retmode": "json"
            }

            summary_response = requests.get(summary_url, params=summary_params, timeout=10)
            summary_response.raise_for_status()
            summary_data = summary_response.json()

            if "result" in summary_data and gene_id in summary_data["result"]:
                return summary_data["result"][gene_id]

            return None
        except Exception as e:
            print(f"NCBI Gene error: {e}")
            return None

    def collect_ncbi_snp(self, snp_id: str) -> Optional[Dict]:
        try:
            id = snp_id.lower().replace("rs", "")

            url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            params = {
                "db": "snp",
                "id": id,
                "retmode": "json"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "result" in data and id in data["result"]:
                return data["result"][id]

            return None
        except Exception as e:
            print(f"ncbi dbSNP error: {e}")
            return None

    def collect_uniprot(self, gene_symbol: str) -> Optional[Dict]:
        try:
            url = "https://rest.uniprot.org/uniprotkb/search"
            params = {
                "query": f"gene:{gene_symbol} AND organism_id:9606",
                "format": "json",
                "size": "1"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "results" in data and len(data["results"]) > 0:
                return data["results"][0]

            return None
        except Exception as e:
            print(f"uniport error: {e}")
            return None
    
    def _make_tool_decl(self, name: str, params: Dict) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=name,
            description=params.get("description", ""),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties=params.get("properties", {}),
                required=params.get("required", []),
            ),
        )

    def _run_tool_execution(self, query: str) -> Dict[str, Any]:
        if not self.client:
            return {"error": "API client not initialized"}

        query_type = self.classify_input(query)
        fn_map = {
            "collect_ensembl_gene_and_variants": self.collect_ensembl_gene_and_variants,
            "collect_ncbi_gene": self.collect_ncbi_gene,
            "collect_uniprot": self.collect_uniprot,
            "collect_mygene": self.collect_mygene,

            "collect_clinicaltables": self.collect_clinicaltables,
            "collect_ensembl_vep": self.collect_ensembl_vep,
            "collect_ncbi_snp": self.collect_ncbi_snp,
            "collect_myvariant": self.collect_myvariant,
        }

        gene_tool_decls = [
            self._make_tool_decl("collect_ensembl_gene_and_variants", {
            "description": "Fetch Ensembl gene metadata and the overlapping variants for the given gene symbol.",
            "properties": {"gene": {"type": "string"}},
            "required": ["gene"],
            }),
            self._make_tool_decl("collect_ncbi_gene", {
                "description": "Get NCBI Gene summary for a human gene symbol.",
                "properties": {"gene_symbol": {"type": "string"}},
                "required": ["gene_symbol"],
            }),
            self._make_tool_decl("collect_uniprot", {
                "description": "Get UniProt entry for a human gene symbol.",
                "properties": {"gene_symbol": {"type": "string"}},
                "required": ["gene_symbol"],
            }),
            self._make_tool_decl("collect_mygene", {
                "description": "Get MyGene.info details for a human gene symbol.",
                "properties": {"gene": {"type": "string"}},
                "required": ["gene"],
            }),
        ]
        snp_tool_decls = [
            self._make_tool_decl("collect_clinicaltables", {
                "description": "Get basic rsID info (chr, pos, alleles).",
                "properties": {"snp_id": {"type": "string"}},
                "required": ["snp_id"],
            }),
            self._make_tool_decl("collect_ensembl_vep", {
                "description": "Get VEP consequence for an rsID.",
                "properties": {"snp_id": {"type": "string"}},
                "required": ["snp_id"],
            }),
            self._make_tool_decl("collect_ncbi_snp", {
                "description": "Get NCBI dbSNP summary for an rsID.",
                "properties": {"snp_id": {"type": "string"}},
                "required": ["snp_id"],
            }),
            self._make_tool_decl("collect_myvariant", {
                "description": "Get MyVariant.info details for an rsID.",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            }),
        ]

        tool = types.Tool(function_declarations=(gene_tool_decls if query_type == "gene" else snp_tool_decls))

        planner_prompt = (
            f"You are a Bioinformatic Data Collector. Use the provided functions to gather ALL raw data for the {query_type.upper()}.\n"
            f"- Respond ONLY with function calls until you have everything you can get.\n"
            f"- When done, return ONE JSON object: "
            f'{{"query":"{query}","type":"{query_type}","sources":{{...}}}} and STOP.'
        )

        contents = [
            types.Content(role="user", parts=[types.Part.from_text(text=f"Collect all data for {query}")])
        ]

        collected = {}
        for attempt in range(3):
            resp = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=planner_prompt,
                    tools=[tool],
                ),

            )

            function_calls = []
            for cand in resp.candidates:
                if not cand.content or not cand.content.parts:
                    continue
                for p in cand.content.parts:
                    if getattr(p, "function_call", None):
                        function_calls.append(p.function_call)

            if function_calls:
                tool_parts = []
                for fc in function_calls:
                    name = fc.name
                    args = dict(fc.args)
                    py_fn = fn_map.get(name)
                    if not py_fn:
                        tool_parts.append(
                            types.Part.from_function_response(
                                name=name,
                                response={"content": [{"text": json.dumps({"error": "tool not available"})}]},
                            )
                        )
                        continue

                    try:
                        if name == "collect_ensembl_gene_and_variants":
                            out = py_fn(args.get("gene"))
                        elif name in ("collect_ncbi_gene", "collect_uniprot"):
                            out = py_fn(args.get("gene_symbol"))
                        elif name in ("collect_mygene"):
                            out = py_fn(args.get("gene"))
                        elif name in ("collect_clinicaltables", "collect_ensembl_vep", "collect_ncbi_snp"):
                            out = py_fn(args.get("snp_id"))
                        elif name == "collect_myvariant":
                            out = py_fn(args.get("query"))
                        else:
                            out = py_fn(**args)
                    except Exception as e:
                        out = {"error": str(e)}

                    collected[name.replace("collect_", "")] = out
                    tool_parts.append(
                        types.Part.from_function_response(
                            name=name,
                            response={"content": [{"text": json.dumps(out if out is not None else {"result": "None"})}]},
                        )
                    )


                contents.append(resp.candidates[0].content)
                contents.append(types.Content(role="tool", parts=tool_parts))
                continue

            final_text = resp.text or ""
            try:
                parsed = json.loads(final_text)
                return parsed
            except Exception:
                break

        return {"query": query, "type": query_type, "sources": collected}
    
    def ai_summary(self, data: Dict[str, Any]) -> str:
        if not self.client:
             return "API Client not initialized."

        data_sources_json = json.dumps(data['sources'], indent=2)
        
        prompt = f"""You are a clinical data aggregation system analyzing bioinformatics API responses.

            CRITICAL INSTRUCTIONS - READ CAREFULLY:
            1. You MUST ONLY use information explicitly present in the DATA section below
            2. DO NOT use your training knowledge about genes, proteins, or diseases
            3. If data seems incomplete or contradictory, report it honestly
            4. Cite the specific data source for each claim (e.g., "According to NCBI Gene...")
            5. Keep your summaries concise. Each subsection should be at most 2-3 paragraphs.


            Your role is to SYNTHESIZE what the APIs returned, not to supplement with external knowledge.

            DATA FROM MULTIPLE SOURCES (these are the ONLY sources you can use):
            {data_sources_json}

            Generate a concise, structured clinical insight summary following this exact format:

            # {data['query']} - {'Gene' if data['type'] == 'gene' else 'SNP'} Summary

            ## 1. Functional Role
            Describe the biological function, pathway involvement, and molecular mechanisms.
            IMPORTANT: Cite the source for each statement (e.g., "UniProt reports...", "NCBI Gene describes...").
            If no functional data is available, state: "Functional data not available from queried sources."

            ## 2. Disease Associations
            List known disease associations with clinical significance levels (if available).
            IMPORTANT: Only include diseases mentioned in the provided data. Cite sources.
            Include:
            
            Disease name
            Strength of association


            ## 3. Known Variants and Population Frequency
            {'For the gene, highlight the most clinically significant variants with their population frequencies' if data['type'] == 'gene' else 'Describe this SNP variant with detailed population frequency analysis'}:

            Variant details (genomic coordinates, alleles, transcript impact)
            Functional impact (missense, nonsense, frameshift, etc.)
            Limit to listing 3 variants.


            ## 4. Clinical Relevance
            Provide actionable insights for researchers or clinicians:
            
            Diagnostic value
            Therapeutic implications
            Screening recommendations

        """
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=prompt,

            )
            return response.text
        except Exception as e:
            return f"error generating summary: {e}"
    
    def run(self, query: str) -> Dict[str, Any]:
        print("running")
        collected_data = self._run_tool_execution(query)
        print("done collecting")
        if "error" in collected_data:
            return collected_data
        
        summary = self.ai_summary(collected_data)

        sources = source_mapper(list(collected_data["sources"].keys()))
        result = {
            "query": query,
            "type": collected_data["type"],
            "data_sources_used": sources,
            "raw_data": collected_data["sources"],
            "ai_summary": summary
        }

        return result


