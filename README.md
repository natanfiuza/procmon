# ProcMon - Monitor de Sistema e Processos

**Propósito:**

ProcMon é uma ferramenta de monitoramento desenvolvida em Python, projetada para registrar o uso de recursos do sistema (CPU e Memória RAM) ao longo do tempo. Ele oferece:

* Monitoramento do uso **global** de CPU e Memória.
* Monitoramento **individual** de processos específicos definidos pelo usuário.
* Geração de **arquivos de log separados** para o monitoramento global e para cada processo individual.
* **Rotação horária** dos arquivos de log, criando um novo arquivo a cada hora com timestamp no nome (`YYYYMMDDHHMM`).
* Configuração flexível através de um arquivo `.env`.
* Capacidade de ser compilado em um **executável standalone** (`.exe`) para Windows usando PyInstaller.
* Capacidade de ser executado como um **serviço Windows** utilizando o NSSM (Non-Sucking Service Manager).
* Uma **interface de linha de comando (CLI)** para visualizar a versão, listar alvos monitorados e exibir as últimas entradas de log de um alvo específico.

Esta ferramenta é útil para administradores de sistemas ou desenvolvedores que precisam acompanhar o consumo de recursos de um servidor ou de aplicações específicas ao longo do tempo para análise de desempenho ou diagnóstico de problemas.

## Funcionalidades Principais

* Monitoramento global de CPU e Memória.
* Monitoramento individual de processos (CPU/Memória) configurados via `.env`.
* Geração de logs horários com timestamps no nome do arquivo.
* Configuração flexível via arquivo `.env` (caminho dos logs, processos, template de nome de arquivo).
* Compilável em um executável único (`.exe`) com PyInstaller.
* Capacidade de rodar como serviço Windows usando NSSM.
* Interface de Linha de Comando (CLI) para:
    * Exibir versão (`-v`).
    * Listar alvos monitorados (`-l`).
    * Visualizar as últimas 5 entradas de log de um alvo específico (`-l <alvo>`).

## Pré-requisitos

Antes de começar, certifique-se de ter instalado:

