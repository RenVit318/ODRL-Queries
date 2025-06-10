from fdp_crawler import query_orchestrator

#sparql_query = """SELECT * WHERE {?s ?p ?o}"""
#user = "http://example.org/Bob" # TODO: Include proper authentication here
#purpose = "http://example.org/research"

user_graph_path = 'users/alice.ttl'
query_graph_path = 'questions/query1.ttl'

with open("fdp_uris.txt") as f:
    fdp_uris = [line.strip() for line in f if line.strip()]

query_orchestrator(fdp_uris, user_graph_path, query_graph_path)