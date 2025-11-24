def filter_high_impact_variants(variants: list) -> list:

    if not variants:
        return []

    impactful = {
        "stop_gained", "stop_lost", "start_lost",
        "frameshift_variant", "splice_acceptor_variant", "splice_donor_variant",
        "transcript_ablation", "transcript_amplification", "missense_variant", "inframe_deletion", "inframe_insertion",
        "coding_sequence_variant", "protein_altering_variant"
    }
    pathogenic_labels = {"pathogenic", "likely_pathogenic"}
    pathogenic_variants = []
    impactful_variants = []

    for v in variants:

        consequence = v.get("consequence_type", "")
        clin_sig = v.get("clinical_significance", [])

        if any(sig.lower() in pathogenic_labels for sig in clin_sig):
            pathogenic_variants.append(v)
            continue

        if consequence in impactful:
            impactful_variants.append(v)
            continue


    filtered = pathogenic_variants + impactful_variants

    #prevent large list for agent to filter
    return filtered[:100]


def source_mapper(sources):
    res = []
    mapped = {
        "uniprot": "Uniprot",
        "ncbi_snp": "NCBI dbSNP",
        "ncbi_gene": "NCBI Gene",
        "clinicaltables": "NIH",
        "ensembl_vep": "Ensembl",
        "ensembl_gene_and_variants": "Ensembl",
        "myvariant": "MyVariant (ClinVar)",
        "mygene": "MyGene (ClinVar)"
    }

    for source in sources:
        res.append(mapped[source])
    return res