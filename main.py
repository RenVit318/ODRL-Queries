from fdp_crawler import crawl_all_fdps

sparql_query = """SELECT * WHERE {?s ?p ?o}"""
user = "http://example.org/Bob" # TODO: Include proper authentication here
purpose = "http://example.org/research"

with open("fdp_uris.txt") as f:
    fdp_uris = [line.strip() for line in f if line.strip()]

crawl_all_fdps(fdp_uris, sparql_query, user, purpose)