"""
Rede doença-doença construída a partir de sintomas partilhados.

Projeto de Grafos e Redes Complexas (Iscte, 2025/26).

Uso:
    python analise_rede.py "Disease and symptoms dataset.csv"
    python analise_rede.py "Disease and symptoms dataset.csv" --girvan-newman

O dataset não está incluído neste repositório (tem cerca de 190 MB).
"""
import argparse
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from networkx.algorithms.community import girvan_newman, louvain_communities

parser = argparse.ArgumentParser()
parser.add_argument("dataset", help="caminho para o CSV doença-sintoma")
parser.add_argument("--saida", default="resultados", help="pasta onde guardar tabelas e figuras")
parser.add_argument("--girvan-newman", action="store_true",
                    help="correr também o Girvan-Newman (os 3 primeiros níveis; demora bastante)")
args = parser.parse_args()
saida = Path(args.saida)
saida.mkdir(exist_ok=True)

# ------------------------------------------------------------------
# 1. Dados e limpeza
# ------------------------------------------------------------------
df = pd.read_csv(args.dataset)
print("Dataset:", df.shape)  # (246945, 378)

# Normalizar o nome das doenças e das colunas
df["diseases"] = df["diseases"].str.strip().str.title()
df.columns = df.columns.str.title()
print("Valores nulos:", int(df.isnull().sum().sum()))

# ------------------------------------------------------------------
# 2. Rede bipartida doença-sintoma e projeção doença-doença
# ------------------------------------------------------------------
sintomas = df.columns.drop("Diseases")
linhas, colunas = np.nonzero(df[sintomas].to_numpy() == 1)  # pares doença-sintoma presentes
pares = pd.DataFrame({
    "Disease": df["Diseases"].to_numpy()[linhas],
    "Symptom": sintomas.to_numpy()[colunas],
}).drop_duplicates()

G_bip = nx.Graph()
G_bip.add_nodes_from(pares["Disease"], bipartite="Disease")
G_bip.add_nodes_from(pares["Symptom"], bipartite="Symptom")
G_bip.add_edges_from(pares.itertuples(index=False, name=None))

doencas = [n for n, d in G_bip.nodes(data=True) if d["bipartite"] == "Disease"]
# O peso de cada aresta é o número de sintomas em comum
G_proj = nx.bipartite.weighted_projected_graph(G_bip, doencas)
print("Nós:", G_proj.number_of_nodes(), "| Arestas:", G_proj.number_of_edges())

# ------------------------------------------------------------------
# 3. Métricas macro
# ------------------------------------------------------------------
num_nodes = G_proj.number_of_nodes()
num_edges = G_proj.number_of_edges()
density = nx.density(G_proj)
num_components = nx.number_connected_components(G_proj)
largest_cc = max(nx.connected_components(G_proj), key=len)
G_lcc = G_proj.subgraph(largest_cc).copy()
avg_path = nx.average_shortest_path_length(G_lcc)
diameter = nx.diameter(G_lcc)

macro_df = pd.DataFrame({
    "Métrica": ["Número de nós", "Número de arestas", "Densidade", "Componentes conectadas",
                "Tamanho da maior componente", "Path length médio", "Diâmetro"],
    "Valor": [num_nodes, num_edges, density, num_components, len(largest_cc), avg_path, diameter],
})
print("\n=== MÉTRICAS MACRO ===\n", macro_df.to_string(index=False))

# ------------------------------------------------------------------
# 4. Métricas meso
# ------------------------------------------------------------------
clustering_global = nx.transitivity(G_proj)
clustering_avg = nx.average_clustering(G_proj, weight="weight")
assortativity = nx.degree_assortativity_coefficient(G_proj)

meso_df = pd.DataFrame({
    "Métrica": ["Clustering global (transitivity)", "Clustering médio ponderado",
                "Assortatividade por grau"],
    "Valor": [clustering_global, clustering_avg, assortativity],
})
print("\n=== MÉTRICAS MESO ===\n", meso_df.to_string(index=False))

# ------------------------------------------------------------------
# 5. Comunidades
# ------------------------------------------------------------------
if args.girvan_newman:
    gerador = girvan_newman(G_proj)
    gn = []
    for nivel in range(1, 4):
        comunidades = [set(c) for c in next(gerador)]
        gn.append({"Nível": nivel, "Número de comunidades": len(comunidades),
                   "Tamanhos das comunidades": sorted((len(c) for c in comunidades), reverse=True)})
    gn_df = pd.DataFrame(gn)
    print("\n=== GIRVAN-NEWMAN ===\n", gn_df.to_string(index=False))
    gn_df.to_csv(saida / "girvan_newman.csv", index=False, encoding="utf-8-sig")

