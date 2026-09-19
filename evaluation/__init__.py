"""Experimento das Sprints 11–12: gabarito, verificação e baseline text-to-SQL.

Este pacote acessa a Gold diretamente por SQL. O agente (`agent/`) nunca
faz isso — só enxerga o modelo semântico. O acesso direto existe aqui
para duas coisas: verificar o gabarito por um caminho independente das
medidas DAX, e servir de base ao baseline text-to-SQL do benchmark.
"""
