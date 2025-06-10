import requests
import rdflib
from rdflib.namespace import DCAT, Namespace
from policy_checker import is_query_allowed

LDP = Namespace("http://www.w3.org/ns/ldp#")
ODRL = Namespace("http://www.w3.org/ns/odrl/2/")

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

def extract_policies(graph, subject):
    policies = []
    for ref in graph.objects(subject, ODRL.hasPolicy):
        if isinstance(ref, rdflib.BNode):
            policies.append((ref, graph))
        else:
            policies.append((ref, None))
    return policies

def crawl_fdp(base_uri):
    fdp = FDP(base_uri)
    g_base = parse_rdf_graph(base_uri)
    fdp.policies.extend(extract_policies(g_base, rdflib.URIRef(base_uri)))

    for cat_uri in g_base.objects(rdflib.URIRef(base_uri), LDP.contains):
        catalog = Catalog(str(cat_uri))
        g_cat = parse_rdf_graph(str(cat_uri))
        catalog.policies.extend(extract_policies(g_cat, cat_uri))

        for ds_uri in g_cat.objects(cat_uri, LDP.contains):
            dataset = Dataset(str(ds_uri))
            g_ds = parse_rdf_graph(str(ds_uri))
            dataset.policies.extend(extract_policies(g_ds, ds_uri))

            for dist_uri in g_ds.objects(ds_uri, LDP.contains):
                distribution = Distribution(str(dist_uri))
                g_dist = parse_rdf_graph(str(dist_uri))
                distribution.policies.extend(extract_policies(g_dist, dist_uri))

                for sparql_endpoint in g_dist.objects(dist_uri, DCAT.accessURL):
                    distribution.sparql_endpoints.append(str(sparql_endpoint))

                dataset.distributions.append(distribution)
            catalog.datasets.append(dataset)
        fdp.catalogs.append(catalog)
    return fdp

def crawl_all_fdps(fdp_uris, query, user, purpose):
    for fdp_uri in fdp_uris:
        print(f"\nProcessing FDP: {fdp_uri}")
        fdp = crawl_fdp(fdp_uri)

        for catalog in fdp.catalogs:
            for dataset in catalog.datasets:
                for distribution in dataset.distributions:
                    for endpoint_url in distribution.sparql_endpoints:
                    #print(f"Checking access for endpoint: {endpoint_url}")

                        hierarchy = [
                            ("FDP", fdp.policies),
                            ("Catalog", catalog.policies),
                            ("Dataset", dataset.policies),
                            ("Distribution", distribution.policies),
                        ]

                        #permission_found = False

                        denied = False
                        allowed = False

                        for level_name, policies in hierarchy:
                            #print(f"Evaluating prohibitions at level: {level_name}")
                            if is_query_allowed(user, query, dataset.uri, purpose, policies, check_prohibition_only=True):
                                print(f"Access denied due to prohibition in policy. At level {level_name}")
                                denied = True
                                break

                        if not denied:
                            for level_name, policies in hierarchy:
                                #print(f"Evaluating permissions at level: {level_name}")
                                if is_query_allowed(user, query, dataset.uri, purpose, policies, check_prohibition_only=False):
                                    print(f"Access granted by policy. At level {level_name}")
                                    allowed = True
                                    break

                        if not denied and not allowed:
                            print("Access denied: No applicable permission found.")  

                        # Old policy handling logic
                        #for level_name, policies in hierarchy:
                        #    print(f"Evaluating permissions at level: {level_name}")
                        #    if is_query_allowed(user, query, dataset.uri, purpose, policies):
                        #        print("Access granted by policy")
                        #        permission_found = True
                        #    else:
                        #        print("Access denied by policy")
                        #    
                        #for level_name, policies in hierarchy:
                        #    print(f"Checking prohibitions at level: {level_name}")
                        #    if is_query_allowed(user, query, dataset.uri, purpose, policies, check_prohibition_only=True):
                        #        print("Access denied due to prohibition in policy.")
                        #        break
                        #    else:
                        #        if permission_found:
                        #            print("Access granted by policy.")
                        #        else:
                        #            print("Access denied: No applicable permission found.")