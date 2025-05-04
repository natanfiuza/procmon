# -*- coding: utf-8 -*-
# procmon.py (Arquivo Principal)
"""
Ponto de entrada principal para o ProcMon.
Carrega configuração, lida com CLI ou inicia o loop de monitoramento.
"""

import os
import sys
import time
import datetime
import logging  # Ainda necessário para o logging no loop principal
from dotenv import load_dotenv

# Importa dos nossos módulos customizados
from procmon_models import PidFilter
from procmon_utils import (
    setup_logger,
    get_timestamp_str,
    get_log_filename,
    get_system_stats,
    get_process_stats,
    StatsCollectionError  # Importa a exceção customizada
)
import procmon_cli  # Importa o módulo CLI inteiro

# --- Constantes ---
__DESCRIPTION__ = "ProcMon - Monitor de Sistema e Processos"
__VERSION__ = "1.1.0"  # Incrementa a versão após refatoração

# --- Configuração Inicial ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ENV_PATH = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=ENV_PATH)

# Carrega configurações em um dicionário
config = {
    'LOG_PATH': os.getenv('PATH_LOG_FILES', os.path.join(BASE_DIR, 'logs')),
    'FILENAME_TEMPLATE': os.getenv('PRINCIPAL_FILENAME_LOG', 'PROCESSMONITOR_%DATAHORA%.log'),
    'MONITORING_PROCESS_NAMES': [p.strip() for p in os.getenv('MONITORING_PROCESSES', '').split(',') if p.strip()],
    'MONITOR_INTERVAL_SECONDS': int(os.getenv('MONITOR_INTERVAL_SECONDS', 60))
}

# Cria o diretório de log se não existir
try:
    os.makedirs(config['LOG_PATH'], exist_ok=True)
except OSError as e:
    print(
        f"ERRO CRÍTICO: Não foi possível criar o diretório de logs '{config['LOG_PATH']}'. Erro: {e}", file=sys.stderr)
    print("Verifique as permissões ou o caminho definido em PATH_LOG_FILES no arquivo .env", file=sys.stderr)
    sys.exit(1)  # Aborta a execução


# Dicionários globais para gerenciar loggers e nomes de arquivos atuais
loggers = {}
current_log_filenames = {}
# Instancia o filtro PID
pid_filter = PidFilter()

# --- Loop Principal de Monitoramento --- (Movido para uma função)