1.  **Python:** Versão 3.7 ou superior recomendada. ([Download Python](https://www.python.org/downloads/))
2.  **Pipenv:** Gerenciador de pacotes e ambientes virtuais para Python.
    * Instale com pip: `pip install pipenv`
    * ([Documentação Pipenv](https://pipenv.pypa.io/en/latest/))
3.  **NSSM (Opcional - para rodar como serviço):** The Non-Sucking Service Manager.
    * ([Download NSSM](https://nssm.cc/download)) - Baixe e extraia o `nssm.exe` para um local acessível (ex: `C:\NSSM`) e, opcionalmente, adicione ao PATH do sistema.

## Instalação e Configuração do Ambiente (com Pipenv)

1.  **Clone o Repositório (ou crie a pasta do projeto):**
    ```bash
    git clone <url_do_seu_repositorio> # Se estiver usando git
    cd <pasta_do_projeto>
    # Ou apenas crie uma pasta e coloque o arquivo procmon.py dentro dela
    ```

2.  **Crie o `Pipfile`:**
    Crie um arquivo chamado `Pipfile` (sem extensão) na raiz do projeto com o seguinte conteúdo:

    ```toml
    [[source]]
    url = "[https://pypi.org/simple](https://pypi.org/simple)"
    verify_ssl = true
    name = "pypi

    [packages]
    psutil = "*"
    python-dotenv = "*"
    tabulate = "*"

    [dev-packages]
    pyinstaller = "*"

    [requires]
    python_version = "3.7" # Ou a versão mínima que você deseja suportar
    ```
    *Nota: As dependências em `[packages]` são necessárias para rodar o script/exe. A dependência em `[dev-packages]` (`pyinstaller`) é necessária apenas para *construir* o executável.*
    
    *Nota: Este arquivo e gerado automáticamente pelo `pipenv`.*

3.  **Instale as Dependências:**
    No terminal, dentro da pasta do projeto, execute:
    ```bash
    pipenv install --dev
    ```
    Este comando criará um ambiente virtual isolado para o projeto, lerá o `Pipfile` e instalará todas as dependências listadas (tanto `packages` quanto `dev-packages`). Ele também criará um arquivo `Pipfile.lock` para garantir builds determinísticos.

4.  **Ative o Ambiente Virtual:**
    Para executar comandos (como `python` ou `pyinstaller`) dentro do ambiente virtual criado, ative-o com:
    ```bash
    pipenv shell
    ```
    Você verá o nome do ambiente virtual no início do prompt do seu terminal, indicando que ele está ativo. Para desativar, digite `exit`.

## Configuração do ProcMon (`.env`)

1.  **Crie o arquivo `.env`:** Na raiz do projeto (mesma pasta do `procmon.py`), crie um arquivo chamado `.env`.

2.  **Adicione as Variáveis de Configuração:** Copie e cole o exemplo abaixo no seu `.env` e ajuste os valores conforme necessário:

    ```dotenv
    # Caminho onde os arquivos de log serão salvos
    PATH_LOG_FILES="C:\Projetos\ProcMon\logs"

    # Template para o nome do arquivo de log principal. %DATAHORA% será substituído.
    # Formato da DATAHORA: YYYYMMDDHHMM (AnoMesDiaHoraMinuto)
    PRINCIPAL_FILENAME_LOG="PROCESSMONITOR_%DATAHORA%.log"

    # Lista de nomes de processos a serem monitorados individualmente (separados por vírgula).
    # IMPORTANTE: Use o nome exato do executável do processo (ex: mysqld.exe, httpd.exe). Verifique no Gerenciador de Tarefas.
    # Deixe em branco para não monitorar nenhum processo específico.
    MONITORING_PROCESSES="mysqld,httpd"

    # Intervalo entre verificações em segundos (opcional, default é 60)
    MONITOR_INTERVAL_SECONDS=60
    ```

3.  **Verifique o Caminho dos Logs:** Certifique-se de que o diretório especificado em `PATH_LOG_FILES` exista ou que o script tenha permissão para criá-lo.

## Construindo o Executável (`procmon.exe`)

1.  **Ative o Ambiente Virtual:**
    ```bash
    pipenv shell
    ```

2.  **Execute o PyInstaller:**
    ```bash
    pyinstaller --onefile --name procmon procmon.py
    ```
    * `--onefile`: Cria um único arquivo `.exe`.
    * `--name procmon`: Define o nome do executável.
    * (Opcional) Adicione `--noconsole` se não quiser que uma janela de terminal apareça ao executar (pode ser útil para serviços, mas dificulta a depuração inicial).

3.  **Localize o Executável:** O arquivo `procmon.exe` será criado na subpasta `dist`.

4.  **Copie o `.env`:** **Muito importante!** Copie o arquivo `.env` que você configurou para a mesma pasta onde está o `procmon.exe` (a pasta `dist`). O executável procurará o `.env` ao seu lado.

## Executando o ProcMon

Você pode executar o ProcMon de diferentes maneiras:

### 1. Como Script Python (para desenvolvimento/teste)

1.  Certifique-se de que o ambiente virtual está ativo (`pipenv shell`).
2.  Execute o script diretamente:
    ```bash
    python procmon.py
    ```
3.  O monitoramento iniciará e os logs serão gerados conforme configurado. Pressione `Ctrl+C` para parar.

### 2. Como Executável Standalone

1.  Navegue até a pasta `dist` (ou onde você colocou `procmon.exe` e `.env`).
2.  Execute o arquivo:
    ```bash
    .\procmon.exe
    ```
3.  O monitoramento iniciará. Se executado diretamente em um console, pressione `Ctrl+C` para parar.

### 3. Como Serviço Windows (usando NSSM)

Esta é a forma recomendada para monitoramento contínuo em segundo plano.

1.  **Abra o Prompt de Comando ou PowerShell como Administrador.**
2.  Use o NSSM para instalar o serviço (substitua `ProcMonService` pelo nome desejado e use o caminho correto para `nssm.exe`):
    ```bash
    C:\NSSM\nssm.exe install ProcMonService
    ```
3.  **Configure na janela do NSSM:**
    * **Aba `Application`:**
        * **Path:** Navegue e selecione o seu `procmon.exe` (ex: `C:\Projetos\ProcMon\dist\procmon.exe`).
        * **Startup directory:** Defina **exatamente** a pasta onde o `procmon.exe` está localizado (ex: `C:\Projetos\ProcMon\dist`). **Isto é crucial para encontrar o `.env`!**
        * **Arguments:** Deixe em branco.
    * **(Opcional)** Configure outras abas como `Details`, `I/O`, `Exit actions` (recomendado configurar reinício em caso de falha).
4.  Clique em **Install service**.
5.  **Gerencie o Serviço:**
    * Iniciar: `nssm start ProcMonService` (ou via `services.msc`)
    * Parar: `nssm stop ProcMonService` (ou via `services.msc`)
    * Status: `nssm status ProcMonService`
    * Editar: `nssm edit ProcMonService` (pare o serviço antes)
    * Remover: `nssm remove ProcMonService` (pare o serviço antes)

## Usando a Interface de Linha de Comando (CLI)

Execute `procmon.exe` (ou `python procmon.py` no ambiente ativo) com os seguintes argumentos:

* **Exibir Versão:**
    ```bash
    procmon.exe -v
    ```
    ou
    ```bash
    procmon.exe --version
    ```

* **Listar Alvos Monitorados:** (Mostra "global" e os processos do `.env`)
    ```bash
    procmon.exe -l
    ```
    ou
    ```bash
    procmon.exe --list
    ```

* **Exibir Últimos Logs de um Alvo:** (Mostra as últimas 5 entradas do log mais recente para o alvo especificado)
    ```bash
    procmon.exe -l global
    ```
    ```bash
    procmon.exe -l <nome_do_processo>
    # Exemplo: procmon.exe -l mysqld
    ```

## Arquivos de Log

* Os logs são salvos no diretório definido em `PATH_LOG_FILES` no arquivo `.env`.
* Um novo arquivo de log é criado a cada hora.
* **Formato do Nome:**
    * Global: `[TEMPLATE]_YYYYMMDDHHMM.log` (ex: `PROCESSMONITOR_202505031800.log`)
    * Processo Específico: `<nome_processo>_[TEMPLATE]_YYYYMMDDHHMM.log` (ex: `mysqld_PROCESSMONITOR_202505031800.log`)
* **Formato das Linhas de Log:**
    ```
    YYYY-MM-DD HH:MM:SS :: LEVEL :: Mensagem (ex: Uso CPU: 15.2% | Uso Memória: 30.5%)
    ```
    * `LEVEL` pode ser `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

---