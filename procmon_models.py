# ProcMon - Monitoramento de Processos
"""
 **Arquivo**: procmon_models.py
 
 **Autor**: Natan Fiuza
 
 **Data**: 2025-05-04
 
 **Descrição**: Este arquivo contém a definição de todas as classes de modelo
 
 *Copyright (c) 2025, NatanFiuza.dev.br*
"""
import logging

class PidFilter(logging.Filter):
    """
    Filtro de logging que adiciona um atributo 'pids' com valor 'N/A'
    ao LogRecord se ele ainda não existir.
    """

    def filter(self, record):
        if not hasattr(record, 'pids'):
            record.pids = 'N/A'  # Define o valor padrão
        return True  # Sempre retorna True para que o log seja processado
