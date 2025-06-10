from rdflib import Graph, Namespace, URIRef, BNode
import rdflib
from urllib.parse import urldefrag

ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
EX = Namespace("http://www.example.org")

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



def is_query_allowed(user, query, dataset_uri, purpose, policy_refs, check_prohibition_only=False):
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

    query_action = deduce_action_from_query(query)
    if query_action is None:
        print("Could not deduce action from query.")
        return False

    if check_prohibition_only:
        for ref, _ in policy_refs:
            policy = ref
            if (policy, rdflib.RDF.type, ODRL.Policy) not in g:
                continue
            for prohibition in g.objects(policy, ODRL.prohibition):
                assignee = g.value(prohibition, ODRL.assignee)
                action = g.value(prohibition, ODRL.action)
                target = g.value(prohibition, ODRL.target)

                if str(assignee) == user and str(target) == dataset_uri and action == query_action:
                    matches = True
                    for constraint in g.objects(prohibition, ODRL.constraint):
                        left = g.value(constraint, ODRL.leftOperand)
                        op = g.value(constraint, ODRL.operator)
                        right = g.value(constraint, ODRL.rightOperand)
                        if left == ODRL.purpose and op == ODRL.eq and str(right) != purpose:
                            matches = False
                    if matches:
                        return True
        return False

    for ref, _ in policy_refs:
        policy = ref
        if (policy, rdflib.RDF.type, ODRL.Policy) not in g:
            continue
        for permission in g.objects(policy, ODRL.permission):
            assignee = g.value(permission, ODRL.assignee)
            action = g.value(permission, ODRL.action)
            target = g.value(permission, ODRL.target)

            if str(assignee) == user and str(target) == dataset_uri and action == query_action:
                matched = True
                for constraint in g.objects(permission, ODRL.constraint):
                    left = g.value(constraint, ODRL.leftOperand)
                    op = g.value(constraint, ODRL.operator)
                    right = g.value(constraint, ODRL.rightOperand)
                    if left == ODRL.purpose and op == ODRL.eq and str(right) != purpose:
                        matched = False
                if matched:
                    return True

    return False
