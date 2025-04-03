import pandas as pd
import requests
from io import StringIO
from flask import Flask, request, jsonify
from flask_cors import CORS

# URL de download do CSV no Google Drive (substitua se necessário)
CSV_URL = "https://drive.google.com/uc?export=download&id=1znQZMBzz5L_Xh9W4Gsb5CKl2_kaHTvjj"

app = Flask(__name__)
CORS(app)

# Variável global para armazenar o DataFrame
df_tuss = None

# Dicionários para indexar as colunas
index_codigo = {}
index_tuss = {}
index_procedimento = {}

def carregar_dados():
    """
    Faz o download do CSV e carrega os dados em um DataFrame.
    Substitui valores NaN por string vazia para evitar erros.
    """
    global df_tuss
    try:
        response = requests.get(CSV_URL)
        if response.status_code == 200:
            data_str = response.content.decode('utf-8')
            df_tuss = pd.read_csv(StringIO(data_str), sep=',', encoding='utf-8')
            df_tuss.fillna("", inplace=True)
            print("CSV carregado com sucesso!")
        else:
            print(f"Erro ao baixar CSV. Status code: {response.status_code}")
    except Exception as e:
        print("Erro ao carregar dados:", e)
        raise

def construir_indices():
    """
    Constrói dicionários mapeando os valores das colunas 'codigo', 'TUSS' e 'procedimento'
    para todas as linhas correspondentes do DataFrame.
    """
    global index_codigo, index_tuss, index_procedimento
    index_codigo = {}
    index_tuss = {}
    index_procedimento = {}
    
    # Itera sobre cada linha do DataFrame e popula os índices
    for _, row in df_tuss.iterrows():
        codigo_val = str(row['codigo'])
        tuss_val = str(row['TUSS'])
        proc_val = str(row['procedimento'])
        
        # Atualiza índice de 'codigo'
        if codigo_val in index_codigo:
            index_codigo[codigo_val].append(row.to_dict())
        else:
            index_codigo[codigo_val] = [row.to_dict()]
        
        # Atualiza índice de 'TUSS'
        if tuss_val in index_tuss:
            index_tuss[tuss_val].append(row.to_dict())
        else:
            index_tuss[tuss_val] = [row.to_dict()]
        
        # Atualiza índice de 'procedimento'
        if proc_val in index_procedimento:
            index_procedimento[proc_val].append(row.to_dict())
        else:
            index_procedimento[proc_val] = [row.to_dict()]

def buscar_informacoes(valor_busca: str) -> dict:
    """
    Busca o valor na ordem: 'codigo', 'TUSS' e 'procedimento'.
    Retorna todas as linhas correspondentes encontradas.
    Se uma correspondência for encontrada em um índice, os demais não são verificados.
    """
    # Busca em 'codigo'
    if valor_busca in index_codigo:
        return {"resultado": index_codigo[valor_busca]}
    
    # Busca em 'TUSS'
    if valor_busca in index_tuss:
        return {"resultado": index_tuss[valor_busca]}
    
    # Busca em 'procedimento'
    if valor_busca in index_procedimento:
        return {"resultado": index_procedimento[valor_busca]}
    
    # Caso não encontre nenhuma correspondência
    return {}

# Carrega o CSV e constrói os índices ao iniciar o aplicativo
carregar_dados()
if df_tuss is not None:
    construir_indices()

@app.route('/')
def index():
    return "API de busca TUSSxRol está online!"

@app.route('/buscar', methods=['GET'])
def buscar():
    """
    Endpoint que recebe um parâmetro 'valor' via query string.
    Exemplo: /buscar?valor=12345
    """
    valor_busca = request.args.get('valor', '').strip()
    if not valor_busca:
        return jsonify({"erro": "Parâmetro 'valor' não fornecido"}), 400

    resultado = buscar_informacoes(valor_busca)
    if resultado:
        return jsonify(resultado), 200
    else:
        return jsonify({"erro": "Nenhum resultado encontrado"}), 404

if __name__ == '__main__':
    # Para rodar localmente; o Cloud Run também suporta esta configuração.
    app.run(host='0.0.0.0', port=8080, debug=True)
