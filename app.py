import os
import pandas as pd
import requests
from io import StringIO
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from itertools import combinations  # para gerar combinações de palavras

def limpar_string(texto):
    # Converte para caixa baixa
    texto = texto.lower()
    # Mapeia caracteres acentuados
    mapa = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'ê': 'e',
        'í': 'i',
        'ó': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ü': 'u',
        'ç': 'c'
    }
    padrao = re.compile("|".join(mapa.keys()))
    texto = padrao.sub(lambda match: mapa[match.group(0)], texto)
    # Remove caracteres que não sejam letras, números ou espaços
    texto = re.sub(r'[^a-z]+', ' ', texto)
    # Remove stopwords (exceto "para")
    stopwords_pattern = r'\b(?:de|do|da|em|na|no|pro|pra|para|com|e|ou|o|a)\b'
    texto = re.sub(stopwords_pattern, ' ', texto)
    # Colapsa espaços e remove espaços das extremidades
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def filter_row(row):
    """Remove do dicionário da linha as colunas indesejadas."""
    keys_to_exclude = {'termos_pesquisa_puros'}
    return {key: value for key, value in row.items() if key not in keys_to_exclude}

# URL de download direto do CSV
# CSV_URL = "https://drive.google.com/uc?export=download&id=1ThZUbTiLait6rMo9TiNv62O_RYLchQWk"
CSV_URL = "https://drive.google.com/uc?export=download&id=1ThZUbTiLait6rMo9TiNv62O_RYLchQWk"


app = Flask(__name__)
CORS(app)

# Variáveis globais para os dados e índices
df_tuss = None
index_codigo = {}    # Índice para busca por código
lista_termos = []    # Lista de registros para busca por termos (já processados)

def carregar_dados():
    """Faz o download do CSV, carrega os dados e converte a coluna 'codigo' para string sem espaços extras."""
    global df_tuss
    try:
        response = requests.get(CSV_URL)
        response.raise_for_status()
        data_str = response.content.decode('utf-8')
        # Lê o CSV com separador ';'
        df_tuss = pd.read_csv(StringIO(data_str), sep=';', encoding='utf-8')
        df_tuss.fillna("", inplace=True)
        
        # Debug: exibe as colunas e as primeiras linhas
        print("Colunas carregadas:", df_tuss.columns.tolist())
        print("Preview do CSV:")
        print(df_tuss.head())
        
        # Verifica se as colunas essenciais estão presentes
        if 'codigo' not in df_tuss.columns or 'termos_pesquisa' not in df_tuss.columns:
            raise ValueError("O CSV precisa conter as colunas 'codigo' e 'termos_pesquisa'")
        
        # Converte a coluna 'codigo' para string e remove espaços extras
        df_tuss['codigo'] = df_tuss['codigo'].astype(str).str.strip()
        print("CSV carregado com sucesso! Total de linhas:", len(df_tuss))
    except Exception as e:
        print("Erro ao baixar ou carregar CSV:", e)
        raise

def construir_indices():
    """
    Constrói dois índices:
      1. Dicionário indexando a coluna 'codigo' (em ordem crescente).
      2. Lista de registros ordenada alfabeticamente pela coluna 'termos_pesquisa' (que já vem processada).
    """
    global index_codigo, lista_termos

    index_codigo = {}
    try:
        df_sorted_codigo = df_tuss.sort_values(by='codigo', ascending=True)
        for _, row in df_sorted_codigo.iterrows():
            cod = row['codigo']
            index_codigo.setdefault(cod, []).append(row.to_dict())
    except Exception as e:
        print("Erro ao construir índice por 'codigo':", e)
        raise

    try:
        df_sorted_termos = df_tuss.sort_values(by='termos_pesquisa', ascending=True)
        lista_termos = df_sorted_termos.to_dict(orient='records')
        print("Índices construídos com sucesso!")
    except Exception as e:
        print("Erro ao construir índice por 'termos_pesquisa':", e)
        raise

