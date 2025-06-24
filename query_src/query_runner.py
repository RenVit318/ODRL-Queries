from SPARQLWrapper import SPARQLWrapper, JSON
import requests
from rdflib import Namespace

EX = Namespace("http://example.org/")

def run_query(query_graph, query_sbj, user_graph, user, endpoint_url):
    if 'allegrograph' in endpoint_url:
        return run_query_agraph(query_graph, query_sbj, user_graph, user, endpoint_url)
    else:
        print(f"Endpoint {endpoint_url} is not in supported endpoint types!")
        return None
        #raise Warning(f"Endpoint {endpoint_url} is not in supported endpoint types!")

def run_query_agraph(query_graph, query_sbj, user_graph, user, endpoint_url):
    """Send a query to an Agraphs server. Current implementation using requests instead of agraph-python
    because requests is very lightweight."""
    headers = {
        'Accept':"application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        'query': query_graph.value(query_sbj, EX.queryText)
    }
    
    # Storing credentials in the graph is not the final way to go!
    # This should end up being e.g. OAuth or OIDC
    
    username = user_graph.value(user, EX.userName) 
    password = user_graph.value(user, EX.password)
    print("AUTH ",username,password)
    auth = (username, password) if username and password else None
    print(auth)

    response = requests.post(endpoint_url, headers=headers, data=data, auth=auth)

    if response.status_code == 200:
        return True, response.json()["results"]["bindings"]
    else:
        return False, f"SPARQL query failed: {response.status_code}\n{response.text}"


def run_query_TODO(query, dataset_uri):
    sparql = SPARQLWrapper(dataset_uri)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)

    #Hardcoded credentials - do this through a secret config file or through an input box on the website
    sparql.setCredentials('user', 'pass')

    results = sparql.query().convert()
    print(results)


