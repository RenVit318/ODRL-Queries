import requests
import rdflib
from rdflib import Graph
from rdflib.namespace import DCAT, XSD, Namespace, RDF, FOAF
from .policy_checker import check_policy, deduce_action_from_query
from .query_runner import run_query

LDP = Namespace("http://www.w3.org/ns/ldp#")
ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
EX = Namespace("http://example.org/")

class PolicyAwareResource:
    def __init__(self, uri):
        self.uri = uri
        self.policies = []

class Distribution(PolicyAwareResource):
    def __init__(self, uri):
        super().__init__(uri)
        self.sparql_endpoints = []

class Dataset(PolicyAwareResource):
    def __init__(self, uri):
        super().__init__(uri)
        self.distributions = []

class Catalog(PolicyAwareResource):
    def __init__(self, uri):
        super().__init__(uri)
        self.datasets = []

class FDP(PolicyAwareResource):
    def __init__(self, base_uri):
        super().__init__(base_uri)
        self.catalogs = []

def parse_rdf_graph(url):
    g = rdflib.Graph()
    try:
        response = requests.get(url)
        response.raise_for_status()
        g.parse(data=response.text, format="turtle")
    except Exception as e:
        print(f"Failed to parse RDF from {url}: {e}")
    return g

def extract_policies(graph, subject, include_fallback=False):
    """Find ODRL policies included in an FDP resource file. The fallback checks if any policies are present
    in a resource file if it didn't find any based on the given URI. This is as a fallback in case the 
    self referencing URI doesn't match the given URI."""
    policies = []

    for ref in graph.objects(subject, ODRL.hasPolicy) :
        if isinstance(ref, rdflib.BNode):
            policies.append((ref, graph))
        else:
            policies.append((ref, None))

    if len(policies) == 0 and include_fallback:
        for _, ref in graph.subject_objects(ODRL.hasPolicy):
            if isinstance(ref, rdflib.BNode):
                policies.append((ref, graph))
            else:
                policies.append((ref, None))
        
    return policies

def navigate_down_fdp(graph, uri, nav_predicate=LDP.contains):
    """Find all resources one level below the given FDP resource. Has a built in fallback in case 
    the given link and the link in RDF file are different (sometimes the case in the base URL)"""

    contains = graph.objects(rdflib.URIRef(uri), nav_predicate)
  
    # Is there a better way to get the lengt of a generator without exracting the objects?
    uris = []
    for c in contains:
        uris.append(c)
    if len(uris) > 0:
        return uris

    print('falling back')
    # Fallback
    for _, cat_uri in graph.subject_objects(nav_predicate):
            uris.append(cat_uri)
    return uris




def crawl_fdp(base_uri):
    fdp = FDP(base_uri)
    g_base = parse_rdf_graph(base_uri)
    fdp.policies.extend(extract_policies(g_base, rdflib.URIRef(base_uri), include_fallback=True))

    for cat_uri in navigate_down_fdp(g_base, base_uri):
        print(cat_uri)
        catalog = Catalog(str(cat_uri))
        g_cat = parse_rdf_graph(str(cat_uri))
        catalog.policies.extend(extract_policies(g_cat, cat_uri, include_fallback=True))

        for ds_uri in navigate_down_fdp(g_cat, cat_uri):
            dataset = Dataset(str(ds_uri))
            g_ds = parse_rdf_graph(str(ds_uri))
            dataset.policies.extend(extract_policies(g_ds, ds_uri, include_fallback=True))

            for dist_uri in navigate_down_fdp(g_ds, ds_uri):
                distribution = Distribution(str(dist_uri))
                g_dist = parse_rdf_graph(str(dist_uri))
                distribution.policies.extend(extract_policies(g_dist, dist_uri, include_fallback=True))

                for sparql_endpoint in g_dist.objects(dist_uri, DCAT.accessURL): # Does not have the same fallback
                    distribution.sparql_endpoints.append(str(sparql_endpoint))
                    print(sparql_endpoint)

                dataset.distributions.append(distribution)
            catalog.datasets.append(dataset)
        fdp.catalogs.append(catalog)
    return fdp

def check_if_supported(url):
    """Check what this endpoint is and if it is automatically queryable"""
    supported_keywords = ['allegrograph', 'sparql']
    for kw in supported_keywords:
        if kw in url:
            return True
    return False

