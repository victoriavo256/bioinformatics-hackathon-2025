import main
from flask import Flask, request, render_template
import json

app = Flask(__name__)

def extract_data(json_information):
    extracted_data = {}
    disease_info = ''
    not_details = ''
    sources = ''

    for disease in json_information['disease_associations']:
        disease_info += disease['name'] + ":<br />" + disease['evidence_note'] + "<br />Source: " + disease['evidence_source'] + "<br /><br />"

    for detail in json_information['notable_details']:
        not_details += detail + "<br /><br />"

    for source in json_information['source_list']:
        sources += source + "<br />"

    print(sources)
    extracted_data.update(diseases=disease_info, entity_type=json_information['entity_type'], functional_role=json_information['functional_role'], headline=json_information['headline'], notable_details=not_details, source_list=sources, species=json_information['species'])
    return extracted_data

@app.route("/", methods=["GET", "POST"])
def start():
    if request.method == "POST":
        string = request.form.get("fgene")
        json_info=main.test_in_terminal(string)

        if json_info == 'error':
            return render_template('error_template.html')
        else:
            gene_dict = extract_data(json_info)
            return render_template('results_template.html', gene_dict=gene_dict)
    return render_template("begin_temp.html")
