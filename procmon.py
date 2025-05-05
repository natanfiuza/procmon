# -*- coding: utf-8 -*-
# procmon.py (Arquivo Principal)
"""
Ponto de entrada principal para o ProcMon.
Carrega configuração, lida com CLI ou inicia o loop de monitoramento.
"""

from dotenv import load_dotenv
import os
import sys
import time
import datetime
import logging  # Ainda necessário para o logging no loop principal

# Importa dos nossos módulos customizados
from procmon_models import PidFilter
from procmon_utils import (
    setup_logger,
    get_timestamp_str,
    get_log_filename,
    get_system_stats,
    get_process_stats,
    get_top_processes,
    CoreInfoError,
    get_core_info,
    StatsCollectionError  # Importa a exceção customizada
)
import procmon_cli  # Importa o módulo CLI inteiro

# --- Constantes ---
__DESCRIPTION__ = "ProcMon - Monitor de Sistema e Processos"
__VERSION__ = "1.1.2"  # Incrementa a versão após refatoração

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
    'MONITOR_INTERVAL_SECONDS': int(os.getenv('MONITOR_INTERVAL_SECONDS', 5))
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
    global loggers, current_log_filenames

    # ... (mensagens iniciais de print) ...

    last_checked_hour_str = ""
    global_logger = None
    topten_logger = None  # Variável para guardar o logger topten

    try:
        while True:
            current_timestamp_str = get_timestamp_str()
            current_hour_str = current_timestamp_str[:-2]

            # --- Rotação/Criação de Loggers por Hora ---
            if current_hour_str != last_checked_hour_str:
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO: Verificando/Atualizando loggers para a hora {current_hour_str}...")

                # Configura/Recria logger global (sem alteração)
                global_log_file = get_log_filename(
                    config['LOG_PATH'], config['FILENAME_TEMPLATE'], current_timestamp_str)
                global_logger = setup_logger(
                    'global', global_log_file, loggers, current_log_filenames, pid_filter)
                if last_checked_hour_str != "":  # Evita logar na primeira vez que roda setup_logger
                    global_logger.info(
                        f"Rotacionando log. Continuando para a hora {current_hour_str} neste arquivo.")
                else:
                    global_logger.info(
                        f"Iniciando log para a hora {current_hour_str} neste arquivo.")

                # Configura/Recria loggers dos processos (sem alteração)
                for proc_name in config['MONITORING_PROCESS_NAMES']:
                    proc_log_file = get_log_filename(
                        config['LOG_PATH'], config['FILENAME_TEMPLATE'], current_timestamp_str, process_name=proc_name)
                    proc_logger = setup_logger(
                        proc_name, proc_log_file, loggers, current_log_filenames, pid_filter)
                    proc_logger.info(
                        f"Iniciando/Continuando log do processo '{proc_name}' para a hora {current_hour_str} neste arquivo.")

                # ---> Configura/Recria logger TopTen <---
                topten_logger_name = "topten"  # Nome para identificar o logger
                # Usa get_log_filename passando "topten" como 'process_name' para adicionar o prefixo
                topten_log_file = get_log_filename(
                    config['LOG_PATH'], config['FILENAME_TEMPLATE'], current_timestamp_str, process_name=topten_logger_name)
                topten_logger = setup_logger(
                    topten_logger_name, topten_log_file, loggers, current_log_filenames, pid_filter)
                topten_logger.info(
                    f"Iniciando/Continuando log Top 10 CPU para a hora {current_hour_str} neste arquivo.")
                # --------------------------------------

                last_checked_hour_str = current_hour_str

            # --- Coleta e Log Global --- (sem alteração)
            if global_logger:
                try:
                    cpu, mem = get_system_stats()
                    log_message = f"Uso CPU: {cpu:.1f}% | Uso Memória: {mem:.1f}%"
                    global_logger.info(log_message)
                except StatsCollectionError as e:
                    global_logger.error(f"Falha ao coletar stats globais: {e}")
                except Exception as e:
                    global_logger.error(
                        f"Erro inesperado na coleta global: {e}", exc_info=False)

            # --- Coleta e Log por Processo --- (sem alteração)
            for proc_name in config['MONITORING_PROCESS_NAMES']:
                # ... (código existente para log de processos específicos) ...
                proc_logger = loggers.get(proc_name)
                if proc_logger:
                    try:
                        proc_cpu, proc_mem, pids = get_process_stats(proc_name)
                        pids_str = ','.join(map(str, pids)) if pids else 'N/A'
                        extra_data = {'pids': pids_str}

                        if not pids:                            
                            log_message = f"Processo '{proc_name}' não encontrado ou sem uso de recursos."
                            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {log_message}")
                            #proc_logger.info(log_message, extra=extra_data) # Não loga se não houver PIDs
                        else:
                            log_message = f"Uso CPU: {proc_cpu:.1f}% | Uso Memória: {proc_mem:.1f}%"
                            proc_logger.info(log_message, extra=extra_data)
                    except StatsCollectionError as e:
                        proc_logger.error(
                            f"Falha ao coletar stats para '{proc_name}': {e}")
                    except Exception as e:
                       proc_logger.error(
                           f"Erro inesperado na coleta de '{proc_name}': {e}", exc_info=False)

            # ---> Coleta e Log Top 10 CPU <---
            if topten_logger:  # Verifica se o logger topten foi inicializado
                core_info_line = "Resumo CPU Sistema: Informações indisponíveis"  # Default
                try:
                    # ---> 1. Obter informações dos cores/uso sistema <---
                    core_data = get_core_info()  # Chama a nova função
                    # Formata os dados obtidos para o log, tratando possíveis Nones (embora a função deva levantar erro)
                    physical_cores_str = str(core_data.get('physical', '?'))
                    logical_cores_str = str(core_data.get('logical', '?'))
                    system_usage_val = core_data.get('system_usage_percent')
                    system_usage_str = f"{system_usage_val:.1f}%" if system_usage_val is not None else 'N/A'
                    # Cria a linha de resumo
                    core_info_line = f"Resumo CPU Sistema: Uso Total {system_usage_str} (Físicos: {physical_cores_str}, Lógicos: {logical_cores_str})"
                    # -----------------------------------------------------

                    # Coleta os top processos 
                    top_processes = get_top_processes(10,'mem')

                    # ---> 2. Formata a mensagem completa do log <---
                    log_lines = [
                        core_info_line,  # <-- Adiciona a linha de resumo criada acima
                        "Top 10 Processos por CPU:"
                    ]
                    # -------------------------------------------
                    if top_processes:
                        for p in top_processes:
                            log_lines.append(
                                f"  - PID: {p['pid']:<6} | CPU: {p['cpu']:>5.1f}% | Mem: {p['mem']:>5.1f}% | Nome: {p['name']}")
                    else:
                        log_lines.append(
                            "  (Nenhum processo encontrado ou erro na coleta)")

                    log_message = " $:".join(log_lines)
                    topten_logger.info(log_message)

                # ---> 3. Atualiza tratamento de erro para incluir CoreInfoError <---
                except CoreInfoError as e:
                    # Loga erro específico da coleta de info de cores e continua para Top 10 se possível
                    # (Ou loga apenas o erro e pula o log do Top 10 nesta iteração)
                    topten_logger.error(
                        f"Falha ao obter informações dos Cores/Uso CPU: {e}")
                    # Opcional: Tentar logar o Top10 mesmo sem a info dos cores?
                    # Se sim, precisaria reestruturar o try/except ou logar a lista 'log_lines' aqui
                    # Vamos manter simples: se falhar em obter core_info, apenas loga o erro.
                except StatsCollectionError as e:
                    # Loga erros específicos da coleta Top 10 (se core_info funcionou)
                    # Inclui info dos cores no erro
                    topten_logger.error(
                        f"Falha ao obter Top 10 processos: {e}\n{core_info_line}")
                except Exception as e:
                    # Loga outros erros inesperados
                    topten_logger.error(
                        f"Erro inesperado na seção Top 10: {e}\n{core_info_line}", exc_info=False)


            # --- Espera --- (sem alteração)
            time.sleep(config['MONITOR_INTERVAL_SECONDS'])

    # ... (blocos except KeyboardInterrupt, Exception e finally sem alteração) ...
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
        # ... (código finally sem alteração) ...
        print("Finalizando ProcMon.")
        # Itera sobre cópia dos valores
        for logger_instance in list(loggers.values()):
            for handler in list(logger_instance.handlers):
                if isinstance(handler, logging.FileHandler):
                    handler.close()
                    logger_instance.removeHandler(handler)
        # Log final apenas se o logger global existe
        if 'global' in loggers and loggers['global'].handlers:
            loggers['global'].info("Monitoramento finalizado.")
        elif global_logger:  # Fallback se o logger global foi criado mas saiu do dict
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
