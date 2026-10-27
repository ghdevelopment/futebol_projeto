# app.py — SERVIDOR PRONTO PARA O PROJETO (FLASK + MYSQL/MARIADB)
#
# Este servidor funciona com QUALQUER banco e QUALQUER tabela.
# O grupo não precisa escrever Python. O trabalho do grupo é:
#   1. criar o banco e as tabelas do seu cenário (arquivo banco.sql);
#   2. ajustar o CONFIG_BANCO logo abaixo;
#   3. criar as páginas HTML (pasta templates) e o CSS (pasta static).
#
# Caminho da informação (o mesmo de sempre):
# navegador (formulário) -> Flask (app.py) -> PyMySQL -> banco do grupo
#
# O QUE ESTE SERVIDOR JÁ SABE FAZER
#   Endereço                    O que acontece
#   /                           abre templates/index.html
#   /qualquer_nome              abre templates/qualquer_nome.html
#   /painel                     mostra todas as tabelas do banco (para testar)
#   /salvar/<tabela>            INSERT  (formulário com method="post")
#   /atualizar/<tabela>/<id>    UPDATE  (formulário com method="post")
#   /excluir/<tabela>/<id>      DELETE  (formulário com method="post")
#
#   Dentro do HTML existem três funções prontas:
#   listar("tabela")            todas as linhas de uma tabela
#   buscar("tabela", id)        uma linha só (para páginas de edição)
#   consultar("SELECT ...")     qualquer SELECT, inclusive com JOIN
#
# REGRA DE OURO: o atributo name de cada campo do formulário
# precisa ser IGUAL ao nome da coluna no banco.

# 1. IMPORTAÇÕES
# Flask: cria o servidor web.
# render_template: abre um arquivo HTML da pasta templates.
# request: dá acesso ao que foi enviado pelo formulário.
# redirect: manda o navegador para outra página.
# pymysql: biblioteca que conversa com o MySQL e com o MariaDB.
import re
from datetime import date, datetime
from decimal import Decimal

from flask import Flask, render_template, render_template_string, request, redirect, url_for
from jinja2 import TemplateNotFound, Undefined
from markupsafe import Markup
import pymysql
import pymysql.cursors

# 2. CONFIGURAÇÃO DA CONEXÃO  <-- A ÚNICA PARTE QUE O GRUPO ALTERA
# Ajuste estes valores de acordo com o banco instalado na máquina.
# A porta padrão do MySQL e do MariaDB é 3306.
# No XAMPP, normalmente o usuário é "root" e a senha é vazia "".
CONFIG_BANCO = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "sesidb",
    "database": "interclasse",  # troque pelo nome do banco do seu grupo
    "charset": "utf8mb4",
}

# 3. CRIAÇÃO DA APLICAÇÃO
# __name__ informa ao Flask onde está este arquivo,
# para ele encontrar as pastas templates e static.
app = Flask(__name__)

# Campo vazio no banco (NULL) chega no Python como None.
# Esta linha faz o HTML mostrar "nada" em vez da palavra None.
app.jinja_env.finalize = lambda valor: "" if valor is None else valor