def search_exact(query_list):
    """
    Realiza a busca com correspondência exata: o registro é considerado _match_
    se, ao dividir a string dos termos (por espaços), contiver todas as palavras em query_list.
    """
    results = []
    for row in lista_termos:
        termos_db = row.get('termos_pesquisa', "")
        if not isinstance(termos_db, str):
            continue
        palavras = termos_db.split()
        # Confere se cada palavra na query está presente de forma exata
        if all(q in palavras for q in query_list):
            results.append(filter_row(row))
    return results

def buscar_informacoes(valor_busca: str) -> dict:
    """
    Realiza a busca:
      - Se valor_busca for um número de 8 dígitos, procura pelo código.
      - Caso contrário, aplica a normalização dos termos e tenta:
          1. Busca com correspondência exata para TODOS os termos da expressão.
          2. Se não houver resultados, realiza buscas progressivas combinando o primeiro termo com
             combinações dos demais (do tamanho máximo até 1). Na primeira rodada em que há resultados,
             retorna todos os resultados dessa rodada sem prosseguir para combinações menores.
    """
    valor_busca = valor_busca.strip()
    if not valor_busca:
        return {}

    # Busca por código (8 dígitos)
    if re.fullmatch(r'\d{8}', valor_busca):
        if valor_busca in index_codigo:
            resultado = [filter_row(row) for row in index_codigo[valor_busca]]
            return {"resultado": resultado}
        else:
            return {"resultado": []}
    else:
        # Normaliza a consulta e obtém as palavras
        termo_processado = limpar_string(valor_busca)
        query_words = termo_processado.split()
        print("Buscando por termos processados:", query_words)
        print("Total de registros para busca:", len(lista_termos))
        
        # Se houver apenas uma palavra, pesquisa diretamente
        if len(query_words) == 1:
            resultado = search_exact(query_words)
            return {"resultado": resultado}
        
        # Busca 1: tenta com todos os termos (correspondência exata de cada palavra)
        resultado_full = search_exact(query_words)
        if resultado_full:
            return {"resultado": resultado_full}
        
        # Se não houver resultado, tenta combinações menores mantendo a primeira palavra como obrigatória.
        first = query_words[0]
        rest = query_words[1:]
        # Itera do tamanho máximo (len(rest)) até 1
        for r in range(len(rest), 0, -1):
            level_results = []
            # Gera todas as combinações de 'rest' com tamanho r
            for comb in combinations(rest, r):
                test_query = [first] + list(comb)
                print("Tentando combinação:", test_query)
                matches = search_exact(test_query)
                if matches:
                    level_results.extend(matches)
            if level_results:
                # Se nessa rodada (nível de combinação) obtivermos resultados, retornamos e não prosseguimos
                return {"resultado": level_results}
        
        # Se nenhuma combinação produzir resultado, retorna resultado vazio.
        return {"resultado": []}

# Inicializa o carregamento dos dados e construção dos índices
try:
    carregar_dados()
    if df_tuss is not None:
        construir_indices()
except Exception as e:
    print("Erro na inicialização da aplicação:", e)

@app.route('/')
def index():
    return "API de busca TUSS vs Rol está online!"

@app.route('/buscar', methods=['GET'])
def buscar():
    """
    Endpoint de busca.
    Exemplos de uso:
      /buscar?valor=12345678          -> Busca por código
      /buscar?valor=exemplo de termo   -> Busca por termos na coluna 'termos_pesquisa'
    """
    valor_busca = request.args.get('valor', '').strip()
    if not valor_busca:
        return jsonify({"erro": "Parâmetro 'valor' não fornecido"}), 400

    resultado = buscar_informacoes(valor_busca)
    if resultado and resultado.get("resultado"):
        return jsonify(resultado), 200
    else:
        return jsonify({"erro": "Nenhum resultado encontrado"}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)


