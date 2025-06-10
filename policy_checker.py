from rdflib import Graph, Namespace, URIRef, BNode, RDF, FOAF
import rdflib
from urllib.parse import urldefrag

ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
EX = Namespace("http://example.org/")

#Immediate thoughts
# Very simple checker on user - graph level
# We can maybe get the action from the SPARQL query for now that should be relatively straight forward. The query is not used at all right now for analysis.
# Very inefficient, parses all permssions. Fine for now
# Also should include prohibitions, e.g. first check prohibitions, if nothing then move on to permissions.

def deduce_action_from_query(query):
    """Very simple action checker based on the SPARQL keyword used."""
    for line in query.strip().splitlines():
        stripped = line.strip().lower()
        if (not stripped or 
            stripped.startswith("prefix") or 
            stripped.startswith("base")):
            continue # These are empty lines or URI PREFIX lines
        if (stripped.startswith("select") or 
            stripped.startswith("ask") or 
            stripped.startswith("construct") or
            stripped.startswith("describe")):
            return ODRL.read
        elif (stripped.startswith("insert") or
              stripped.startswith("delete")):
            return ODRL.write
        break
    
    return None


def load_policy_graph(policy_refs):
    g = Graph()
    loaded_uris = set()
    for ref, source_graph in policy_refs:
        if isinstance(ref, URIRef):
            base_uri, _ = urldefrag(ref)
            if base_uri not in loaded_uris:
                try:
                    g.parse(base_uri, format="turtle")
                    loaded_uris.add(base_uri)
                except Exception as e:
                    print(f"Warning: Failed to load policy from {base_uri}: {e}")
        elif isinstance(ref, BNode):
            for triple in source_graph.triples((ref, None, None)):
                g.add(triple)
    return g


def matches_constraints(policy_graph, rule, query_graph, query_sbj, user_graph, user):
    matched = False
    for constraint in policy_graph.objects(rule, ODRL.constraint):
        # Assume the constraint is described as left = predicate, right = object
        left = policy_graph.value(constraint, ODRL.leftOperand)
        op = policy_graph.value(constraint, ODRL.operator)
        right = policy_graph.value(constraint, ODRL.rightOperand)

        print(left, op, right)
        if op == ODRL.eq:
            # Search for the predicate in both the query graph and the user graph
            print(query_graph.value(query_sbj, left))
            if query_graph.value(query_sbj, left) == right:
                matched = True
            elif user_graph.value(user, left) == right:
                matched = True 
        else:
            print(f"WARNING: ODRL Operator {ODRL.eq} not yet supported.")
    return matched


def check_policy(policy_refs, user_graph, query_graph, mode):

    # Can do all of the below earlier, don't need to do this everytime

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
    print(user)
    ########
    
    policy_graph = load_policy_graph(policy_refs)
    #print(policy_graph.serialize())
    allowed = False
    for ref, _ in policy_refs:
        policy = ref
        if (policy, RDF.type, ODRL.Policy) not in policy_graph:
            print(f"WARNING: Could not find policy {policy} in policy graph. Skipping this.")
            continue
        for rule in policy_graph.objects(policy, getattr(ODRL, mode)): # mode = 'permission' or 'prohibition'
            assignee = policy_graph.objects(rule, ODRL.assignee)
            action = policy_graph.objects(rule, ODRL.action)
            target = policy_graph.objects(rule, ODRL.target)

            # Check if targeting matches. Each of these is still very simplistic
            user_match = user in assignee 
            action_match = query_action in action
            target_match = query_graph.value(query_sbj, ODRL.target) in target # This cannot work in the full FDP version!! 
            print(user_match, action_match, target_match)
            if user_match and action_match and target_match:
                if matches_constraints(policy_graph, rule, query_graph, query_sbj, user_graph, user):
                    allowed = True
                else:
                    print(f"access denied by policy {policy}")
    return allowed