# 4. CONEXÃO COM O BANCO
class ErroDoProjeto(Exception):
    """Erro com explicação em português, mostrado numa página amigável."""

    def __init__(self, mensagem, dica="", status=400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.dica = dica
        self.status = status


def conectar():
    # O ** "desempacota" o dicionário: é o mesmo que escrever
    # pymysql.connect(host="localhost", port=3306, user="root", ...)
    # DictCursor faz cada linha virar um dicionário:
    # no HTML escrevemos linha.nome em vez de linha[1].
    try:
        return pymysql.connect(**CONFIG_BANCO, cursorclass=pymysql.cursors.DictCursor)
    except RuntimeError as erro:
        # O MySQL 8 usa um tipo de login que exige o pacote cryptography.
        if "cryptography" in str(erro):
            raise ErroDoProjeto(
                "O MySQL 8 exige um pacote extra do Python para fazer o login.",
                "No terminal, rode: pip install cryptography — e inicie o servidor de novo.",
                500,
            )
        raise


def executar(sql, valores=(), alterou=False):
    # O mesmo passo a passo de sempre:
    # conectar -> criar cursor -> executar SQL -> (commit, se alterou) -> fechar.
    conexao = conectar()
    try:
        cursor = conexao.cursor()
        # Os %s são preenchidos pelo PyMySQL com segurança (contra SQL Injection).
        # Sem valores passamos None, para um % do SQL (ex.: LIKE 'A%') não atrapalhar.
        cursor.execute(sql, valores or None)
        linhas = cursor.fetchall()
        if alterou:
            conexao.commit()  # sem commit, INSERT/UPDATE/DELETE não ficam salvos
        cursor.close()
        return linhas
    finally:
        conexao.close()  # fecha a conexão mesmo se der erro


# 5. ESTRUTURA DO BANCO
# O MySQL guarda a descrição de todas as tabelas num banco especial chamado
# information_schema. É lendo ele que o servidor se adapta a qualquer cenário.
def _texto(linhas):
    # Algumas versões do MySQL devolvem textos do information_schema como bytes.
    return [
        {chave: valor.decode() if isinstance(valor, bytes) else valor for chave, valor in linha.items()}
        for linha in linhas
    ]


def tabelas_do_banco():
    return _texto(executar(
        "SELECT TABLE_NAME AS nome, TABLE_TYPE AS tipo FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME",
        (CONFIG_BANCO["database"],),
    ))


def colunas_da_tabela(tabela):
    return _texto(executar(
        "SELECT COLUMN_NAME AS nome, DATA_TYPE AS tipo, COLUMN_TYPE AS tipo_completo, "
        "IS_NULLABLE AS aceita_nulo, COLUMN_DEFAULT AS padrao, COLUMN_KEY AS chave, "
        "EXTRA AS extra, CHARACTER_MAXIMUM_LENGTH AS tamanho "
        "FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
        (CONFIG_BANCO["database"], tabela),
    ))


def chaves_estrangeiras(tabela):
    return _texto(executar(
        "SELECT COLUMN_NAME AS coluna, REFERENCED_TABLE_NAME AS tabela_ref, "
        "REFERENCED_COLUMN_NAME AS coluna_ref "
        "FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL",
        (CONFIG_BANCO["database"], tabela),
    ))


def conferir_tabela(nome):
    # Só aceitamos nomes de tabelas que existem de verdade no banco.
    # Isso protege o SQL, já que nome de tabela não pode ir num %s.
    tabelas = tabelas_do_banco()
    for tabela in tabelas:
        if tabela["nome"].lower() == nome.lower():
            return tabela["nome"]
    existentes = ", ".join(t["nome"] for t in tabelas) or "nenhuma (rode o banco.sql)"
    raise ErroDoProjeto(
        f"A tabela '{nome}' não existe no banco '{CONFIG_BANCO['database']}'.",
        f"Confira o nome usado no action do formulário ou no listar(). Tabelas que existem: {existentes}.",
        404,
    )


def conferir_coluna(tabela, colunas, nome):
    for coluna in colunas:
        if coluna["nome"].lower() == nome.lower():
            return coluna
    existentes = ", ".join(c["nome"] for c in colunas)
    raise ErroDoProjeto(
        f"A tabela '{tabela}' não tem a coluna '{nome}'.",
        "No formulário, o name de cada campo precisa ser igual ao nome da coluna. "
        f"Colunas que existem: {existentes}.",
    )


def chave_primaria(tabela, colunas):
    chaves = [c["nome"] for c in colunas if c["chave"] == "PRI"]
    if len(chaves) != 1:
        raise ErroDoProjeto(
            f"Para editar ou excluir, a tabela '{tabela}' precisa de UMA coluna PRIMARY KEY.",
            "Exemplo: id INT AUTO_INCREMENT PRIMARY KEY. "
            "Em tabelas de ligação (N:N), crie também uma coluna id.",
        )
    return chaves[0]


# 6. CONVERSÃO DOS VALORES DO FORMULÁRIO
# Tudo que vem do formulário chega como texto (str).
# Aqui ajustamos o texto para o tipo da coluna no banco.
INTEIROS = {"tinyint", "smallint", "mediumint", "int", "integer", "bigint", "year", "bit"}
DECIMAIS = {"decimal", "numeric", "float", "double", "real"}
TEXTOS_LONGOS = {"text", "tinytext", "mediumtext", "longtext"}


def converter_valor(texto, coluna):
    texto = texto.strip()
    if texto == "":
        return None  # campo vazio vira NULL
    tipo = coluna["tipo"]
    if tipo in INTEIROS or tipo in DECIMAIS:
        if texto.lower() in ("on", "sim", "true"):  # checkbox marcado
            return 1
        texto = texto.replace("R$", "").replace(" ", "")
        if "," in texto:  # aceita o jeito brasileiro: 1.234,56 -> 1234.56
            texto = texto.replace(".", "").replace(",", ".")
        return texto
    if tipo in ("datetime", "timestamp"):
        return texto.replace("T", " ")  # o input datetime-local envia 2026-10-26T14:30
    return texto


def dados_do_formulario(tabela, colunas):
    dados = {}
    for campo in request.form:
        if campo.startswith("_"):  # campos com _ no começo são de controle (ex.: _voltar)
            continue
        coluna = conferir_coluna(tabela, colunas, campo)
        valores = request.form.getlist(campo)  # vários checkboxes com o mesmo name
        texto = ", ".join(v.strip() for v in valores if v.strip()) if len(valores) > 1 else valores[0]
        dados[coluna["nome"]] = converter_valor(texto, coluna)
    if not dados:
        raise ErroDoProjeto(
            "O formulário não enviou nenhum campo.",
            'Confira se cada <input> tem o atributo name e se o <form> tem method="post".',
        )
    return dados


def voltar():
    # Depois de gravar, volta para a página que enviou o formulário.
    # Para ir a outra página, coloque no form: <input type="hidden" name="_voltar" value="/">
    return redirect(request.form.get("_voltar") or request.referrer or "/")


# 7. ROTAS DAS PÁGINAS DO GRUPO
@app.route("/")
def pagina_inicial():
    return abrir_pagina("index")


@app.route("/<pagina>")
def outra_pagina(pagina):
    return abrir_pagina(pagina)


def abrir_pagina(nome):
    if nome.endswith(".html"):  # /cadastro e /cadastro.html funcionam igual
        nome = nome[:-5]
    try:
        return render_template(f"{nome}.html")
    except TemplateNotFound as erro:
        if erro.name != f"{nome}.html":
            raise  # o que falta é outro arquivo (ex.: um include), não a página
        if nome == "index":
            return redirect(url_for("painel"))  # ainda não há site: mostra o painel
        raise ErroDoProjeto(
            f"Não existe o arquivo templates/{nome}.html",
            f"Crie o arquivo na pasta templates ou corrija o link (href=\"/{nome}\").",
            404,
        )


# 8. ROTAS QUE ALTERAM O BANCO
@app.route("/salvar/<tabela>", methods=["POST"])
def salvar(tabela):
    tabela = conferir_tabela(tabela)
    colunas = colunas_da_tabela(tabela)
    # Campos vazios ficam de fora: o banco usa o DEFAULT ou o AUTO_INCREMENT.
    dados = {c: v for c, v in dados_do_formulario(tabela, colunas).items() if v is not None}
    if not dados:
        raise ErroDoProjeto("Todos os campos do formulário chegaram vazios.", "Preencha o formulário antes de enviar.")
    nomes = ", ".join(f"`{c}`" for c in dados)
    espacos = ", ".join(["%s"] * len(dados))
    executar(f"INSERT INTO `{tabela}` ({nomes}) VALUES ({espacos})", tuple(dados.values()), alterou=True)
    return voltar()


@app.route("/atualizar/<tabela>/<id>", methods=["POST"])
def atualizar(tabela, id):
    tabela = conferir_tabela(tabela)
    colunas = colunas_da_tabela(tabela)
    chave = chave_primaria(tabela, colunas)
    dados = dados_do_formulario(tabela, colunas)
    dados.pop(chave, None)  # o id não muda
    if dados:
        trocas = ", ".join(f"`{c}` = %s" for c in dados)
        executar(f"UPDATE `{tabela}` SET {trocas} WHERE `{chave}` = %s", (*dados.values(), id), alterou=True)
    return voltar()


@app.route("/excluir/<tabela>/<id>", methods=["GET", "POST"])
def excluir(tabela, id):
    tabela = conferir_tabela(tabela)
    chave = chave_primaria(tabela, colunas_da_tabela(tabela))
    executar(f"DELETE FROM `{tabela}` WHERE `{chave}` = %s", (id,), alterou=True)
    return voltar()


# 9. FUNÇÕES QUE O HTML PODE USAR
def listar(tabela, ordem=None):
    # listar("jogadores")  ou  listar("jogadores", ordem="nome")  ou  ordem="nome desc"
    tabela = conferir_tabela(tabela)
    sql = f"SELECT * FROM `{tabela}`"
    if ordem:
        partes = ordem.split()
        coluna = conferir_coluna(tabela, colunas_da_tabela(tabela), partes[0])
        sql += f" ORDER BY `{coluna['nome']}`"
        if len(partes) > 1 and partes[1].lower() == "desc":
            sql += " DESC"
    return executar(sql)


def _sem_indefinido(valor):
    # request.args.id sem ?id= no endereço chega como "indefinido": tratamos como None.
    return None if isinstance(valor, Undefined) else valor


def buscar(tabela, id):
    # buscar("times", request.args.id) -> uma linha (ou None se não achar)
    id = _sem_indefinido(id)
    if id in (None, ""):
        return None
    tabela = conferir_tabela(tabela)
    chave = chave_primaria(tabela, colunas_da_tabela(tabela))
    linhas = executar(f"SELECT * FROM `{tabela}` WHERE `{chave}` = %s", (id,))
    return linhas[0] if linhas else None


def consultar(sql, *valores):
    # consultar("SELECT j.nome, t.nome AS time FROM jogadores j JOIN times t ON t.id = j.time_id")
    # consultar("SELECT * FROM jogadores WHERE time_id = %s", 3)
    if not sql.strip().lower().startswith(("select", "with", "show")):
        raise ErroDoProjeto(
            "consultar() serve só para SELECT.",
            "Para gravar dados, use um formulário com action=\"/salvar/nome_da_tabela\".",
        )
    return executar(sql, tuple(_sem_indefinido(v) for v in valores))


def dinheiro(valor):
    # {{ produto.preco | dinheiro }} -> R$ 1.234,50
    if valor is None or str(valor).strip() == "":
        return ""
    try:
        texto = f"{Decimal(str(valor).replace(',', '.')):,.2f}"
    except ArithmeticError:
        return valor  # não é número: mostra como está
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def data_br(valor):
    # {{ partida.data | data_br }} -> 26/10/2026
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return valor


app.jinja_env.globals.update(listar=listar, buscar=buscar, consultar=consultar)
app.jinja_env.filters.update(dinheiro=dinheiro, data_br=data_br)


# 10. PAINEL: MOSTRA O BANCO E GERA O CÓDIGO HTML DE CADA TABELA
def acesso(variavel, coluna):
    # linha.nome é mais fácil de ler; linha["nome"] funciona para qualquer nome.
    if coluna.isidentifier() and not hasattr(dict, coluna):
        return f"{variavel}.{coluna}"
    return f'{variavel}["{coluna}"]'


def tipo_do_campo(coluna):
    tipo = coluna["tipo"]
    nome = coluna["nome"].lower()
    if coluna["tipo_completo"].lower().startswith("tinyint(1)") or tipo in ("bool", "boolean"):
        return "sim_nao"
    if tipo == "enum":
        return "enum"
    if tipo in INTEIROS:
        return "inteiro"
    if tipo in DECIMAIS:
        return "decimal"
    if tipo in ("date", "time"):
        return tipo
    if tipo in ("datetime", "timestamp"):
        return "datetime-local"
    if tipo in TEXTOS_LONGOS:
        return "textarea"
    if "blob" in tipo or "binary" in tipo:
        return None  # arquivos não entram no formulário
    if "email" in nome:
        return "email"
    if "senha" in nome:
        return "password"
    if "telefone" in nome or "celular" in nome:
        return "tel"
    return "text"


def codigo_do_formulario(tabela, colunas, estrangeiras):
    linhas = [f'<form method="post" action="/salvar/{tabela}">']
    for coluna in colunas:
        tipo = tipo_do_campo(coluna)
        if "auto_increment" in coluna["extra"] or tipo is None:
            continue
        nome = coluna["nome"]
        exigido = " required" if coluna["aceita_nulo"] == "NO" and coluna["padrao"] is None else ""
        rotulo = nome[:-3] if nome in estrangeiras and nome.endswith("_id") else nome  # time_id -> Time
        linhas.append(f"    <label>{rotulo.replace('_', ' ').capitalize()}")
        if nome in estrangeiras:
            ref = estrangeiras[nome]
            linhas += [
                f'        <select name="{nome}"{exigido}>',
                '            <option value="">Escolha...</option>',
                '            {% for item in listar("' + ref["tabela"] + '") %}',
                '            <option value="{{ ' + acesso("item", ref["coluna"]) + ' }}">{{ '
                + acesso("item", ref["rotulo"]) + " }}</option>",
                "            {% endfor %}",
                "        </select>",
            ]
        elif tipo == "enum":
            opcoes = [o.replace("''", "'") for o in re.findall(r"'((?:[^']|'')*)'", coluna["tipo_completo"])]
            linhas.append(f'        <select name="{nome}"{exigido}>')
            linhas.append('            <option value="">Escolha...</option>')
            linhas += [f'            <option value="{o}">{o}</option>' for o in opcoes]
            linhas.append("        </select>")
        elif tipo == "sim_nao":
            linhas += [
                f'        <select name="{nome}"{exigido}>',
                '            <option value="1">Sim</option>',
                '            <option value="0">Não</option>',
                "        </select>",
            ]
        elif tipo == "textarea":
            linhas.append(f'        <textarea name="{nome}"{exigido}></textarea>')
        else:
            extras = {"inteiro": ' step="1"', "decimal": ' step="any"'}.get(tipo, "")
            tipo_html = "number" if tipo in ("inteiro", "decimal") else tipo
            if coluna["tamanho"] and tipo_html in ("text", "email", "password", "tel"):
                extras += f' maxlength="{coluna["tamanho"]}"'
            linhas.append(f'        <input type="{tipo_html}" name="{nome}"{extras}{exigido}>')
        linhas.append("    </label>")
    linhas += ['    <button type="submit">Salvar</button>', "</form>"]
    return "\n".join(linhas)


def codigo_da_lista(tabela, colunas, chave):
    linhas = ["<table>", "    <tr>"]
    linhas += [f"        <th>{c['nome']}</th>" for c in colunas]
    if chave:
        linhas.append("        <th></th>")
    linhas += ["    </tr>", '    {% for linha in listar("' + tabela + '") %}', "    <tr>"]
    linhas += ["        <td>{{ " + acesso("linha", c["nome"]) + " }}</td>" for c in colunas]
    if chave:
        linhas += [
            "        <td>",
            f'            <form method="post" action="/excluir/{tabela}/{{{{ {acesso("linha", chave)} }}}}">',
            '                <button type="submit">Excluir</button>',
            "            </form>",
            "        </td>",
        ]
    linhas += ["    </tr>", "    {% endfor %}", "</table>"]
    return "\n".join(linhas)


@app.route("/painel")
def painel():
    tabelas = []
    for tabela in tabelas_do_banco():
        nome = tabela["nome"]
        colunas = colunas_da_tabela(nome)
        chaves = [c["nome"] for c in colunas if c["chave"] == "PRI"]
        chave = chaves[0] if len(chaves) == 1 else None
        e_visao = tabela["tipo"] == "VIEW"
        estrangeiras = {}
        for fk in ([] if e_visao else chaves_estrangeiras(nome)):
            colunas_ref = colunas_da_tabela(fk["tabela_ref"])
            textos = [c["nome"] for c in colunas_ref if c["chave"] != "PRI" and c["tipo"] in ("varchar", "char")]
            estrangeiras[fk["coluna"]] = {
                "tabela": fk["tabela_ref"],
                "coluna": fk["coluna_ref"],
                "rotulo": textos[0] if textos else fk["coluna_ref"],
            }
        codigo_form = "" if e_visao else codigo_do_formulario(nome, colunas, estrangeiras)
        codigo_lista = codigo_da_lista(nome, colunas, None if e_visao else chave)
        tabelas.append({
            "nome": nome,
            "visao": e_visao,
            "colunas": colunas,
            "chave": chave,
            "estrangeiras": estrangeiras,
            "codigo_form": codigo_form,
            "codigo_lista": codigo_lista,
            # O painel mostra o próprio código funcionando:
            "html_form": Markup(render_template_string(codigo_form)) if codigo_form else "",
            "html_lista": Markup(render_template_string(codigo_lista)),
        })
    return render_template_string(PAGINA_DO_PAINEL, tabelas=tabelas, banco=CONFIG_BANCO["database"])


# 11. ERROS EXPLICADOS EM PORTUGUÊS
# Cada erro do MySQL tem um número. Aqui traduzimos os mais comuns.
# {0} e {1} são trocados pelos nomes que aparecem entre aspas na mensagem original.
ERROS_DO_MYSQL = {
    2003: ("Não foi possível conectar ao MySQL.",
           "O MySQL/MariaDB está ligado? No XAMPP, clique em Start no MySQL. "
           "Confira também host e port no CONFIG_BANCO."),
    1045: ("O MySQL recusou o usuário ou a senha.",
           "Confira user e password no CONFIG_BANCO. No XAMPP a senha costuma ser vazia: \"\"."),
    1049: ("O banco informado no CONFIG_BANCO não existe.",
           "Rode o arquivo banco.sql (CREATE DATABASE) ou corrija o nome em database."),
    1146: ("Uma tabela usada no SQL não existe.",
           "Confira o nome da tabela no seu SELECT ou rode o banco.sql de novo."),
    1054: ("Uma coluna usada no SQL não existe: '{0}'.",
           "Confira o nome da coluna no seu SELECT (veja os nomes certos no /painel)."),
    1064: ("Há um erro de escrita no comando SQL.",
           "Confira o SQL dentro do consultar(): vírgulas, aspas e palavras como FROM e WHERE."),
    1048: ("O campo '{0}' é obrigatório e chegou vazio.",
           "Preencha o campo ou permita NULL nessa coluna."),
    1364: ("O campo '{0}' é obrigatório e não foi preenchido.",
           "Confira se o formulário tem um campo com name=\"{0}\" e se ele foi preenchido."),
    1406: ("O texto do campo '{0}' é maior do que a coluna aceita.",
           "Aumente o tamanho do VARCHAR no banco ou use maxlength no input."),
    1366: ("O valor '{0}' não serve para o campo '{1}'.",
           "Provavelmente é um campo numérico recebendo texto. Use type=\"number\" no input."),
    1292: ("O valor '{0}' não é uma data/hora válida para o campo '{1}'.",
           "Use type=\"date\", type=\"time\" ou type=\"datetime-local\" no input."),
    1265: ("O valor enviado para o campo '{0}' não é aceito pela coluna.",
           "Confira as opções do ENUM ou o tipo da coluna no banco."),
    1062: ("Já existe um registro com o valor '{0}'.",
           "Essa coluna é UNIQUE ou PRIMARY KEY: não aceita valores repetidos."),
    1452: ("O valor escolhido não existe na tabela ligada (chave estrangeira).",
           "Cadastre primeiro o registro \"pai\" (ex.: o time antes do jogador)."),
    1451: ("Este registro não pode ser excluído: outros registros dependem dele.",
           "Exclua primeiro os registros ligados a ele (ex.: os jogadores do time) "
           "ou use ON DELETE CASCADE na chave estrangeira."),
}


@app.errorhandler(ErroDoProjeto)
def mostrar_erro_do_projeto(erro):
    return render_template_string(PAGINA_DE_ERRO, mensagem=erro.mensagem, dica=erro.dica, tecnico=""), erro.status


@app.errorhandler(pymysql.MySQLError)
def mostrar_erro_do_banco(erro):
    codigo = erro.args[0] if erro.args else 0
    original = str(erro.args[1]) if len(erro.args) > 1 else str(erro)
    aspas = re.findall(r"'([^']*)'", original) + ["?", "?"]
    mensagem, dica = ERROS_DO_MYSQL.get(codigo, ("O banco de dados recusou o comando.", "Leia o detalhe técnico abaixo."))
    return render_template_string(
        PAGINA_DE_ERRO,
        mensagem=mensagem.format(*aspas),
        dica=dica.format(*aspas),
        tecnico=f"Erro {codigo} do MySQL: {original}",
    ), 500


# 12. INICIA O SERVIDOR
# Este if garante que o servidor só sobe quando rodamos: python app.py
# debug=True reinicia o servidor ao salvar o arquivo e mostra erros detalhados.
# Para abrir pelo celular na mesma rede (apresentação), use: app.run(debug=True, host="0.0.0.0")
if __name__ == "__main__":
    app.run(debug=True)

# PARA O CADERNO
# Conectar -> criar cursor -> executar SQL -> (commit, se alterou) -> fechar.
# SELECT apenas lê; INSERT, UPDATE e DELETE alteram e precisam de commit.
# Os %s protegem o banco: os valores nunca são colados direto no texto do SQL.
# name do campo no HTML = nome da coluna no banco.


# ---------------------------------------------------------------------------
# PARTE INTERNA — páginas do painel e de erro. Não precisa mexer daqui para baixo.
# ---------------------------------------------------------------------------
ESTILO_INTERNO = """
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, Segoe UI, Roboto, Arial, sans-serif; background: #f3f5f8; color: #1d2430; }
  header { background: #12355b; color: #fff; padding: 18px 24px; }
  header h1 { margin: 0; font-size: 1.3rem; }
  header p { margin: 4px 0 0; opacity: .8; font-size: .9rem; }
  main { max-width: 1100px; margin: 0 auto; padding: 20px 16px 60px; }
  nav a { display: inline-block; margin: 0 6px 6px 0; padding: 4px 12px; border-radius: 99px; background: #dfe7f1; color: #12355b; text-decoration: none; font-size: .9rem; }
  .cartao { background: #fff; border: 1px solid #dde2ea; border-radius: 10px; padding: 18px; margin-top: 20px; }
  .cartao h2 { margin: 0 0 4px; font-size: 1.15rem; }
  .cartao h3 { font-size: .95rem; margin: 18px 0 8px; color: #445; }
  .estrutura { font-size: .8rem; color: #556; }
  .estrutura span { display: inline-block; margin: 2px 6px 2px 0; padding: 2px 8px; border-radius: 6px; background: #eef1f5; }
  .estrutura b { color: #12355b; }
  .colunas { display: grid; grid-template-columns: minmax(240px, 1fr) 2fr; gap: 20px; }
  @media (max-width: 760px) { .colunas { grid-template-columns: 1fr; } }
  form label { display: block; margin-bottom: 10px; font-size: .85rem; font-weight: 600; }
  input, select, textarea { display: block; width: 100%; margin-top: 3px; padding: 7px 9px; border: 1px solid #c5ccd6; border-radius: 6px; font: inherit; font-weight: 400; }
  button { padding: 7px 14px; border: 0; border-radius: 6px; background: #12355b; color: #fff; font: inherit; cursor: pointer; }
  td button { background: #b3261e; padding: 4px 10px; font-size: .8rem; }
  td form { margin: 0; }
  .rolagem { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: .85rem; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e6e9ee; white-space: nowrap; }
  th { background: #f6f8fa; }
  details { margin-top: 16px; }
  summary { cursor: pointer; font-weight: 600; color: #12355b; }
  pre { background: #1d2430; color: #e8edf4; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: .8rem; }
  .copiar { background: #dfe7f1; color: #12355b; font-size: .8rem; padding: 4px 10px; }
  .aviso { background: #fff7e0; border: 1px solid #f0d48a; border-radius: 8px; padding: 12px 14px; }
  .erro { background: #fdecea; border: 1px solid #f3b8b2; border-radius: 10px; padding: 18px; }
  .erro h2 { margin: 0 0 8px; color: #8c1d18; font-size: 1.15rem; }
  .tecnico { font-family: Consolas, monospace; font-size: .8rem; color: #556; background: #f3f5f8; padding: 10px; border-radius: 6px; }
</style>
"""

PAGINA_DO_PAINEL = """<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Painel do banco</title>""" + ESTILO_INTERNO + """</head>
<body>
<header>
  <h1>Painel do banco: {{ banco }}</h1>
  <p>Página só para testar. O site do grupo começa em templates/index.html (endereço /).</p>
</header>
<main>
  {% if not tabelas %}
    <p class="aviso">A conexão funcionou, mas o banco <b>{{ banco }}</b> não tem tabelas. Rode o arquivo banco.sql.</p>
  {% else %}
    <nav>{% for t in tabelas %}<a href="#{{ t.nome }}">{{ t.nome }}</a>{% endfor %}</nav>
  {% endif %}
  {% for t in tabelas %}
  <section class="cartao" id="{{ t.nome }}">
    <h2>{{ t.nome }}{% if t.visao %} (VIEW){% endif %}</h2>
    <div class="estrutura">
      {% for c in t.colunas %}<span><b>{{ c.nome }}</b> {{ c.tipo_completo }}{% if c.chave == 'PRI' %} · PK{% endif %}{% if c.nome in t.estrangeiras %} · FK → {{ t.estrangeiras[c.nome].tabela }}{% endif %}{% if c.aceita_nulo == 'NO' and c.padrao is none and 'auto_increment' not in c.extra %} · obrigatório{% endif %}</span>{% endfor %}
    </div>
    {% if not t.chave and not t.visao %}<p class="aviso">Sem uma PRIMARY KEY simples: dá para cadastrar e listar, mas não editar nem excluir.</p>{% endif %}
    <div class="colunas">
      {% if t.html_form %}<div><h3>Cadastrar</h3>{{ t.html_form }}</div>{% endif %}
      <div><h3>Registros</h3><div class="rolagem">{{ t.html_lista }}</div></div>
    </div>
    <details>
      <summary>Código para usar no seu HTML</summary>
      {% if t.codigo_form %}<h3>Formulário de cadastro <button class="copiar" type="button">Copiar</button></h3><pre>{{ t.codigo_form }}</pre>{% endif %}
      <h3>Tabela com os registros <button class="copiar" type="button">Copiar</button></h3><pre>{{ t.codigo_lista }}</pre>
    </details>
  </section>
  {% endfor %}
</main>
<script>
  document.querySelectorAll(".copiar").forEach(function (botao) {
    botao.addEventListener("click", function () {
      var codigo = botao.parentElement.nextElementSibling.textContent;
      navigator.clipboard.writeText(codigo).then(function () {
        botao.textContent = "Copiado!";
        setTimeout(function () { botao.textContent = "Copiar"; }, 1500);
      });
    });
  });
</script>
</body></html>"""

PAGINA_DE_ERRO = """<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Algo deu errado</title>""" + ESTILO_INTERNO + """</head>
<body>
<header><h1>Algo deu errado</h1><p>O servidor explicou o problema abaixo.</p></header>
<main>
  <section class="erro">
    <h2>{{ mensagem }}</h2>
    {% if dica %}<p><b>Como resolver:</b> {{ dica }}</p>{% endif %}
    {% if tecnico %}<p class="tecnico">{{ tecnico }}</p>{% endif %}
    <p><a href="javascript:history.back()">Voltar</a> · <a href="/painel">Abrir o painel</a></p>
  </section>
</main>
</body></html>"""
