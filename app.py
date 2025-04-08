import pandas as pd
import requests
from io import StringIO
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

def limpar_string(texto):
    # Converter a string para caixa baixa
    texto = texto.lower()

    # Dicionário com mapeamento dos caracteres acentuados para suas equivalentes sem acento
    mapa = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'ê': 'e',
        'í': 'i',
        'ó': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ü': 'u',
        'ç': 'c'
    }

    # Compilar padrão regex para os caracteres acentuados
    padrao = re.compile("|".join(mapa.keys()))
    texto = padrao.sub(lambda match: mapa[match.group(0)], texto)

    # Remover os caracteres que não sejam letras, números ou espaços
    texto = re.sub(r'[^a-z]+', ' ', texto)

    # Remover stopwords (exceto "para")
    stopwords_pattern = r'\b(?:de|do|da|em|na|no|pro|pra|para|com|e|ou|o|a)\b'
    texto = re.sub(stopwords_pattern, ' ', texto)

    # Colapsar espaços múltiplos e remover espaços nas extremidades
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def filter_row(row):
    """
    Remove do dicionário da linha as chaves indesejadas:
    "TUSS_x", "procedimento_x", "sinonimo", "subgrupo_x"
    """
    keys_to_exclude = {'TUSS_x', 'procedimento_x', 'sinonimo', 'subgrupo_x'}
    return { key: value for key, value in row.items() if key not in keys_to_exclude }

# URL de download direto do CSV "tuss_rol.csv"
CSV_URL = "https://drive.google.com/uc?export=download&id=1oe4yPNRzNPzh71DnWSeQGEaafjscuWue"

app = Flask(__name__)
CORS(app)

# Variáveis globais para os dados e índices
df_tuss = None
index_codigo = {}    # Dicionário indexando a coluna 'codigo' (ordenado em ordem crescente)
lista_termos = []    # Lista de registros (como dict) ordenada alfabeticamente pela coluna 'termos_pesquisa'

def carregar_dados():
    """
    Faz o download do CSV e carrega os dados em um DataFrame.
    Preenche valores ausentes, converte a coluna 'codigo' para string e
    garante que a coluna 'termos_pesquisa' já esteja armazenada na forma processada.
    """
    global df_tuss
    try:
        response = requests.get(CSV_URL)
        if response.status_code == 200:
            data_str = response.content.decode('utf-8')
            df_tuss = pd.read_csv(StringIO(data_str), sep=',', encoding='utf-8')
            df_tuss.fillna("", inplace=True)
            # Converter a coluna "codigo" para string
            df_tuss['codigo'] = df_tuss['codigo'].astype(str)
            print("CSV carregado com sucesso!")
        else:
            print(f"Erro ao baixar CSV. Status code: {response.status_code}")
    except Exception as e:
        print("Erro ao carregar dados:", e)
        raise

def construir_indices():
    """
    Constrói os índices para busca:
      1. Índice para a coluna 'codigo' (ordenado em ordem crescente).
      2. Lista de registros ordenada alfabeticamente pela coluna 'termos_pesquisa'.
    """
    global index_codigo, lista_termos

    index_codigo = {}
    # Ordena o DataFrame por 'codigo' (ordem crescente)
    df_sorted_codigo = df_tuss.sort_values(by='codigo', ascending=True)
    for _, row in df_sorted_codigo.iterrows():
        cod = row['codigo']
        index_codigo.setdefault(cod, []).append(row.to_dict())

    # Ordena o DataFrame por 'termos_pesquisa' (ordem alfabética)
    df_sorted_termos = df_tuss.sort_values(by='termos_pesquisa', ascending=True)
    lista_termos = df_sorted_termos.to_dict(orient='records')

def buscar_informacoes(valor_busca: str) -> dict:
    """
    Realiza a busca na base de dados.
    
    - Se o valor recebido for um número de 8 dígitos (ex: "12345678"), pesquisa em 'codigo'.
    - Caso contrário, processa o termo com limpar_string() e busca em 'termos_pesquisa', retornando apenas as linhas
      em que todas as palavras (tokenizadas) estejam presentes.
    
    As linhas retornadas são filtradas para não incluir as colunas: TUSS_x, procedimento_x, sinonimo, subgrupo_x.
    """
    valor_busca = valor_busca.strip()
    if not valor_busca:
        return {}

    # Se for código de 8 dígitos
    if re.fullmatch(r'\d{8}', valor_busca):
        if valor_busca in index_codigo:
            resultado = [filter_row(row) for row in index_codigo[valor_busca]]
            return {"resultado": resultado}
        else:
            return {}
    else:
        # Processa a entrada e divide em palavras
        termo_processado = limpar_string(valor_busca)
        query_words = termo_processado.split()
        resultado = []
        # Percorre os registros ordenados pela coluna 'termos_pesquisa'
        for row in lista_termos:
            termos_db = row.get('termos_pesquisa', "")
            # Verifica se todas as palavras estão presentes no campo
            if all(word in termos_db for word in query_words):
                resultado.append(filter_row(row))
        return {"resultado": resultado}

# Carrega os dados e constrói os índices ao iniciar a aplicação
carregar_dados()
if df_tuss is not None:
    construir_indices()

@app.route('/')
def index():
    return "API de busca TUSS vs Rol está online!"

@app.route('/buscar', methods=['GET'])
def buscar():
    """
    Endpoint de busca.
    
    Exemplos:
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
    # Executa localmente; o Cloud Run também suporta este padrão.
    app.run(host='0.0.0.0', port=8080, debug=True)
