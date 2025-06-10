from SPARQLWrapper import SPARQLWrapper, JSON

def run_query(query, dataset_uri):
    print("EXECUTING QUERY CODE TO BE IMPLEMENTED")

def run_query_TODO(query, dataset_uri):
    sparql = SPARQLWrapper(dataset_uri)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)

    #Hardcoded credentials - do this through a secret config file or through an input box on the website
    sparql.setCredentials('admin', 'vodan')

    results = sparql.query().convert()
    print(results)