def prepare_query(input_user_graph, input_query_graph, input_graph_type):
    if input_graph_type == 'path':
        user_graph  = Graph().parse(input_user_graph,  format="turtle")
        query_graph = Graph().parse(input_query_graph, format="turtle")
    elif input_graph_type == 'graph':
        user_graph = input_user_graph
        query_graph = input_query_graph
    else:
        raise TypeError(f"Unknown input type {input_graph_type}")

    # Find all unique sbj that are ODRL Actions. Use this for extracting attributes
    i = 0
    for query_sbj in query_graph.subjects(RDF.type, ODRL.Action, unique=True):
        i += 1
    if i > 1:
        print(f"WARNING: CURRENTLY ONLY SUPPORTING ONE QUERY. ONLY EXECUTING {query_sbj}")

    query_action = deduce_action_from_query(query_graph.value(query_sbj, EX.queryText))
    if query_action is None:
        print("Could not deduce action from query.")
        return False

    i = 0
    for user in user_graph.subjects(RDF.type, FOAF.Person, unique=True): # Assumes this declaration!
        i += 1
    if i > 1:
        print(f"WARNING: CURRENTLY ONLY SUPPORTING ONE USER PER FILE. USING PROFILE {user}")

    ########
    
    return query_graph, query_sbj, query_action, user_graph, user

def query_orchestrator(fdp_uris, input_user_graph, input_query_graph, input_graph_type):
    """Main function that crawls all provided FDPs, orchestrates policy checking and query execution"""

    # Maybe also put this into one or more objects?
    # Extract all required information for later matching etc. in the right variables
    print("STARTING NEW RUN")
    query_graph, query_sbj, query_action, user_graph, user = prepare_query(input_user_graph, input_query_graph, input_graph_type)
    results = []

    for fdp_uri in fdp_uris:
        print(f"\nProcessing FDP: {fdp_uri}")
        fdp = crawl_fdp(fdp_uri) 
        # This returns an FDP object with nested in it. Each object points down and has a set of policies
        # 1. Catalog
        # 2. Dataset
        # 3. Distribution
        # 4. Endpoints (Assumed to be triplestores)

        # Find each endpoint and do all below code for all defined endpoints
        for catalog in fdp.catalogs:
            for dataset in catalog.datasets:
                for distribution in dataset.distributions:
                    for endpoint_url in distribution.sparql_endpoints:
                        # Check what this endpoint is - only continue if it is a supported Triplestore
                        if not check_if_supported(endpoint_url):
                            print(f"ERROR: URL {endpoint_url} is not supported in the current version.")
                            continue

                        res = {
                            "fdp": fdp_uri,
                            "endpoint": endpoint_url,
                            "allowed": None
                        }

                        #print(f"Checking access for endpoint: {endpoint_url}")

                        hierarchy = [
                            ("FDP", fdp.policies),
                            ("Catalog", catalog.policies),
                            ("Dataset", dataset.policies),
                            ("Distribution", distribution.policies),
                        ]

                        for level_name, policy_refs in hierarchy:

                            #print(f"Evaluating prohibitions at level: {level_name}")
                            #print(policy_refs)
                            #if len(policy_refs) > 0:
                            #    print(policy_refs)
                            match, policy = check_policy(policy_refs, query_graph, query_sbj, query_action, user_graph, user, endpoint_url, mode="prohibition")
                            if match:
                                print(f"Access to {endpoint_url} denied due to prohibition in policy. At level {level_name}")
                                
                                res["allowed"] = False
                                res["reason"] = "Denied by prohibition"
                                res["policy"] = policy
                                results.append(res)

                                break

                        if res["allowed"] is None: 
                            for level_name, policy_refs in hierarchy:
                                #print(f"Evaluating permissions at level: {level_name}")
                                #if len(policy_refs) > 0:
                                #    print(policy_refs)
                                match, policy = check_policy(policy_refs, query_graph, query_sbj, query_action, user_graph, user, endpoint_url, mode="permission")
                                if match:
                                    print(f"Access to {endpoint_url} granted by policy. At level {level_name}")
                                    res["allowed"] = True
                                    res["policy"] = policy
                                    break

                        if res["allowed"] is None:
                            print(f"Access to {endpoint_url} denied: No applicable permission found.")  
                            res["reason"] = "No applicable permission found"
                            results.append(res)


                        elif res["allowed"]:
                            success, response = run_query(query_graph, query_sbj, user_graph, user, endpoint_url)
                            if success:
                                res["data"] = response
                            else:
                                res["allowed"] = False
                                res["reason"] = response
                                res["policy"] = None # Empty this because this policy allowed access, not relevant anymore.
                            results.append(res)


    return results