import requests

url = "https://www.bcb.gov.br/pda/desig/scrdata_2024.zip"
destino = "ingestion/scrdata_2024_teste.zip"

print("Baixando...")
resposta = requests.get(url, stream=True)
resposta.raise_for_status()

total_bytes = 0
with open(destino, "wb") as arquivo:
    for pedaco in resposta.iter_content(chunk_size=8192):
        arquivo.write(pedaco)
        total_bytes += len(pedaco)

print(f"Download concluído: {destino}")
print(f"Tamanho: {total_bytes / 1024 / 1024:.1f} MB")
