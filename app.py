import streamlit as st
from query_src.fdp_crawler import query_orchestrator 
import pandas as pd
import rdflib
import io

st.set_page_config(page_title="ODRL-FDP Query Evaluator", layout="wide")
st.title("🔍 FDP Access Evaluator via ODRL Policies")

# --- FDP Inputs ---
st.header("1. FDP Source URIs")


with open("fdp_uris.txt") as f:
    default_fdp_uris = [line.strip() for line in f if line.strip()]

fdp_input_method = st.radio("Select input method:", ["Manual input", "Upload file", "Use defaults"])

fdp_uris = []
if fdp_input_method == "Manual input":
    fdp_text = st.text_area("Enter one or more FDP URIs (one per line)")
    fdp_uris = [line.strip() for line in fdp_text.splitlines() if line.strip()]
elif fdp_input_method == "Upload file":
    uploaded_file = st.file_uploader("Upload a text file with FDP URIs")
    if uploaded_file is not None:
        fdp_uris = [line.strip() for line in uploaded_file.read().decode("utf-8").splitlines() if line.strip()]
else:
    fdp_uris = default_fdp_uris

st.markdown(f"**Loaded {len(fdp_uris)} FDP URIs**")
if fdp_uris:
    selected_fdp = st.selectbox("View a loaded FDP URI:", options=fdp_uris)

# --- Query & Metadata ---
st.header("2. SPARQL Query & Parameters")
default_query = """SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 25"""
sparql_query = st.text_area("Enter your SPARQL query", value=default_query, height=200)
query_purpose = st.text_input("Purpose of the query (e.g. 'research', 'analysis')")

# --- User Graph ---
st.header("3. Upload User Graph")
user_graph = rdflib.Graph()
user_choice = st.radio("Select user:", ["Default: Alice", "Default: Bob", "Upload file"])

if user_choice == "Default: Alice":
    user_graph.parse('users/alice.ttl')
    #try:
    #    url = "https://raw.githubusercontent.com/example/demo-user-graphs/main/alice.ttl"  # Replace with actual URL
    #    data = requests.get(url).text
    #    user_graph.parse(data=data, format="turtle")
    #    st.success(f"Loaded standard user graph with {len(user_graph)} triples.")
    #except Exception as e:
    #    st.error(f"Failed to load default user graph: {e}")
elif user_choice == "Default: Bob":
    user_graph.parse('users/bob.ttl')
else:
    user_graph_file = st.file_uploader("Upload your user RDF graph (.ttl, .rdf, .jsonld)", type=["ttl", "rdf", "jsonld"])
    if user_graph_file is not None:
        try:
            user_graph.parse(file=user_graph_file, format=rdflib.util.guess_format(user_graph_file.name))
            st.success(f"Loaded user graph with {len(user_graph)} triples.")
        except Exception as e:
            st.error(f"Failed to parse RDF file: {e}")

# --- Encode Query as RDF Graph ---
def build_query_graph(query_text, purpose_text):
    EX = rdflib.Namespace("http://example.org/")
    ODRL = rdflib.Namespace("http://www.w3.org/ns/odrl/2/")
    
    g = rdflib.Graph()
    g.bind("ex", EX)
    g.bind("odrl", ODRL)

    query_node = EX["Q1"]
    g.add((query_node, rdflib.RDF.type, ODRL.Action))
    g.add((query_node, EX.queryText, rdflib.Literal(query_text)))
    if purpose_text:
        g.add((query_node, ODRL.purpose, EX[purpose_text]))

    return g

# --- Evaluate ---
st.header("4. Evaluate")
if st.button("Evaluate Query"):
    if not sparql_query or not fdp_uris or user_graph is None:
        st.warning("Please provide all required inputs: FDP URIs, query, and user graph.")
    else:
        with st.spinner("Evaluating query..."):
            try:
                query_graph = build_query_graph(sparql_query, query_purpose)
                results = query_orchestrator(
                    fdp_uris=fdp_uris,
                    input_user_graph=user_graph,
                    input_query_graph=query_graph,
                    input_graph_type = 'graph'                         
                )

                #st.write('Finshed the program')
                #st.write(results)
                print(len(results))

                if not isinstance(results, list):
                    st.error("❌ Unexpected response format from evaluate_query. Expected a list of results.")
                elif len(results) == 0:
                    st.warning("No FDPs returned any results or all queries were denied.")
                else:
                    for res in results:
                        fdp_text = res.get("fdp", "[Unknown FDP]")
                        #endpoint_text = res.get("endpoint")
                        st.subheader(f"FDP: {fdp_text}")
                        st.write(f"Endpoint: {res.get('endpoint')}")

                        if res.get("allowed"):
                            st.success("✅ Query Permitted")
                            allowed_by = res.get('policy', 'Unknown policy.')
                            st.markdown(f"**Allowed by:** {allowed_by}")
                            if res.get("data") is None:
                                st.error(f"Failed to get data. {res.get('error', 'Unkown error. Probably occured at the triplestore.')}")
                            else:
                                st.json(res.get("data", {}))
                        else:
                            st.error("❌ Query Denied")
                            st.markdown(f"**Reason:** {res.get('reason', 'No reason provided.')}")
                            denied_by = res.get('policy', False)
                            if denied_by:
                                st.markdown(f"**Denied by:** {denied_by}")

            except Exception as e:
                st.exception(e)
