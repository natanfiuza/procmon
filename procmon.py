# -*- coding: utf-8 -*-
"""
Monitor de Processos e Sistema (ProcMon)
Registra uso de CPU/Memória global e de processos específicos.
Pode ser compilado para .exe e rodar como serviço Windows.
"""

import psutil
import time
import logging
import logging.handlers
import datetime
import os
import sys
import argparse
from dotenv import load_dotenv
from tabulate import tabulate  # pip install tabulate
import re # Para parsear logs

# --- Constantes ---
__DESCRIPTION__ = "ProcMon - Monitor de Sistema e Processos"
__VERSION__ = "1.0.0"

# --- Configuração Inicial ---
# Encontra o diretório base (útil para PyInstaller)
if getattr(sys, 'frozen', False):
    # Se rodando como .exe (congelado pelo PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Se rodando como script .py
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Carrega variáveis do arquivo .env localizado no mesmo diretório
ENV_PATH = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=ENV_PATH)

# Lê configurações do .env ou usa defaults
DEFAULT_LOG_PATH = os.path.join(BASE_DIR, 'logs') # Default na subpasta 'logs'
LOG_PATH = os.getenv('PATH_LOG_FILES', DEFAULT_LOG_PATH)
FILENAME_TEMPLATE = os.getenv('PRINCIPAL_FILENAME_LOG', 'PROCESSMONITOR_%DATAHORA%.log')
MONITORING_PROCESS_NAMES = [p.strip() for p in os.getenv('MONITORING_PROCESSES', '').split(',') if p.strip()]
MONITOR_INTERVAL_SECONDS = int(os.getenv('MONITOR_INTERVAL_SECONDS', 5)) # Intervalo padrão de 5s

# Cria o diretório de log se não existir
os.makedirs(LOG_PATH, exist_ok=True)

# Dicionário para manter os loggers ativos (global e por processo)
loggers = {}
current_log_filenames = {}

# --- Funções Auxiliares ---

def get_timestamp_str():
    """Retorna o timestamp atual no formato YYYYMMDDHHMM."""
    return datetime.datetime.now().strftime("%Y%m%d%H%M")

def get_log_filename(template, timestamp_str, process_name=None):
    """Gera o nome completo do arquivo de log."""
    filename = template.replace('%DATAHORA%', timestamp_str)
    if process_name:
        filename = f"{process_name}_{filename}"
    return os.path.join(LOG_PATH, filename)

def setup_logger(name, log_file):
    """Configura e retorna um logger para um arquivo específico."""
    # Remover handler antigo se existir para este logger (evita duplicação)
    if name in loggers:
        # Acessa o logger existente
        logger = loggers[name]
        # Encontra e remove handlers antigos para evitar duplicidade ao trocar de hora
        for handler in list(logger.handlers): # Itera sobre uma cópia da lista
             if isinstance(handler, logging.FileHandler) and handler.baseFilename == current_log_filenames.get(name):
                 logger.removeHandler(handler)
                 handler.close() # Fecha o arquivo antigo
    else:
         # Cria um novo logger se for a primeira vez
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        # Evita que logs se propaguem para o logger raiz (que pode ter console handler)
        logger.propagate = False


    # Configura o formato da mensagem
    # Usamos '::' como separador para facilitar o parse depois
    log_format = '%(asctime)s :: %(levelname)s :: %(message)s'
    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')

    # Cria o handler do arquivo
    # Usamos FileHandler normal, pois a rotação é feita pela mudança de nome/hora
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # Adiciona o handler ao logger
    logger.addHandler(file_handler)

    loggers[name] = logger
    current_log_filenames[name] = log_file # Guarda o nome atual
    # print(f"DEBUG: Logger '{name}' configurado para o arquivo: {log_file}") # Debug
    return logger

def get_system_stats():
    """Coleta estatísticas globais de CPU e memória."""
    try:
        # Usamos interval=None para uma medição mais rápida/menos bloqueante no loop
        cpu_usage = psutil.cpu_percent(interval=None)
        memory_info = psutil.virtual_memory()
        memory_usage_percent = memory_info.percent
        return cpu_usage, memory_usage_percent
    except Exception as e:
        # Logamos no logger global se ele existir, senão printamos
        msg = f"Erro ao coletar estatísticas GLOBAIS: {e}"
        if 'global' in loggers:
            loggers['global'].error(msg)
        else:
            print(f"ERRO: {msg}", file=sys.stderr)
        return None, None

