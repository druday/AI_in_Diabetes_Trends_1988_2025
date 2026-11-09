import sys, json, time
import networkx as nx
from collections import Counter

import os; ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MERGE={"Endocrinology_Diabetes","Complications_Cardiometabolic_Nephrology_Neurology","Pediatrics_Maternal_Health"}
SUPER="Endocrine_Cardiometabolic_Maternal"

def metrics(G, mapping=None):
    comps=list(nx.connected_components(G))
    single=two=three=0; dc=[]
    for c in comps:
        types={str(G.nodes[n].get("type","Other")) for n in c}
        if mapping: types={mapping.get(t,t) for t in types}
        key={f for f in types if f!="Other"}
        dc.append(len(key))
        if len(key)==1: single+=1
        elif len(key)==2: two+=1
        elif len(key)>=3: three+=1
    n=len(comps) or 1
    return dict(num_components=len(comps),single=single,two=two,three_plus=three,
        single_ratio=single/n,three_plus_ratio=three/n,
        mean_domains=sum(dc)/len(dc) if dc else 0, max_domains=max(dc,default=0))

def footprint(G, target, mapping=None):
    """share of components containing target domain; distinct partner domains of target"""
    comps=list(nx.connected_components(G)); hit=0; partners=Counter(); nodes=0
    for c in comps:
        types=[str(G.nodes[n].get("type","Other")) for n in c]
        if mapping: types=[mapping.get(t,t) for t in types]
        s=set(types)
        if target in s:
            hit+=1
            for t in s:
                if t not in ("Other",target): partners[t]+=1
        nodes+=sum(1 for t in types if t==target)
    n=len(comps) or 1
    return dict(components_with=hit, share_components=hit/n, nodes=nodes,
                distinct_partner_domains=len(partners), top_partners=partners.most_common(6))

per=sys.argv[1]
t0=time.time()
G=nx.read_graphml(f"{ROOT}/outputs/networks/institutions_{per}.graphml")
mapping={d:SUPER for d in MERGE}
out={"period":per,"nodes":G.number_of_nodes(),"edges":G.number_of_edges(),
     "baseline":metrics(G),"merged":metrics(G,mapping),
     "types_present":sorted({str(G.nodes[n].get('type','Other')) for n in G})}
for d in sorted(MERGE):
    out[f"fp_{d}"]=footprint(G,d)
out["fp_SUPER"]=footprint(G,SUPER,mapping)
out["fp_GenClin"]=footprint(G,"General_Clinical_Medicine")
out["secs"]=round(time.time()-t0,1)
open(f"{per}.json","w").write(json.dumps(out,indent=1))
print(per,"done",out["secs"],"s")
