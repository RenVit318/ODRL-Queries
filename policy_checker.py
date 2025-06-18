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
    """"""
    g = Graph()
    loaded_uris = set()
    for ref, source_graph in policy_refs:
        if isinstance(ref, URIRef):
            base_uri, _ = urldefrag(ref)
            if base_uri not in loaded_uris:
                #try:
                    g.parse(base_uri, format="turtle")
                    loaded_uris.add(base_uri)
                #except Exception as e:
                #    print(f"Warning: Failed to load policy from {base_uri}: {e}")
        elif isinstance(ref, BNode):
            for triple in source_graph.triples((ref, None, None)):
                g.add(triple)
    return g


def matches_constraints(policy_graph, rule, query_graph, query_sbj, user_graph, user):
    """Find all constraints given in an ODRL policy and match them against the user and query graphs.
    False means one or more of the constraints did not match. True means either all constraints matched or there were no constraints"""

    i = 0 # Use this to count the number of constraints. Can't get the length of policy_graph.objects() 
    for constraint in policy_graph.objects(rule, ODRL.constraint):
        i += 1
        # Assume the constraint is described as left = predicate, right = object
        left = policy_graph.value(constraint, ODRL.leftOperand)
        op = policy_graph.value(constraint, ODRL.operator)
        right = policy_graph.value(constraint, ODRL.rightOperand)

        #print(left, op, right)
        if op == ODRL.eq:
            # Search for the predicate in both the query graph and the user graph
            print(query_graph.value(query_sbj, left))
            if query_graph.value(query_sbj, left) == right:
                continue
            elif user_graph.value(user, left) == right:
                continue
        else:
            print(f"WARNING: ODRL Operator {ODRL.eq} not yet supported.")

        return False # No continue so no match in either graph
    
    return True # Either no constraints, or passed all constraints


def check_policy(policy_refs, query_graph, query_sbj, query_action, user_graph, user, endpoint_url, mode):
    """"""
    
    policy_graph = load_policy_graph(policy_refs)

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
            target_match = endpoint_url in target # Don't set one target but the target is always the discovered endpoint!
            target_match = True#
            print(user_match, action_match, target_match)
            #print('desired endpoint: ' + endpoint_url)


            if user_match and action_match and target_match:
                if matches_constraints(policy_graph, rule, query_graph, query_sbj, user_graph, user):
                    allowed = True
                else:
                    print(f"access denied by policy {policy}")

    return allowed