communities = louvain_communities(G_proj, weight="weight", seed=42)
partition = {no: i for i, comunidade in enumerate(communities) for no in comunidade}
tamanhos = Counter(partition.values())
print("\n=== LOUVAIN ===")
print("Comunidades:", len(communities), "| Tamanhos:", dict(tamanhos))

community_df = pd.DataFrame({"Disease": list(partition.keys()),
                             "Community": list(partition.values())})
community_summary = community_df.groupby("Community")["Disease"].apply(list).reset_index()
community_summary["Número de doenças"] = community_summary["Disease"].apply(len)
community_summary["Exemplos de doenças"] = community_summary["Disease"].apply(
    lambda d: ", ".join(d[:8]))
community_summary = (community_summary[["Community", "Número de doenças", "Exemplos de doenças"]]
                     .sort_values("Número de doenças", ascending=False))

# ------------------------------------------------------------------
# 6. Métricas micro (centralidades)
# ------------------------------------------------------------------
degree_centrality = nx.degree_centrality(G_proj)
strength = dict(G_proj.degree(weight="weight"))  # grau ponderado

# O peso mede semelhança; para caminhos mais curtos usa-se a distância inversa
G_dist = G_proj.copy()
for _, _, dados in G_dist.edges(data=True):
    dados["distance"] = 1 / dados["weight"]

betweenness = nx.betweenness_centrality(G_dist, weight="distance", normalized=True)
closeness = nx.closeness_centrality(G_dist, distance="distance")

micro_df = pd.DataFrame({
    "Disease": list(G_proj.nodes()),
    "Degree Centrality": [degree_centrality[n] for n in G_proj.nodes()],
    "Strength": [strength[n] for n in G_proj.nodes()],
    "Betweenness Centrality": [betweenness[n] for n in G_proj.nodes()],
    "Closeness Centrality": [closeness[n] for n in G_proj.nodes()],
})
top_degree = micro_df.sort_values("Degree Centrality", ascending=False).head(10)
top_strength = micro_df.sort_values("Strength", ascending=False).head(10)
top_betweenness = micro_df.sort_values("Betweenness Centrality", ascending=False).head(10)
top_closeness = micro_df.sort_values("Closeness Centrality", ascending=False).head(10)
for nome, t in [("Degree", top_degree), ("Strength", top_strength),
                ("Betweenness", top_betweenness), ("Closeness", top_closeness)]:
    print(f"\nTop 10 - {nome}\n", t.to_string(index=False))

# ------------------------------------------------------------------
# 7. Figuras
# ------------------------------------------------------------------
for t, coluna, titulo, ficheiro in [
        (top_strength, "Strength", "Top 10 doenças com maior strength", "top10_strength.png"),
        (top_degree, "Degree Centrality", "Top 10 doenças com maior degree centrality",
         "top10_degree_centrality.png")]:
    plt.figure(figsize=(10, 6))
    plt.barh(t["Disease"], t[coluna])
    plt.xlabel(coluna)
    plt.ylabel("Doença")
    plt.title(titulo)
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(saida / ficheiro, dpi=150)
    plt.close()

plt.figure(figsize=(8, 5))
plt.bar(community_summary["Community"].astype(str), community_summary["Número de doenças"])
plt.xlabel("Comunidade")
plt.ylabel("Número de doenças")
plt.title("Tamanho das comunidades identificadas pelo algoritmo Louvain")
plt.tight_layout()
plt.savefig(saida / "comunidades_louvain.png", dpi=150)
plt.close()

# ------------------------------------------------------------------
# 8. Tabelas
# ------------------------------------------------------------------
tabelas = {
    "metricas_macro": macro_df, "metricas_meso": meso_df,
    "comunidades_louvain": community_summary, "metricas_micro_completa": micro_df,
    "top10_degree_centrality": top_degree, "top10_strength": top_strength,
    "top10_betweenness": top_betweenness, "top10_closeness": top_closeness,
}
for nome, t in tabelas.items():
    t.to_csv(saida / f"{nome}.csv", index=False, encoding="utf-8-sig")
print("\nTabelas e figuras guardadas em", saida)
