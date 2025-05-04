
# ProcMon - Monitoramento de Processos

"""
 **Arquivo**: procmon_cli.py
 **Autor**: Natan Fiuza
 **Data**: 2025-05-04
 **Descrição**: Este arquivo contém a definição de todas as classes de modelo
 *Copyright (c) 2025, NatanFiuza.dev.br*
"""

import argparse
import os
import sys
import re

from tabulate import tabulate  

# Funções movidas de procmon.py (adaptadas para receber config)

def list_monitoring_targets(monitoring_processes):
    """Lista os alvos de monitoramento configurados."""
    targets = ["global"] + monitoring_processes
    print("Alvos de monitoramento configurados:")
    for target in targets:
        print(f"- {target}")


def find_latest_log(log_path, filename_template, target_name):
    """Encontra o arquivo de log mais recente para um alvo específico."""
    pattern_part = filename_template.split('%DATAHORA%')[0]
    file_prefix = f"{target_name}_" if target_name != "global" else ""
    full_prefix = file_prefix + pattern_part
    latest_file = None
    latest_timestamp = ""

    try:
        # Verifica se o diretório de log existe antes de listar
        if not os.path.isdir(log_path):
            print(
                f"AVISO: Diretório de logs não encontrado: {log_path}", file=sys.stderr)
            return None
        for filename in os.listdir(log_path):
            if filename.startswith(full_prefix) and filename.endswith(".log"):
                match = re.search(r'(\d{12})', filename)
                if match:
                    timestamp = match.group(1)
                    if timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_file = os.path.join(log_path, filename)
    except Exception as e:
        print(
            f"ERRO ao procurar logs para '{target_name}': {e}", file=sys.stderr)
        return None

    return latest_file


def read_last_log_entries(log_file, num_entries=5):
    """Lê as últimas N entradas de um arquivo de log."""
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Retorna as últimas N linhas ou todas se houver menos que N
            return lines[-num_entries:]
    except FileNotFoundError:
        # find_latest_log já deve ter prevenido isso, mas é bom verificar
        print(
            f"ERRO: Arquivo de log não encontrado ao tentar ler: {log_file}", file=sys.stderr)
        return []
    except Exception as e:
        print(
            f"ERRO ao ler o arquivo de log '{log_file}': {e}", file=sys.stderr)
        return []


def parse_log_line(line):
    """Extrai dados de uma linha de log formatada (incluindo PIDs)."""
    parts = line.split(' :: ')
    if len(parts) == 4:
        timestamp_str = parts[0]
        # level = parts[1] # Não usamos level na tabela
        pids_match = re.search(r'PIDs\[(.*)\]', parts[2])
        pids_str = pids_match.group(1) if pids_match else 'N/A'
        message = parts[3].strip()
        cpu_match = re.search(r'Uso CPU:\s*([\d.]+)\%', message)
        mem_match = re.search(r'Uso Memória:\s*([\d.]+)\%', message)
        cpu = cpu_match.group(1) if cpu_match else 'N/A'
        mem = mem_match.group(1) if mem_match else 'N/A'
        return timestamp_str, pids_str, cpu, mem
    return None, None, None, None


def display_log_summary(log_path, filename_template, target_name):
    """Exibe as últimas entradas de log para um alvo em formato de tabela."""
    latest_log = find_latest_log(log_path, filename_template, target_name)
    if not latest_log:
        print(f"Nenhum arquivo de log encontrado para '{target_name}'.")
        return

    print(
        f"Exibindo as últimas 5 entradas do log mais recente para '{target_name}':")
    print(f"Arquivo: {latest_log}")

    lines = read_last_log_entries(latest_log, 5)
    if not lines:
        print("Log vazio ou não pôde ser lido.")
        return

    table_data = []
    headers = ["Timestamp", "PIDs", "CPU (%)", "Memória (%)"]
    for line in lines:
        timestamp, pids, cpu, mem = parse_log_line(line)
        if timestamp:
            table_data.append([timestamp, pids, cpu, mem])

    if table_data:
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("Não foi possível parsear as linhas de log.")


# Função principal da CLI
def handle_cli_args(description, version, config):
    """
    Configura o argparse, processa argumentos da linha de comando e executa ações.

    Args:
        description (str): Descrição do script.
        version (str): Versão do script.
        config (dict): Dicionário contendo a configuração carregada (LOG_PATH, etc.).

    Returns:
        bool: True se o monitoramento principal deve prosseguir, False caso contrário.
    """
    parser = argparse.ArgumentParser(description=f"{description} v{version}")

    parser.add_argument(
        '-l', '--list',
        nargs='?',
        const='_list_all_',
        metavar='TARGET',
        help="Lista alvos monitorados ou exibe as últimas 5 entradas do log mais recente para o TARGET."
    )
    parser.add_argument(
        '-v', '--version',
        action='store_true',
        help="Exibe a versão do script."
    )

    args = parser.parse_args()

    monitoring_processes = config.get('MONITORING_PROCESS_NAMES', [])
    # Usa um default se não estiver no config
    log_path = config.get('LOG_PATH', './logs')
    filename_template = config.get(
        'FILENAME_TEMPLATE', 'PROCESSMONITOR_%DATAHORA%.log')

    if args.version:
        print(f"{description}")
        print(f"Versão: {version}")
        return False  # Não prosseguir com monitoramento

    elif args.list:
        if args.list == '_list_all_':
            list_monitoring_targets(monitoring_processes)
        else:
            target = args.list
            valid_targets = ["global"] + monitoring_processes
            if target in valid_targets:
                display_log_summary(log_path, filename_template, target)
            else:
                print(f"ERRO: Alvo '{target}' inválido.")
                print("Alvos válidos são:")
                list_monitoring_targets(monitoring_processes)
                # Considerar sair com erro: sys.exit(1) aqui? Ou apenas retornar False?
                # Retornar False é mais seguro para não interromper abruptamente se importado.
        return False  # Não prosseguir com monitoramento

    # Se nenhum argumento CLI relevante foi passado, prosseguir com monitoramento
    return True