def main_monitor_loop():
    """Loop principal que coleta e registra as estatísticas periodicamente."""
    global loggers, current_log_filenames  # Precisa acessar/modificar globais

    print(f"{__DESCRIPTION__} v{__VERSION__} - Iniciando modo de monitoramento...")
    print(
        f"Intervalo: {config['MONITOR_INTERVAL_SECONDS']}s | Logs em: {config['LOG_PATH']}")
    print(
        f"Processos monitorados: {config['MONITORING_PROCESS_NAMES'] if config['MONITORING_PROCESS_NAMES'] else 'Nenhum específico'}")
    print("Pressione Ctrl+C (ou pare o serviço) para interromper.")

    last_checked_hour_str = ""
    global_logger = None  # Guarda referência ao logger global para mensagens de erro/fim

    try:
        while True:
            current_timestamp_str = get_timestamp_str()
            current_hour_str = current_timestamp_str[:-2]

            # --- Rotação/Criação de Loggers por Hora ---
            if current_hour_str != last_checked_hour_str:
                # Adiciona um log simples no console
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO: Verificando/Atualizando loggers para a hora {current_hour_str}...")

                # Configura/Recria logger global
                global_log_file = get_log_filename(
                    config['LOG_PATH'], config['FILENAME_TEMPLATE'], current_timestamp_str)
                # Passa os dicionários e o filtro para a função utilitária
                global_logger = setup_logger(
                    'global', global_log_file, loggers, current_log_filenames, pid_filter)
                global_logger.info(
                    f"Iniciando/Continuando log para a hora {current_hour_str} neste arquivo.")

                # Configura/Recria loggers dos processos
                for proc_name in config['MONITORING_PROCESS_NAMES']:
                    proc_log_file = get_log_filename(
                        config['LOG_PATH'], config['FILENAME_TEMPLATE'], current_timestamp_str, process_name=proc_name)
                    proc_logger = setup_logger(
                        proc_name, proc_log_file, loggers, current_log_filenames, pid_filter)
                    proc_logger.info(
                        f"Iniciando/Continuando log do processo '{proc_name}' para a hora {current_hour_str} neste arquivo.")

                last_checked_hour_str = current_hour_str

            # --- Coleta e Log Global ---
            if global_logger:  # Verifica se o logger global foi inicializado
                try:
                    cpu, mem = get_system_stats()  # Chama a função do utils
                    log_message = f"Uso CPU: {cpu:.1f}% | Uso Memória: {mem:.1f}%"
                    # Loga normalmente (o filtro cuidará do PID='N/A')
                    global_logger.info(log_message)
                except StatsCollectionError as e:
                    # Loga o erro levantado pela função utilitária
                    global_logger.error(f"Falha ao coletar stats globais: {e}")
                except Exception as e:
                    # Loga outros erros inesperados na coleta global
                    # exc_info=False para não poluir muito
                    global_logger.error(
                        f"Erro inesperado na coleta global: {e}", exc_info=False)

            # --- Coleta e Log por Processo ---
            for proc_name in config['MONITORING_PROCESS_NAMES']:
                # Pega o logger já configurado
                proc_logger = loggers.get(proc_name)
                if proc_logger:
                    try:
                        proc_cpu, proc_mem, pids = get_process_stats(
                            proc_name)  # Chama a função do utils
                        pids_str = ','.join(map(str, pids)) if pids else 'N/A'
                        extra_data = {'pids': pids_str}

                        if not pids:
                            log_message = f"Processo '{proc_name}' não encontrado ou sem uso de recursos."
                            proc_logger.info(log_message, extra=extra_data)
                        else:
                            log_message = f"Uso CPU: {proc_cpu:.1f}% | Uso Memória: {proc_mem:.1f}%"
                            proc_logger.info(log_message, extra=extra_data)
                    except StatsCollectionError as e:
                        # Loga o erro levantado pela função utilitária
                        proc_logger.error(
                            f"Falha ao coletar stats para '{proc_name}': {e}")
                    except Exception as e:
                        # Loga outros erros inesperados na coleta do processo
                       proc_logger.error(
                           f"Erro inesperado na coleta de '{proc_name}': {e}", exc_info=False)

            # --- Espera ---
            time.sleep(config['MONITOR_INTERVAL_SECONDS'])

    except KeyboardInterrupt:
        print("\nMonitoramento interrompido pelo usuário (Ctrl+C).")
        if global_logger:
            global_logger.warning(
                "Monitoramento interrompido (KeyboardInterrupt).")
    except Exception as e:
        errmsg = f"ERRO CRÍTICO NO LOOP PRINCIPAL: {e}"
        print(f"\n{errmsg}", file=sys.stderr)
        if global_logger:
            global_logger.critical(errmsg, exc_info=True)
    finally:
        print("Finalizando ProcMon.")
        # Fecha todos os handlers de arquivo abertos
        for logger_instance in loggers.values():
            for handler in list(logger_instance.handlers):
                if isinstance(handler, logging.FileHandler):
                    handler.close()  # Garante que o arquivo seja fechado
                    logger_instance.removeHandler(
                        handler)  # Opcional, mas limpa
        if global_logger:
            global_logger.info("Monitoramento finalizado.")


# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    # Chama a função da CLI para processar argumentos
    # Ela retorna True se o monitoramento deve iniciar, False caso contrário
    should_run_monitor = procmon_cli.handle_cli_args(
        __DESCRIPTION__, __VERSION__, config)

    if should_run_monitor:
        main_monitor_loop()  # Inicia o loop de monitoramento
    else:
        # A função da CLI já imprimiu a saída necessária (versão, lista, logs) ou erro.
        # Apenas encerra o script silenciosamente.
        pass