def get_process_stats(process_name):
    """Coleta estatísticas de CPU e memória para um processo específico (ou soma de vários com mesmo nome)."""
    total_cpu = 0.0
    total_mem_percent = 0.0
    process_found = False
    try:
        # Itera sobre todos os processos em execução
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                # psutil pode dar erro ao acessar alguns processos (ex: permissão)
                if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                    process_found = True
                    # cpu_percent() precisa ser chamado uma vez para inicializar, depois dá o uso desde a última chamada
                    # Para simplificar, pegamos o valor instantâneo (pode ser menos preciso que interval=)
                    # Dividir por psutil.cpu_count() pode ser necessário se cpu_percent > 100% (multi-core)
                    # Mas para monitoramento básico, o valor direto costuma ser útil.
                    total_cpu += proc.info['cpu_percent'] if proc.info['cpu_percent'] is not None else 0.0
                    total_mem_percent += proc.info['memory_percent'] if proc.info['memory_percent'] is not None else 0.0
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Ignora processos que não podem ser acessados ou já morreram
                continue
        if process_found:
            return total_cpu, total_mem_percent
        else:
            # Se o processo não foi encontrado rodando
            return 0.0, 0.0 # Retorna 0 se não encontrado, log será informativo
    except Exception as e:
        msg = f"Erro ao coletar estatísticas para o processo '{process_name}': {e}"
        # Tenta logar no logger específico ou global
        if process_name in loggers:
            loggers[process_name].error(msg)
        elif 'global' in loggers:
            loggers['global'].error(msg)
        else:
            print(f"ERRO: {msg}", file=sys.stderr)
        return None, None

# --- Funções para Comandos CLI ---

def list_monitoring_targets():
    """Lista os alvos de monitoramento configurados."""
    targets = ["global"] + MONITORING_PROCESS_NAMES
    print("Alvos de monitoramento configurados:")
    for target in targets:
        print(f"- {target}")

def find_latest_log(target_name):
    """Encontra o arquivo de log mais recente para um alvo específico."""
    pattern_part = FILENAME_TEMPLATE.split('%DATAHORA%')[0] # Parte antes do timestamp
    file_prefix = f"{target_name}_" if target_name != "global" else ""
    full_prefix = file_prefix + pattern_part
    latest_file = None
    latest_timestamp = ""

    try:
        for filename in os.listdir(LOG_PATH):
            if filename.startswith(full_prefix) and filename.endswith(".log"):
                # Extrai o timestamp YYYYMMDDHHMM do nome do arquivo
                match = re.search(r'(\d{12})', filename) # Procura 12 dígitos seguidos
                if match:
                    timestamp = match.group(1)
                    if timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_file = os.path.join(LOG_PATH, filename)
    except FileNotFoundError:
        print(f"ERRO: Diretório de logs não encontrado: {LOG_PATH}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERRO ao procurar logs para '{target_name}': {e}", file=sys.stderr)
        return None

    return latest_file

