import pandas as pd
import requests
from io import StringIO
from flask import Flask, request, jsonify
from flask_cors import CORS

# URL de download direto do seu CSV no Google Drive
CSV_URL = "https://drive.google.com/uc?export=download&id=1znQZMBzz5L_Xh9W4Gsb5CKl2_kaHTvjj"

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas

df_tuss = None  # Variável global para armazenar o DataFrame

def carregar_dados():
    """
    Faz o download do CSV do Google Drive e carrega em um DataFrame pandas.
    Substitui valores NaN por string vazia para evitar erros de JSON.
    """
    global df_tuss
    try:
        response = requests.get(CSV_URL)
        if response.status_code == 200:
            data_str = response.content.decode('utf-8')
            # Ajuste o separador se necessário (sep=';')
            df_tuss = pd.read_csv(StringIO(data_str), sep=',', encoding='utf-8')
            # Substitui NaN por ""
            df_tuss = df_tuss.fillna("")
            print("CSV carregado com sucesso!")
        else:
            print(f"Erro ao baixar CSV. Status code: {response.status_code}")
    except Exception as e:
        print("Erro ao carregar dados:", e)
        raise

def buscar_informacoes(valor_busca: str) -> dict:
    """
    Busca o valor em cada coluna relevante e retorna um dicionário
    com as outras colunas correspondentes.
    Caso não encontre correspondência, retorna um dicionário vazio.
    """
    if df_tuss is None:
        return {}

    # Ajuste o nome das colunas conforme seu CSV
    col_codigo = 'codigo'
    col_tuss = 'TUSS'
    col_tussxrol = 'TUSSxRol'
    col_procedimento = 'procedimento'
    col_sinonimos = 'sinonimos'  # Ajuste se necessário

    # Converter para string antes de comparar, para evitar problemas de tipo
    df_tuss[col_codigo] = df_tuss[col_codigo].astype(str)
    df_tuss[col_tuss] = df_tuss[col_tuss].astype(str)
    df_tuss[col_tussxrol] = df_tuss[col_tussxrol].astype(str)
    if col_sinonimos in df_tuss.columns:
        df_tuss[col_sinonimos] = df_tuss[col_sinonimos].astype(str)

    # 1) Verifica se o valor está em 'codigo'
    if valor_busca in df_tuss[col_codigo].values:
        linha = df_tuss.loc[df_tuss[col_codigo] == valor_busca].iloc[0]
        return {
            col_tuss: linha[col_tuss],
            col_tussxrol: linha[col_tussxrol],
            col_procedimento: linha[col_procedimento]
        }

    # 2) Verifica se o valor está em 'TUSS'
    if valor_busca in df_tuss[col_tuss].values:
        linha = df_tuss.loc[df_tuss[col_tuss] == valor_busca].iloc[0]
        return {
            col_codigo: linha[col_codigo],
            col_tussxrol: linha[col_tussxrol],
            col_procedimento: linha[col_procedimento]
        }

    # 3) Verifica se o valor está em 'TUSSxRol'
    if valor_busca in df_tuss[col_tussxrol].values:
        linha = df_tuss.loc[df_tuss[col_tussxrol] == valor_busca].iloc[0]
        return {
            col_codigo: linha[col_codigo],
            col_tuss: linha[col_tuss],
            col_procedimento: linha[col_procedimento]
        }

    # 4) Verifica se existe a coluna "sinonimos" e se o valor está nela
    if col_sinonimos in df_tuss.columns:
        # Exemplo de busca contendo substring (case-insensitive)
        mask = df_tuss[col_sinonimos].str.contains(valor_busca, case=False, na=False)
        if mask.any():
            linha = df_tuss.loc[mask].iloc[0]
            return {
                col_codigo: linha[col_codigo],
                col_tuss: linha[col_tuss],
                col_tussxrol: linha[col_tussxrol],
                col_procedimento: linha[col_procedimento]
            }

    # Caso não encontre correspondência
    return {}

# Carrega o CSV ao importar o módulo (funciona tanto localmente quanto no Gunicorn/Cloud Run)
carregar_dados()

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
        return jsonify({"resultado": resultado}), 200
    else:
        return jsonify({"erro": "Nenhum resultado encontrado"}), 404

if __name__ == '__main__':
    # Para rodar localmente:
    app.run(host='0.0.0.0', port=8080, debug=True)
