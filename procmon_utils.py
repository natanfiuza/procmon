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

# Exceção customizada 
class StatsCollectionError(Exception):
    pass
class CoreInfoError(Exception):
    """Exceção para erros ao obter informações dos núcleos da CPU."""
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


def get_top_processes(num_processes=10,type='cpu'):
    """
    Coleta informações dos N processos que mais consomem CPU, incluindo uso de memória.

    Args:
        num_processes (int): O número de processos a serem retornados.
        type (str): O tipo de métrica a ser usada para ordenação ('cpu' ou 'mem').

    Returns:
        list: Uma lista de dicionários, cada um contendo 'pid', 'name', 'cpu', 'mem'.
              Retorna lista vazia em caso de erro grave na iteração.

    Raises:
        StatsCollectionError: Se ocorrer um erro significativo durante a coleta.
    """
    processes_data = []
    try:
        # ---> Pede também 'memory_percent' ao iterar <---
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                cpu_percent = proc.info['cpu_percent']
                # ---> Coleta memory_percent <---
                mem_percent = proc.info['memory_percent']

                # Inclui se tiver nome e ambos os percentuais (mesmo que 0.0)
                if proc.info['name'] and cpu_percent is not None and mem_percent is not None:
                    processes_data.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu': cpu_percent,                        
                        'mem': mem_percent
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as inner_e:
                print(f"Aviso: Erro ao processar PID {proc.info.get('pid', '?')}: {inner_e}", file=sys.stderr) # Debug
                continue

        # Ordena APENAS pelo percentual de CPU
        sorted_processes = sorted(
            processes_data, key=lambda p: p[type], reverse=True)

        return sorted_processes[:num_processes]

    except Exception as e:
        raise StatsCollectionError(
            f"Erro ao iterar processos para obter Top CPU: {e}") from e


def get_core_info():
    """
    Obtém informações sobre os núcleos da CPU e o uso percentual total do sistema.

    Returns:
        dict: Um dicionário contendo:
              'physical' (int|None): número de núcleos físicos.
              'logical' (int|None): número de núcleos lógicos.
              'system_usage_percent' (float|None): uso percentual total da CPU.

    Raises:
        CoreInfoError: Se ocorrer um erro na coleta de dados do psutil.
    """
    core_info = {
        'physical': None,
        'logical': None,
        'system_usage_percent': None
    }
    try:
        core_info['physical'] = psutil.cpu_count(logical=False)
        core_info['logical'] = psutil.cpu_count(logical=True)
        # Usa um intervalo curto para uma medição mais representativa do uso atual do sistema
        core_info['system_usage_percent'] = psutil.cpu_percent(interval=0.1)

        # Verifica se algum valor essencial não foi obtido (pouco provável para cpu_count/percent)
        if core_info['physical'] is None or core_info['logical'] is None or core_info['system_usage_percent'] is None:
            raise CoreInfoError(
                "Não foi possível obter todos os dados de CPU (cores/uso).")

        return core_info
    except NotImplementedError as e:
        raise CoreInfoError(
            f"Funcionalidade não suportada pela plataforma/psutil: {e}") from e
    except Exception as e:
        raise CoreInfoError(
            f"Erro ao obter informações dos núcleos/uso da CPU via psutil: {e}") from e