def read_last_log_entries(log_file, num_entries=5):
    """Lê as últimas N entradas de um arquivo de log."""
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return lines[-num_entries:]
    except FileNotFoundError:
        print(f"ERRO: Arquivo de log não encontrado: {log_file}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"ERRO ao ler o arquivo de log '{log_file}': {e}", file=sys.stderr)
        return []

def parse_log_line(line):
    """Extrai dados de uma linha de log formatada."""
    parts = line.split(' :: ')
    if len(parts) == 3:
        timestamp_str = parts[0]
        level = parts[1]
        message = parts[2].strip()
        # Extrai CPU e Memória da mensagem (ex: "Uso CPU: 12.3% | Uso Memória: 45.6%")
        cpu_match = re.search(r'Uso CPU:\s*([\d.]+)\%', message)
        mem_match = re.search(r'Uso Memória:\s*([\d.]+)\%', message)
        cpu = cpu_match.group(1) if cpu_match else 'N/A'
        mem = mem_match.group(1) if mem_match else 'N/A'
        return timestamp_str, cpu, mem
    return None, None, None

def display_log_summary(target_name):
    """Exibe as últimas entradas de log para um alvo em formato de tabela."""
    latest_log = find_latest_log(target_name)
    if not latest_log:
        print(f"Nenhum arquivo de log encontrado para '{target_name}'.")
        return

    print(f"Exibindo as últimas 5 entradas do log mais recente para '{target_name}':")
    print(f"Arquivo: {latest_log}")

    lines = read_last_log_entries(latest_log, 5)
    if not lines:
        print("Log vazio ou não pôde ser lido.")
        return

    table_data = []
    headers = ["Timestamp", "CPU (%)", "Memória (%)"]
    for line in lines:
        timestamp, cpu, mem = parse_log_line(line)
        if timestamp:
            table_data.append([timestamp, cpu, mem])

    if table_data:
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("Não foi possível parsear as linhas de log.")


# --- Loop Principal de Monitoramento ---

def main_monitor_loop():
    """Loop principal que coleta e registra as estatísticas periodicamente."""
    print(f"{__DESCRIPTION__} v{__VERSION__} - Iniciando modo de monitoramento...")
    print(f"Intervalo: {MONITOR_INTERVAL_SECONDS}s | Logs em: {LOG_PATH}")
    print(f"Processos monitorados: {MONITORING_PROCESS_NAMES if MONITORING_PROCESS_NAMES else 'Nenhum específico'}")
    print("Pressione Ctrl+C (ou pare o serviço) para interromper.")

    last_checked_hour_str = "" # Para controlar a rotação/criação de loggers

    try:
        while True:
            current_timestamp_str = get_timestamp_str()
            current_hour_str = current_timestamp_str[:-2] # YYYYMMDDHH

            # --- Rotação/Criação de Loggers por Hora ---
            if current_hour_str != last_checked_hour_str:
                print(f"DEBUG: Hora mudou para {current_hour_str}. Atualizando loggers...") # Debug
                # Configura/Recria logger global
                global_log_file = get_log_filename(FILENAME_TEMPLATE, current_timestamp_str)
                global_logger = setup_logger('global', global_log_file)
                global_logger.info(f"Iniciando/Continuando log para a hora {current_hour_str} neste arquivo.")

                # Configura/Recria loggers dos processos
                for proc_name in MONITORING_PROCESS_NAMES:
                    proc_log_file = get_log_filename(FILENAME_TEMPLATE, current_timestamp_str, process_name=proc_name)
                    proc_logger = setup_logger(proc_name, proc_log_file)
                    proc_logger.info(f"Iniciando/Continuando log do processo '{proc_name}' para a hora {current_hour_str} neste arquivo.")

                last_checked_hour_str = current_hour_str

            # --- Coleta e Log Global ---
            if 'global' in loggers:
                cpu, mem = get_system_stats()
                if cpu is not None:
                    log_message = f"Uso CPU: {cpu:.1f}% | Uso Memória: {mem:.1f}%"
                    loggers['global'].info(log_message)

            # --- Coleta e Log por Processo ---
            for proc_name in MONITORING_PROCESS_NAMES:
                if proc_name in loggers:
                    proc_cpu, proc_mem = get_process_stats(proc_name)
                    if proc_cpu is not None: # Se não houve erro na coleta
                        if proc_cpu == 0.0 and proc_mem == 0.0:
                             log_message = f"Processo '{proc_name}' não encontrado ou sem uso de recursos."
                             # Logar como WARNING ou INFO? INFO parece ok.
                             loggers[proc_name].info(log_message)
                        else:
                            log_message = f"Uso CPU: {proc_cpu:.1f}% | Uso Memória: {proc_mem:.1f}%"
                            loggers[proc_name].info(log_message)
                    # Se get_process_stats retornou None, o erro já foi logado lá


            # --- Espera ---
            time.sleep(MONITOR_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nMonitoramento interrompido pelo usuário (Ctrl+C).")
        if 'global' in loggers: loggers['global'].info("Monitoramento interrompido (KeyboardInterrupt).")
    except Exception as e:
        print(f"\nERRO CRÍTICO NO LOOP PRINCIPAL: {e}", file=sys.stderr)
        # Tenta logar o erro fatal se possível
        if 'global' in loggers: loggers['global'].critical(f"Erro crítico no loop principal: {e}", exc_info=True)
    finally:
        print("Finalizando ProcMon.")
        # Fecha todos os handlers de arquivo abertos
        for logger_name, logger_instance in loggers.items():
             for handler in list(logger_instance.handlers): # Itera sobre uma cópia
                 if isinstance(handler, logging.FileHandler):
                     logger_instance.removeHandler(handler)
                     handler.close()
        if 'global' in loggers and 'global' in current_log_filenames: loggers['global'].info("Monitoramento finalizado.")


# --- Ponto de Entrada Principal e CLI ---
if __name__ == "__main__":
    # Configura o parser de argumentos
    parser = argparse.ArgumentParser(description=f"{__DESCRIPTION__} v{__VERSION__}")

    parser.add_argument(
        '-l', '--list',
        nargs='?', # 0 ou 1 argumento
        const='_list_all_', # Valor se -l for usado sem argumento
        metavar='TARGET',
        help="Lista alvos monitorados ou exibe as últimas 5 entradas do log mais recente para o TARGET (ex: global, mysql)."
             " Se nenhum TARGET for fornecido, lista todos os alvos."
    )
    parser.add_argument(
        '-v', '--version',
        action='store_true', # Não espera valor, apenas a presença do flag
        help="Exibe a versão do script."
    )

    # Analisa os argumentos passados na linha de comando
    args = parser.parse_args()

    # Executa a ação com base nos argumentos
    if args.version:
        print(f"{__DESCRIPTION__}")
        print(f"Versão: {__VERSION__}")
        sys.exit(0) # Sai após exibir a versão

    elif args.list:
        if args.list == '_list_all_':
            list_monitoring_targets()
        else:
            target = args.list
            valid_targets = ["global"] + MONITORING_PROCESS_NAMES
            if target in valid_targets:
                display_log_summary(target)
            else:
                print(f"ERRO: Alvo '{target}' inválido.")
                print("Alvos válidos são:")
                list_monitoring_targets()
                sys.exit(1) # Sai com erro
        sys.exit(0) # Sai após listar/exibir logs

    # Se nenhum argumento CLI relevante foi passado, inicia o monitoramento
    else:
        main_monitor_loop()