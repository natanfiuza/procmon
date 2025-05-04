# ProcMon - Monitoramento de Processos
"""
 **Arquivo**: procmon_utils.py
 
 **Autor**: Natan Fiuza
 
 **Data**: 2025-05-04
 
 **Descrição**: Este arquivo contém a definição de todas as funções auxiliares
 
 *Copyright (c) 2025, NatanFiuza.dev.br*
"""
import logging
import datetime
import os
import psutil  

# Exceção customizada para erros na coleta de stats
class StatsCollectionError(Exception):
    pass


def get_timestamp_str():
    """Retorna o timestamp atual no formato YYYYMMDDHHMM."""
    return datetime.datetime.now().strftime("%Y%m%d%H%M")


def get_log_filename(log_path, template, timestamp_str, process_name=None):
    """Gera o nome completo do arquivo de log."""
    filename = template.replace('%DATAHORA%', timestamp_str)
    if process_name:
        filename = f"{process_name}_{filename}"
    return os.path.join(log_path, filename)


def setup_logger(name, log_file, loggers_dict, filenames_dict, filter_instance):
    """
    Configura e retorna um logger para um arquivo específico,
    gerenciando dicionários de loggers e nomes de arquivos.
    """
    logger = loggers_dict.get(name)
    if logger:
        # Remover handler antigo se o nome base for o mesmo (evita duplicatas ao rotacionar)
        for handler in list(logger.handlers):
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == filenames_dict.get(name):
                handler.close()
                logger.removeHandler(handler)
    else:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    # Adiciona o filtro para garantir 'pids' (apenas uma vez)
    if filter_instance and filter_instance not in logger.filters:
        logger.addFilter(filter_instance)

    # Configura o formato da mensagem (com %(pids)s)
    log_format = '%(asctime)s :: %(levelname)s :: PIDs[%(pids)s] :: %(message)s'
    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')

    # Configura o FileHandler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # Adiciona o handler ao logger (evita duplicatas)
    handler_exists = any(
        isinstance(h, logging.FileHandler) and h.baseFilename == log_file
        for h in logger.handlers
    )
    if not handler_exists:
        logger.addHandler(file_handler)

    # Atualiza os dicionários de estado
    loggers_dict[name] = logger
    filenames_dict[name] = log_file
    return logger


def get_system_stats():
    """Coleta estatísticas globais de CPU e memória. Levanta StatsCollectionError em caso de falha."""
    try:
        cpu_usage = psutil.cpu_percent(interval=None)
        memory_info = psutil.virtual_memory()
        memory_usage_percent = memory_info.percent
        return cpu_usage, memory_usage_percent
    except Exception as e:
        # Levanta uma exceção específica em vez de logar aqui
        raise StatsCollectionError(
            f"Erro ao coletar estatísticas GLOBAIS: {e}") from e


def get_process_stats(process_name):
    """
    Coleta estatísticas de CPU/memória e PIDs para processos cujo nome contém process_name.
    Levanta StatsCollectionError em caso de falha na iteração. Retorna (0, 0, []) se não encontrado.
    """
    total_cpu = 0.0
    total_mem_percent = 0.0
    pids_found = []
    process_found = False
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                    process_found = True
                    pids_found.append(proc.info['pid'])
                    total_cpu += proc.info['cpu_percent'] if proc.info['cpu_percent'] is not None else 0.0
                    total_mem_percent += proc.info['memory_percent'] if proc.info['memory_percent'] is not None else 0.0
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue  # Ignora processos inacessíveis

        # Retorna mesmo se process_found for False (retornará 0, 0, [])
        return total_cpu, total_mem_percent, pids_found

    except Exception as e:
        # Levanta uma exceção específica em vez de logar aqui
        raise StatsCollectionError(
            f"Erro ao iterar ou coletar estatísticas para o processo '{process_name}': {e}") from e
